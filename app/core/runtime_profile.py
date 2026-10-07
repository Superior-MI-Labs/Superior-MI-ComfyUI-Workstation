from __future__ import annotations

import platform
from typing import Any, Iterable

from .contracts import RuntimeProfile


def _torch_backend(torch_module: Any) -> str:
    version = getattr(torch_module, "version", None)
    hip = getattr(version, "hip", None)
    cuda_version = getattr(version, "cuda", None)

    cuda = getattr(torch_module, "cuda", None)
    if cuda is not None and callable(getattr(cuda, "is_available", None)) and cuda.is_available():
        if hip:
            return "rocm"
        return "cuda" if cuda_version is not None else "cuda"

    xpu = getattr(torch_module, "xpu", None)
    if xpu is not None and callable(getattr(xpu, "is_available", None)) and xpu.is_available():
        return "xpu"

    backends = getattr(torch_module, "backends", None)
    mps = getattr(backends, "mps", None) if backends is not None else None
    if mps is not None and callable(getattr(mps, "is_available", None)) and mps.is_available():
        return "mps"

    return "cpu"


def observe_runtime(
    *,
    comfyui_url: str = "",
    comfyui_version: str = "",
    installed_node_types: Iterable[str] = (),
    installed_packages: Iterable[str] = (),
    torch_module: Any | None = None,
) -> RuntimeProfile:
    if torch_module is None:
        try:
            import torch as torch_module  # type: ignore
        except ImportError:
            torch_module = None

    if torch_module is None:
        torch_version = ""
        backend = "cpu"
        backend_version = ""
    else:
        torch_version = str(getattr(torch_module, "__version__", ""))
        backend = _torch_backend(torch_module)
        version = getattr(torch_module, "version", None)
        if backend == "rocm":
            backend_version = str(getattr(version, "hip", "") or "")
        elif backend == "cuda":
            backend_version = str(getattr(version, "cuda", "") or "")
        else:
            backend_version = ""

    return RuntimeProfile(
        python_version=platform.python_version(),
        torch_version=torch_version,
        compute_backend=backend,
        backend_version=backend_version,
        comfyui_version=comfyui_version,
        comfyui_url=comfyui_url,
        installed_node_types=frozenset(str(x) for x in installed_node_types),
        installed_packages=tuple(sorted(str(x) for x in installed_packages)),
    )
