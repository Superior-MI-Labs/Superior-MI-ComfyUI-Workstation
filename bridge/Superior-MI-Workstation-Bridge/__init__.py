from __future__ import annotations

import asyncio

from aiohttp import web
from server import PromptServer

from . import workstation_runtime

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
WEB_DIRECTORY = "./web/js"

_PENDING = None


def _is_local_request(request) -> bool:
    remote = str(request.remote or "").strip().lower()
    return remote in {"127.0.0.1", "::1", "localhost"} or remote.startswith("::ffff:127.")


@PromptServer.instance.routes.get("/superior-mi/bridge/status")
async def superior_mi_bridge_status(request):
    return web.json_response({
        "ok": True,
        "bridge": "Superior-MI-Workstation-Bridge",
        "version": "3",
        "core": workstation_runtime.core_status(),
    })


@PromptServer.instance.routes.get("/superior-mi/core/status")
async def superior_mi_core_status(request):
    return web.json_response(workstation_runtime.core_status())


@PromptServer.instance.routes.post("/superior-mi/assistant/propose")
async def superior_mi_assistant_propose(request):
    if not _is_local_request(request):
        return web.json_response(
            {"ok": False, "error": "Assistant planning is local-only in Core R1."},
            status=403,
        )
    try:
        data = await request.json()
        result = await asyncio.to_thread(workstation_runtime.propose, data)
        return web.json_response(result)
    except (ValueError, KeyError) as exc:
        return web.json_response({"ok": False, "error": str(exc)}, status=400)
    except Exception as exc:
        return web.json_response({"ok": False, "error": str(exc)}, status=500)


@PromptServer.instance.routes.post("/superior-mi/open-workflow")
async def superior_mi_open_workflow(request):
    global _PENDING
    if not _is_local_request(request):
        return web.json_response(
            {"ok": False, "error": "Workflow handoff is local-only."},
            status=403,
        )
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
