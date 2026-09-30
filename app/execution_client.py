from __future__ import annotations

import json
import socket
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

try:
    import websocket
except Exception:
    websocket = None

HOME = Path.home()
COMFY_OUTPUT = HOME / "Projects" / "AI-Runtimes" / "ComfyUI" / "output"

def _url(base_url: str, path: str) -> str:
    return base_url.rstrip("/") + path

def _get_json(url, timeout=3.0):
    req=urllib.request.Request(url,headers={"User-Agent":"Superior-MI-Labs-ComfyUI-Workstation"})
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def _queue(prompt: dict, base_url: str, client_id: str) -> str:
    payload=json.dumps({"prompt":prompt,"client_id":client_id}).encode("utf-8")
    req=urllib.request.Request(
        _url(base_url,"/prompt"),
        data=payload,
        method="POST",
        headers={"Content-Type":"application/json","User-Agent":"Superior-MI-Labs-ComfyUI-Workstation"},
    )
    with urllib.request.urlopen(req,timeout=10) as r:
        data=json.loads(r.read().decode("utf-8"))
    if "prompt_id" not in data:
        raise RuntimeError(f"ComfyUI queue response did not contain prompt_id: {data}")
    return str(data["prompt_id"])

def _history(prompt_id: str, base_url: str):
    try:
        return _get_json(_url(base_url,f"/history/{urllib.parse.quote(prompt_id)}"),timeout=3.0)
    except Exception:
        return {}

def _find_outputs(history: dict, prompt_id: str) -> list[dict]:
    item=history.get(prompt_id,{}) if isinstance(history,dict) else {}
    outputs=item.get("outputs",{}) if isinstance(item,dict) else {}
    rows=[]
    seen=set()
    def walk(x):
        if isinstance(x,dict):
            if "filename" in x and isinstance(x.get("filename"),str):
                key=(x.get("filename"),x.get("subfolder",""),x.get("type","output"))
                if key not in seen:
                    seen.add(key)
                    rows.append({"filename":key[0],"subfolder":key[1] or "","type":key[2] or "output"})
            for v in x.values(): walk(v)
        elif isinstance(x,(list,tuple)):
            for v in x: walk(v)
    walk(outputs)
    for r in rows:
        if r["type"] == "output":
            r["path"] = str(COMFY_OUTPUT / r["subfolder"] / r["filename"])
        else:
            r["path"] = ""
    return rows

def _node_label(prompt, node_id):
    node=prompt.get(str(node_id),{}) if isinstance(prompt,dict) else {}
    return str((node.get("_meta") or {}).get("title") or node.get("class_type") or node_id)

def _poll_until_done(prompt_id, prompt, base_url, callback, started, timeout):
    callback({"state":"running","percent":0.0,"stage":"Queued","detail":"Waiting for ComfyUI…","elapsed":0})
    while time.time()-started < timeout:
        hist=_history(prompt_id,base_url)
        item=hist.get(prompt_id) if isinstance(hist,dict) else None
        if item:
            status=(item.get("status") or {}).get("status_str","completed")
            outputs=_find_outputs(hist,prompt_id)
            callback({"state":"completed" if status=="success" else status,"percent":1.0,"stage":"Complete","detail":status,"elapsed":time.time()-started,"outputs":outputs})
            return {"prompt_id":prompt_id,"status":status,"outputs":outputs,"history":hist}
        time.sleep(1.0)
    raise TimeoutError(f"Timed out waiting for ComfyUI prompt {prompt_id}")

