from pathlib import Path
import sys

APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))

from core.hardware import (
    observe_gpus,
    parse_lspci_gpus,
    parse_os_release_text,
    parse_macos_displays_json,
    parse_nvidia_smi_csv,
    parse_windows_video_json,
)


def test_nvidia_smi_parser_captures_multiple_devices():
    rows = parse_nvidia_smi_csv(
        "NVIDIA RTX A, 12288, 555.10, 8.9\n"
        "NVIDIA RTX B, 24576, 555.10, 9.0\n"
    )
    assert len(rows) == 2
    assert rows[0].vendor == "NVIDIA"
    assert rows[0].vram_bytes == 12288 * 1024**2
    assert rows[0].backend_candidates == ("cuda",)
    assert rows[0].compute_capability == "8.9"


def test_os_release_parser_preserves_distribution_identity():
    values = parse_os_release_text('NAME="Linux Mint"\nVERSION_ID="22.3"\nPRETTY_NAME="Linux Mint 22.3"\n')
    assert values["NAME"] == "Linux Mint"
    assert values["VERSION_ID"] == "22.3"
    assert values["PRETTY_NAME"] == "Linux Mint 22.3"


def test_linux_lspci_discovers_amd_and_intel_without_claiming_runtime():
    rows = parse_lspci_gpus(
        "03:00.0 VGA compatible controller: Advanced Micro Devices, Inc. [AMD/ATI] Navi Example\n"
        "00:02.0 VGA compatible controller: Intel Corporation Arc Example\n"
    )
    assert [gpu.vendor for gpu in rows] == ["AMD", "Intel"]
    assert [gpu.backend_candidates for gpu in rows] == [("rocm",), ("xpu",)]


def test_linux_gpu_profile_reports_candidate_not_active_runtime():
    outputs = {
        ("nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"): "",
        ("lspci",): "03:00.0 VGA compatible controller: Advanced Micro Devices, Inc. [AMD/ATI] Navi Example",
    }

    def fake_run(command):
        return outputs.get(tuple(command), "")

    rows = observe_gpus(system="Linux", run_text=fake_run)
    assert len(rows) == 1
    assert rows[0].vendor == "AMD"
    assert rows[0].backend_candidates == ("rocm",)


def test_macos_system_profiler_parser_marks_apple_mps_candidate():
    rows = parse_macos_displays_json(
        '{"SPDisplaysDataType":[{"sppci_model":"Apple M4","spdisplays_vram_shared":"16 GB"}]}'
    )
    assert len(rows) == 1
    assert rows[0].vendor == "Apple"
    assert rows[0].backend_candidates == ("mps",)
    assert rows[0].vram_bytes == 16 * 1024**3


def test_windows_video_controller_parser_is_data_only():
    rows = parse_windows_video_json(
        '[{"Name":"Intel Arc Example","AdapterRAM":8589934592,"DriverVersion":"1.2.3"},'
        '{"Name":"NVIDIA Example","AdapterRAM":12884901888,"DriverVersion":"4.5.6"}]'
    )
    assert [gpu.vendor for gpu in rows] == ["Intel", "NVIDIA"]
    assert rows[0].driver == "1.2.3"
    # Device detection alone does not prove XPU/CUDA runtime health on Windows.
    assert [gpu.backend_candidates for gpu in rows] == [("xpu",), ("cuda",)]
