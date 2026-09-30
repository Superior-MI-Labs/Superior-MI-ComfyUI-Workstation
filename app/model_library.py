from __future__ import annotations
import csv, json, os, hashlib
from pathlib import Path
from datetime import datetime

HOME=Path.home()
COMFY=HOME/"Projects/AI-Runtimes/ComfyUI"
CANON=HOME/"Models/Media"
DOWNLOADS=HOME/"Downloads"
MODEL_EXTS={".safetensors",".gguf",".ckpt",".pt",".pth",".bin"}

def human(n):
    n=float(n or 0); units=["B","KiB","MiB","GiB","TiB"]; i=0
    while n>=1024 and i<len(units)-1: n/=1024; i+=1
    return f"{n:.1f} {units[i]}"

def scan():
    rows=[]
    roots=[("ComfyUI",COMFY/"models"),("Canonical",CANON)]
    seen=set()
    for origin,root in roots:
        if not root.exists(): continue
        for p in root.rglob("*"):
            try:
                if not (p.is_file() or p.is_symlink()): continue
                if p.suffix.lower() not in MODEL_EXTS: continue
                key=(origin,str(p))
                if key in seen: continue
                seen.add(key)
                broken=p.is_symlink() and not p.exists()
                target=""
                if p.is_symlink():
                    try: target=os.path.realpath(p)
                    except Exception: target="?"
                try: size=0 if broken else p.stat().st_size
                except Exception: size=0
                try:
                    rel=p.relative_to(root)
                    category=rel.parts[0] if len(rel.parts)>1 else "root"
                except Exception:
                    category="?"
                rows.append({
                    "origin":origin,"category":category,"name":p.name,"path":str(p),
                    "size":size,"size_h":human(size),"symlink":p.is_symlink(),
                    "target":target,"status":"BROKEN" if broken else "OK"
                })
            except OSError:
                continue
    rows.sort(key=lambda r:(r["status"]!="BROKEN",r["category"].lower(),r["name"].lower(),r["origin"]))
    return rows

def duplicate_report(rows=None):
    rows=rows or scan(); by={}
    for r in rows:
        if r["status"]!="OK": continue
        by.setdefault(r["name"],[]).append(r)
    dup=[]
    for name,items in by.items():
        # Ignore the expected canonical + Comfy symlink pairing if same target.
        physical=[]
        targets=set()
        for r in items:
            physical.append(r)
            targets.add(r["target"] if r["symlink"] else r["path"])
        if len(targets)>1:
            dup.append((name,items))
    return sorted(dup,key=lambda x:x[0].lower())

def broken_links(rows=None):
    return [r for r in (rows or scan()) if r["status"]=="BROKEN"]

def summary(rows=None):
    rows=rows or scan()
    physical=[r for r in rows if r["status"]=="OK" and not r["symlink"]]
    return {
        "entries":len(rows),
        "physical_files":len(physical),
        "physical_bytes":sum(r["size"] for r in physical),
        "broken":len(broken_links(rows)),
        "duplicate_names":len(duplicate_report(rows)),
    }

def export_manifest(rows=None):
    rows=rows or scan(); DOWNLOADS.mkdir(parents=True,exist_ok=True)
    out=DOWNLOADS/f"Superior-MI-Model-Manifest-{datetime.now():%Y%m%d-%H%M%S}.json"
    payload={"generated":datetime.now().isoformat(),"summary":summary(rows),"models":rows}
    out.write_text(json.dumps(payload,indent=2)+"\n")
    return out
