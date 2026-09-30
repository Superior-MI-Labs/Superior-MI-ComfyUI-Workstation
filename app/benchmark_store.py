from __future__ import annotations
import csv, json, os, re, time, urllib.request
from pathlib import Path
from datetime import datetime

HOME=Path.home(); CONFIG=HOME/".config/superior-mi-comfyui-control"; FILE=CONFIG/"benchmarks.json"; DOWNLOADS=HOME/"Downloads"

def load():
    try:
        data=json.loads(FILE.read_text())
        return data if isinstance(data,list) else []
    except Exception: return []

def save(rows):
    CONFIG.mkdir(parents=True,exist_ok=True); FILE.write_text(json.dumps(rows[-1000:],indent=2)+"\n")

def add(row):
    rows=load(); rows.append(row); save(rows); return row

def clear(): save([])

def export_csv():
    rows=load(); DOWNLOADS.mkdir(parents=True,exist_ok=True)
    out=DOWNLOADS/f"Superior-MI-ComfyUI-Benchmarks-{datetime.now():%Y%m%d-%H%M%S}.csv"
    cols=["finished","prompt_id","elapsed_s","peak_vram_gib","models","resolution","steps","frames","status"]
    with out.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=cols); w.writeheader()
        for r in rows: w.writerow({k:r.get(k,"") for k in cols})
    return out

def fetch_json(url, timeout=1.2):
    req=urllib.request.Request(url,headers={"User-Agent":"Superior-MI-Labs-ComfyUI"})
    with urllib.request.urlopen(req,timeout=timeout) as r: return json.loads(r.read().decode())

def queue_items(base_url):
    q=fetch_json(base_url.rstrip('/')+'/queue')
    out=[]
    for state,key in (("running","queue_running"),("pending","queue_pending")):
        for raw in q.get(key,[]) or []:
            pid=None; prompt=None
            if isinstance(raw,(list,tuple)):
                if len(raw)>1 and isinstance(raw[1],str): pid=raw[1]
                if len(raw)>2 and isinstance(raw[2],dict): prompt=raw[2]
            if not pid:
                # robust fallback: first UUID-like string
                vals=list(raw) if isinstance(raw,(list,tuple)) else []
                for v in vals:
                    if isinstance(v,str) and len(v)>=16: pid=v; break
            if pid: out.append({"id":pid,"state":state,"prompt":prompt or {}})
    return out

def history_status(base_url,pid):
    try:
        data=fetch_json(base_url.rstrip('/')+'/history/'+pid,timeout=1.5)
        item=data.get(pid,{}) if isinstance(data,dict) else {}
        st=item.get('status',{}) if isinstance(item,dict) else {}
        return st.get('status_str') or ('completed' if item else 'unknown')
    except Exception: return 'unknown'

def summarize_prompt(prompt):
    models=[]; widths=[]; heights=[]; steps=[]; frames=[]
    def walk(x):
        if isinstance(x,dict):
            for k,v in x.items():
                kl=str(k).lower()
                if isinstance(v,str) and v.lower().endswith((".safetensors",".gguf",".ckpt")):
                    models.append(Path(v).name)
                if kl=='width' and isinstance(v,(int,float)): widths.append(int(v))
                if kl=='height' and isinstance(v,(int,float)): heights.append(int(v))
                if kl=='steps' and isinstance(v,(int,float)): steps.append(int(v))
                if kl in ('length','frames','num_frames') and isinstance(v,(int,float)): frames.append(int(v))
                walk(v)
        elif isinstance(x,(list,tuple)):
            for v in x: walk(v)
    walk(prompt)
    resolution=''
    if widths and heights: resolution=f"{widths[-1]}x{heights[-1]}"
    return {
      "models":", ".join(dict.fromkeys(models))[:500],
      "resolution":resolution,"steps":steps[-1] if steps else "","frames":frames[-1] if frames else ""
    }
