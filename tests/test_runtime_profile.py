from pathlib import Path
import sys
from types import SimpleNamespace

APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))

from core.runtime_profile import observe_runtime


class Available:
    def __init__(self, value):
        self.value = value

    def is_available(self):
        return self.value


def fake_torch(*, cuda=False, hip=None, cuda_version=None, xpu=False, mps=False):
    return SimpleNamespace(
        __version__="9.9.test",
        version=SimpleNamespace(hip=hip, cuda=cuda_version),
        cuda=Available(cuda),
        xpu=Available(xpu),
        backends=SimpleNamespace(mps=Available(mps)),
    )


def test_runtime_classifies_cuda():
    runtime = observe_runtime(torch_module=fake_torch(cuda=True, cuda_version="13.0"))
    assert runtime.compute_backend == "cuda"
    assert runtime.backend_version == "13.0"
    assert runtime.torch_version == "9.9.test"


def test_runtime_distinguishes_rocm_from_torch_cuda_compat_api():
    runtime = observe_runtime(torch_module=fake_torch(cuda=True, hip="7.0"))
    assert runtime.compute_backend == "rocm"
    assert runtime.backend_version == "7.0"


def test_runtime_classifies_xpu_and_mps():
    assert observe_runtime(torch_module=fake_torch(xpu=True)).compute_backend == "xpu"
    assert observe_runtime(torch_module=fake_torch(mps=True)).compute_backend == "mps"


def test_runtime_cpu_fallback_and_canonical_inventory():
    runtime = observe_runtime(
        torch_module=fake_torch(),
        comfyui_url="http://127.0.0.1:8188",
        comfyui_version="example",
        installed_node_types=["KSampler", "LoadImage", "KSampler"],
        installed_packages=["z-package", "a-package"],
    )
    assert runtime.compute_backend == "cpu"
    assert runtime.installed_node_types == frozenset({"KSampler", "LoadImage"})
    assert runtime.installed_packages == ("a-package", "z-package")