def queue_and_monitor(prompt: dict, base_url: str, callback=lambda event: None, timeout=7200):
    """Queue one prompt and stream progress. Falls back to history polling."""
    client_id=str(uuid.uuid4())
    started=time.time()
    ws=None

    if websocket is not None:
        try:
            parsed=urllib.parse.urlparse(base_url)
            scheme="wss" if parsed.scheme=="https" else "ws"
            host=parsed.netloc or parsed.path
            ws=websocket.create_connection(f"{scheme}://{host}/ws?clientId={client_id}",timeout=2)
        except Exception:
            ws=None

    prompt_id=_queue(prompt,base_url,client_id)
    callback({"state":"queued","prompt_id":prompt_id,"percent":0.0,"stage":"Queued","detail":"ComfyUI accepted the job.","elapsed":0})

    if ws is None:
        return _poll_until_done(prompt_id,prompt,base_url,callback,started,timeout)

    executed=set()
    total_nodes=max(1,len(prompt))
    last_percent=0.0
    try:
        ws.settimeout(2)
        while time.time()-started < timeout:
            try:
                raw=ws.recv()
            except Exception as exc:
                # Socket timeouts are normal. History is authoritative for terminal state.
                hist=_history(prompt_id,base_url)
                if isinstance(hist,dict) and prompt_id in hist:
                    outputs=_find_outputs(hist,prompt_id)
                    callback({"state":"completed","prompt_id":prompt_id,"percent":1.0,"stage":"Complete","detail":"Output saved.","elapsed":time.time()-started,"outputs":outputs})
                    return {"prompt_id":prompt_id,"status":"completed","outputs":outputs,"history":hist}
                continue
            if not isinstance(raw,str):
                continue
            try:
                msg=json.loads(raw)
            except Exception:
                continue
            typ=msg.get("type")
            data=msg.get("data") or {}
            if data.get("prompt_id") not in (None,prompt_id):
                continue

            if typ=="execution_start":
                callback({"state":"running","prompt_id":prompt_id,"percent":max(last_percent,0.01),"stage":"Starting","detail":"Execution started.","elapsed":time.time()-started})
            elif typ=="executing":
                node=data.get("node")
                if node is None:
                    continue
                base=len(executed)/total_nodes
                last_percent=max(last_percent,min(.98,base))
                callback({"state":"running","prompt_id":prompt_id,"percent":last_percent,"stage":_node_label(prompt,node),"node":str(node),"detail":"Running node","elapsed":time.time()-started})
            elif typ=="progress":
                value=float(data.get("value",0) or 0)
                maximum=max(1.0,float(data.get("max",1) or 1))
                node=data.get("node")
                frac=max(0.0,min(1.0,value/maximum))
                overall=min(.98,(len(executed)+frac)/total_nodes)
                last_percent=max(last_percent,overall)
                callback({"state":"running","prompt_id":prompt_id,"percent":last_percent,"node":str(node) if node is not None else "","stage":_node_label(prompt,node),"detail":f"{int(value)}/{int(maximum)}","elapsed":time.time()-started})
            elif typ=="progress_state":
                nodes=data.get("nodes") or {}
                done=sum(1 for x in nodes.values() if x.get("state")=="finished")
                running=[x for x in nodes.values() if x.get("state")=="running"]
                frac=0.0
                detail="Working…"
                if running:
                    x=running[-1]
                    mx=max(1.0,float(x.get("max",1) or 1))
                    frac=max(0.0,min(1.0,float(x.get("value",0) or 0)/mx))
                    detail=f"{int(float(x.get('value',0) or 0))}/{int(mx)}"
                overall=min(.98,(done+frac)/total_nodes)
                last_percent=max(last_percent,overall)
                callback({"state":"running","prompt_id":prompt_id,"percent":last_percent,"stage":"Generating","detail":detail,"elapsed":time.time()-started})
            elif typ=="executed":
                node=data.get("node")
                if node is not None:
                    executed.add(str(node))
            elif typ=="execution_error":
                raise RuntimeError(data.get("exception_message") or "ComfyUI execution error")
            elif typ=="execution_interrupted":
                raise RuntimeError("Generation was interrupted.")
            elif typ=="execution_success":
                hist=_history(prompt_id,base_url)
                outputs=_find_outputs(hist,prompt_id)
                callback({"state":"completed","prompt_id":prompt_id,"percent":1.0,"stage":"Complete","detail":"Output saved.","elapsed":time.time()-started,"outputs":outputs})
                return {"prompt_id":prompt_id,"status":"completed","outputs":outputs,"history":hist}

        raise TimeoutError(f"Timed out waiting for ComfyUI prompt {prompt_id}")
    finally:
        try:
            ws.close()
        except Exception:
            pass
