from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any, Callable


def _default_get_json(url: str, timeout: float = 5.0) -> Any:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Superior-MI-Labs-ComfyUI-Workstation"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


class ComfyManagerDiscovery:
    """Read-only projection of ComfyUI-Manager registry/runtime metadata."""

    def __init__(
        self,
        base_url: str,
        *,
        get_json: Callable[[str, float], Any] = _default_get_json,
    ):
        self.base_url = base_url.rstrip("/")
        self._get_json = get_json

    def _get(self, path: str, *, query: dict[str, str] | None = None) -> Any:
        url = self.base_url + path
        if query:
            url += "?" + urllib.parse.urlencode(query)
        return self._get_json(url, 5.0)

    def custom_node_list(self, mode: str = "default") -> dict[str, dict[str, Any]]:
        if mode not in {"default", "local", "remote", "cache"}:
            raise ValueError(f"Unsupported Manager mode: {mode}")
        payload = self._get(
            "/customnode/getlist",
            query={"mode": mode, "skip_update": "true"},
        )
        if not isinstance(payload, dict):
            raise RuntimeError("ComfyUI-Manager returned an invalid custom-node list.")
        rows = payload.get("node_packs", {})
        if not isinstance(rows, dict):
            raise RuntimeError("ComfyUI-Manager node_packs payload is invalid.")
        return {
            str(key): value
            for key, value in rows.items()
            if isinstance(value, dict)
        }

    def node_mappings(self, mode: str = "default") -> dict[str, Any]:
        if mode not in {"default", "local", "remote", "cache"}:
            raise ValueError(f"Unsupported Manager mode: {mode}")
        payload = self._get("/customnode/getmappings", query={"mode": mode})
        if not isinstance(payload, dict):
            raise RuntimeError("ComfyUI-Manager returned invalid node mappings.")
        return payload

    def queue_status(self) -> dict[str, Any]:
        payload = self._get("/manager/queue/status")
        if not isinstance(payload, dict):
            raise RuntimeError("ComfyUI-Manager returned invalid queue status.")
        return payload

    def require_package(self, package_id: str, mode: str = "default") -> dict[str, Any]:
        packages = self.custom_node_list(mode=mode)
        direct = packages.get(package_id)
        if direct is not None:
            metadata = dict(direct)
            metadata.setdefault("id", package_id)
            return metadata

        for key, row in packages.items():
            if str(row.get("id") or "") == package_id:
                metadata = dict(row)
                metadata.setdefault("id", key)
                return metadata

        raise KeyError(f"ComfyUI-Manager does not know package ID: {package_id}")
