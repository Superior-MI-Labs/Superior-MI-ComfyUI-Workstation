#!/usr/bin/env python3
from __future__ import annotations
import importlib
import os
import platform
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent.parent
APP_DIR = APP_ROOT / "app"

def emit(label, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL':4}  {label:26} {detail}")
    return ok

def main():
    print("SUPERIOR MI LABS / COMFYUI WORKSTATION DIAGNOSTICS")
    print("=" * 64)
    print("Python:", sys.version.replace("\\n", " "))
    print("Executable:", sys.executable)
    print("Platform:", platform.platform())
    print("DISPLAY:", os.environ.get("DISPLAY", "<unset>"))
    print("WAYLAND_DISPLAY:", os.environ.get("WAYLAND_DISPLAY", "<unset>"))
    print("XDG_SESSION_TYPE:", os.environ.get("XDG_SESSION_TYPE", "<unset>"))
    print()

    ok_all = True
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk, Gdk, GdkPixbuf, GLib, Pango
        ok_all &= emit("PyGObject / GTK3 import", True, f"GTK {Gtk.get_major_version()}.{Gtk.get_minor_version()}.{Gtk.get_micro_version()}")
        try:
            display = Gdk.Display.get_default()
            ok_all &= emit("GDK display", display is not None, str(display) if display else "No graphical display available")
        except Exception as e:
            ok_all &= emit("GDK display", False, repr(e))
    except Exception as e:
        ok_all &= emit("PyGObject / GTK3 import", False, repr(e))

    modules = [
        "preset_manager", "stack_manager", "role_assets", "model_library",
        "benchmark_store", "gallery_helper", "setup_helper",
        "character_library", "creation_helper", "platform_support", "update_manager", "startup_guard",
    ]
    sys.path.insert(0, str(APP_DIR))
    for name in modules:
        try:
            importlib.import_module(name)
            ok_all &= emit(f"module: {name}", True)
        except Exception as e:
            ok_all &= emit(f"module: {name}", False, repr(e))

    required = [
        APP_ROOT / "assets" / "superior-mi-comfyui.png",
        APP_ROOT / "assets" / "kisha" / "03_kisha_digital_interface_reference_sheet.png",
        APP_ROOT / "assets" / "characters" / "bundled" / "Human" / "Kisha.png",
        APP_ROOT / "preset_library" / "index.json",
        APP_ROOT / "catalog" / "stacks.json",
    ]
    for p in required:
        ok_all &= emit("asset: " + p.name, p.exists(), str(p))

    print()
    print("Result:", "PASS" if ok_all else "FAIL")
    return 0 if ok_all else 1

if __name__ == "__main__":
    raise SystemExit(main())
