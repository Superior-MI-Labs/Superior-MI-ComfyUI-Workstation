from __future__ import annotations
from aiohttp import web
from server import PromptServer

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
WEB_DIRECTORY = "./web/js"

_PENDING = None

@PromptServer.instance.routes.get("/superior-mi/bridge/status")
async def superior_mi_bridge_status(request):
    return web.json_response({"ok": True, "bridge": "Superior-MI-Workstation-Bridge", "version": "2"})

@PromptServer.instance.routes.post("/superior-mi/open-workflow")
async def superior_mi_open_workflow(request):
    global _PENDING
    data = await request.json()
    if not isinstance(data, dict) or not data.get("path"):
        return web.json_response({"ok": False, "error": "path is required"}, status=400)
    _PENDING = {"path": str(data["path"])}
    PromptServer.instance.send_sync("superior_mi.open_workflow", _PENDING)
    return web.json_response({"ok": True, "pending": _PENDING})

@PromptServer.instance.routes.get("/superior-mi/pending-workflow")
async def superior_mi_pending_workflow(request):
    global _PENDING
    data = _PENDING
    if request.rel_url.query.get("consume", "1") not in ("0", "false", "False"):
        _PENDING = None
    return web.json_response({"ok": True, "pending": data})

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
