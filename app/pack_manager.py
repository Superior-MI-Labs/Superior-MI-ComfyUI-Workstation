from __future__ import annotations
import blueprint_manager
import stack_manager

def install_pack(pack: dict, authorized: bool = False, progress=None) -> str:
    results=[]
    stacks=blueprint_manager.pack_stacks(pack)
    for idx,st in enumerate(stacks,start=1):
        if progress:
            progress(f"{pack['title']}: component {idx}/{len(stacks)} — {st['title']}")
        results.append(f"=== {st['title']} ===")
        results.append(stack_manager.download_stack(st, authorized=authorized, progress=progress))
    return "\n".join(results)
