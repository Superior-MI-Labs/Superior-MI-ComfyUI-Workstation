from __future__ import annotations
from pathlib import Path
from datetime import datetime

HOME=Path.home(); OUTPUT=HOME/"Projects/AI-Runtimes/ComfyUI/output"
IMG={'.png','.jpg','.jpeg','.webp'}; VID={'.mp4','.webm','.mov','.mkv'}

def scan(limit=200):
    if not OUTPUT.exists(): return []
    rows=[]
    for p in OUTPUT.rglob('*'):
        try:
            if not p.is_file(): continue
            ext=p.suffix.lower()
            if ext not in IMG|VID: continue
            st=p.stat(); typ='Image' if ext in IMG else 'Video'
            rows.append({"type":typ,"name":p.name,"path":str(p),"size":st.st_size,"mtime":st.st_mtime,
                         "time":datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d %H:%M')})
        except OSError: pass
    rows.sort(key=lambda r:r['mtime'],reverse=True)
    return rows[:limit]
