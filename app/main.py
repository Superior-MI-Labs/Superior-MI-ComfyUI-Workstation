#!/usr/bin/env python3
from __future__ import annotations

import json
import hashlib
import math
import os
import shutil
import signal
import socket
import subprocess
import threading
import time
import urllib.request
import sys
import traceback
from datetime import datetime
from pathlib import Path

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib, GdkPixbuf, Pango

import preset_manager
import stack_manager
import role_assets
import model_library
import benchmark_store
import gallery_helper
import setup_helper
import character_library
import creation_helper
import platform_support
import blueprint_manager
import pack_manager
import comfy_integration
import execution_client
import update_manager
import startup_guard

APP_NAME = "Superior MI Labs - ComfyUI Workstation"
APP_ID = "com.superiormi.labs.comfyui"
VERSION = "3.0.3"
SAFE_MODE = "--safe" in sys.argv

HOME = Path.home()
COMFY = HOME / "Projects/AI-Runtimes/ComfyUI"
RUNTIMES = HOME / "Projects/AI-Runtimes"
QUAL = RUNTIMES / "Qualification"
START_HELPER = QUAL / "bin/q-start-comfyui.sh"
STOP_HELPER = QUAL / "bin/q-stop-comfyui.sh"
FALLBACK_START = RUNTIMES / "run-comfyui.sh"
MODEL_ROOT = HOME / "Models/Media"
PRESET_ROOT = QUAL / "presets"
LOG_ROOT = QUAL / "logs"
OUTPUT_ROOT = COMFY / "output"
INPUT_ROOT = COMFY / "input"
TEMP_ROOT = COMFY / "temp"
APP_ROOT = Path(__file__).resolve().parent.parent
INSTALL_ROOT = APP_ROOT
SYSTEM_INSTALL = str(APP_ROOT).startswith("/opt/") or str(APP_ROOT).startswith("/usr/")
CONFIG_DIR = HOME / ".config/superior-mi-comfyui-control"
CONFIG_FILE = CONFIG_DIR / "config.json"
CACHE_DIR = HOME / ".cache/superior-mi-comfyui-workstation"
CRASH_LOG = CACHE_DIR / "crash.log"
LAST_CRASH_LOG = CACHE_DIR / "last-crash.log"
LAST_RUN_LOG = CACHE_DIR / "last-run.log"

SOCIAL_LINKS = {
    "GitHub": "https://github.com/Superior-MI-Labs",
    "Hugging Face": "https://huggingface.co/Superior-Mind-Labs",
    "Facebook": "https://www.facebook.com/profile.php?id=61594542915752",
}

DEFAULT_CONFIG = {
    "host": "127.0.0.1",
    "port": 8188,
    "refresh_seconds": 2,
    "browser_url": "http://127.0.0.1:8188",
    "log_lines": 350,
    "splash": False,
    "auto_benchmark": True,
    "onboarding_complete": False,
}

CSS = b"""
window {
    background: #07101a;
    color: #e8f2fb;
}
#topbar {
    background: #0b1725;
    border-bottom: 1px solid #1b3851;
}
#brand-title {
    font-size: 22px;
    font-weight: 800;
    color: #f3f8fd;
}
#brand-subtitle {
    color: #81a6c1;
}
.card {
    background: #0d1a28;
    border: 1px solid #1d3850;
    border-radius: 14px;
    padding: 14px;
}
.hero-card {
    background: #0b1b2b;
    border: 1px solid #27516f;
    border-radius: 16px;
}
.status-running {
    background: #0c2725;
    border: 1px solid #1c9a86;
    border-radius: 12px;
}
.status-stopped {
    background: #24131a;
    border: 1px solid #844154;
    border-radius: 12px;
}
.status-starting {
    background: #28220e;
    border: 1px solid #a17b25;
    border-radius: 12px;
}
.status-warning {
    background: #281b11;
    border: 1px solid #ad6732;
    border-radius: 12px;
}
.status-title {
    font-size: 20px;
    font-weight: 800;
}
.section-title {
    font-size: 15px;
    font-weight: 700;
    color: #cdeeff;
}
.muted {
    color: #88a1b5;
}
.metric-value {
    font-size: 17px;
    font-weight: 800;
    color: #f4fbff;
}
.role-title { font-size: 14px; font-weight: 800; color: #80e7ff; }
.role-caption { color: #8daabd; font-size: 11px; }
.warning { color: #ffbd74; }
.success { color: #72e0c7; }
.kisha-label {
    color: #6bdcff;
    font-weight: 800;
}
button {
    background: #14283b;
    color: #eef8ff;
    border: 1px solid #2b4f69;
    border-radius: 9px;
    padding: 8px 12px;
}
button:hover {
    background: #1a354d;
}
button.suggested-action {
    background: #0f5f93;
    border-color: #2b9ed1;
}
button.destructive-action {
    background: #5a2838;
    border-color: #a14a61;
}
notebook header {
    background: #09131f;
}
notebook tab {
    padding: 8px 14px;
}
textview {
    background: #050b12;
    color: #cfe5f2;
    font-family: monospace;
    border: 1px solid #1c3448;
}
entry, spinbutton {
    background: #07101a;
    color: #edf7fc;
    border: 1px solid #29465d;
    border-radius: 7px;
}
progressbar trough {
    background: #172736;
    border-radius: 6px;
}
progressbar progress {
    background: #2ca7c9;
    border-radius: 6px;
}
separator {
    background: #193248;
}
"""

def write_crash(text, context="Unhandled exception"):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = f"=== {datetime.now().isoformat()} / {VERSION} / {context} ===\n"
    payload = stamp + str(text).rstrip() + "\n"
    try:
        with CRASH_LOG.open("a") as f:
            f.write("\n" + payload)
    except Exception:
        pass
    try:
        LAST_CRASH_LOG.write_text(payload)
    except Exception:
        pass

def install_exception_hook():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    def hook(exc_type, exc_value, exc_tb):
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        write_crash(text)
        sys.__excepthook__(exc_type, exc_value, exc_tb)
    sys.excepthook = hook

def ensure_config():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    cfg = dict(DEFAULT_CONFIG)
    try:
        if CONFIG_FILE.exists():
            raw = json.loads(CONFIG_FILE.read_text())
            if isinstance(raw, dict):
                cfg.update(raw)
    except Exception:
        pass
    if SAFE_MODE:
        cfg["splash"] = False
        cfg["auto_benchmark"] = False
    return cfg

def save_config(cfg):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2) + "\n")

def run_text(cmd, timeout=12, cwd=None, env=None):
    try:
        p = subprocess.run(
            cmd,
            cwd=cwd,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
        return p.returncode, p.stdout.strip()
    except Exception as e:
        return 999, str(e)

def notify(title, body):
    if shutil.which("notify-send"):
        subprocess.Popen(
            ["notify-send", "-a", APP_NAME, title, body],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

def open_path(path: Path):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    platform_support.open_target(path)

def open_url(url: str):
    platform_support.open_target(url)

def fmt_bytes(n):
    if not n:
        return "0 B"
    n = float(n)
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    i = 0
    while n >= 1024 and i < len(units) - 1:
        n /= 1024.0
        i += 1
    return f"{n:.1f} {units[i]}"

def comfy_pids():
    out = []
    try:
        target = str(COMFY.resolve())
    except Exception:
        target = str(COMFY)
    proc = Path("/proc")
    if not proc.exists():
        return out
    for d in proc.iterdir():
        if not d.name.isdigit():
            continue
        try:
            cwd = os.path.realpath(str(d / "cwd"))
            if cwd != target:
                continue
            cmd = (d / "cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace")
            if "main.py" in cmd and "python" in cmd.lower():
                out.append(int(d.name))
        except Exception:
            continue
    return sorted(out)

def process_cmdline(pid):
    try:
        return (Path("/proc") / str(pid) / "cmdline").read_bytes().replace(b"\0", b" ").decode().strip()
    except Exception:
        return ""

def port_open(host, port):
    try:
        with socket.create_connection((host, int(port)), timeout=0.35):
            return True
    except Exception:
        return False

def http_ok(base_url):
    for endpoint in ("/system_stats", "/"):
        try:
            req = urllib.request.Request(
                base_url.rstrip("/") + endpoint,
                headers={"User-Agent": APP_NAME},
            )
            with urllib.request.urlopen(req, timeout=0.8) as r:
                if 200 <= r.status < 500:
                    return True
        except Exception:
            continue
    return False

def latest_log():
    if not LOG_ROOT.exists():
        return None
    logs = sorted(LOG_ROOT.glob("comfyui-*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    return logs[0] if logs else None

def dir_size(root: Path):
    total = 0
    if not root.exists():
        return 0
    try:
        for base, _, names in os.walk(root):
            for name in names:
                p = Path(base) / name
                try:
                    if p.is_symlink():
                        continue
                    total += p.stat().st_size
                except OSError:
                    pass
    except Exception:
        pass
    return total

def count_models(root: Path):
    exts = {".safetensors", ".gguf", ".ckpt", ".pt", ".pth"}
    count = 0
    if root.exists():
        for p in root.rglob("*"):
            if p.is_file() and p.suffix.lower() in exts:
                count += 1
    return count

class RuntimeStatus:
    def __init__(self):
        self.state = "STOPPED"
        self.detail = ""
        self.pids = []
        self.port = False
        self.http = False
        self.cmdline = ""
        self.gpu_name = "Unavailable"
        self.gpu_used = self.gpu_total = 0
        self.gpu_util = self.gpu_temp = 0
        self.ram_used = self.ram_total = 0
        self.disk_free = self.disk_total = 0
        self.git_head = "?"
        self.log_path = None
        self.model_count = 0
        self.model_size = 0

def collect_status(cfg, include_inventory=False):
    s = RuntimeStatus()
    s.pids = comfy_pids()
    s.port = port_open(cfg["host"], cfg["port"])
    s.http = http_ok(cfg["browser_url"]) if s.port else False
    s.cmdline = process_cmdline(s.pids[0]) if s.pids else ""

    if s.pids and s.http:
        s.state = "RUNNING"
        s.detail = f"Healthy on {cfg['host']}:{cfg['port']} • PID {s.pids[0]}"
    elif s.pids and s.port:
        s.state = "DEGRADED"
        s.detail = "Process and listener exist, but HTTP health did not answer."
    elif s.pids and not s.port:
        s.state = "STARTING"
        s.detail = f"Process detected • waiting for port {cfg['port']}"
    elif not s.pids and s.port:
        s.state = "PORT CONFLICT"
        s.detail = f"Port {cfg['port']} is occupied by another process."
    else:
        s.state = "STOPPED"
        s.detail = "No ComfyUI runtime process detected."

    rc, out = run_text([
        "nvidia-smi",
        "--query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu",
        "--format=csv,noheader,nounits",
    ], timeout=3)
    if rc == 0 and out:
        try:
            p = [x.strip() for x in out.splitlines()[0].split(",")]
            s.gpu_name = p[0]
            s.gpu_used = int(float(p[1])) * 1024**2
            s.gpu_total = int(float(p[2])) * 1024**2
            s.gpu_util = int(float(p[3]))
            s.gpu_temp = int(float(p[4]))
        except Exception:
            pass

    try:
        mem = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            k, v = line.split(":", 1)
            mem[k] = int(v.strip().split()[0]) * 1024
        s.ram_total = mem.get("MemTotal", 0)
        s.ram_used = s.ram_total - mem.get("MemAvailable", 0)
    except Exception:
        pass

    try:
        st = os.statvfs(str(HOME))
        s.disk_total = st.f_blocks * st.f_frsize
        s.disk_free = st.f_bavail * st.f_frsize
    except Exception:
        pass

    if COMFY.exists():
        rc, out = run_text(["git", "rev-parse", "--short", "HEAD"], timeout=3, cwd=COMFY)
        if rc == 0:
            s.git_head = out

    s.log_path = latest_log()
    if include_inventory:
        s.model_count = count_models(MODEL_ROOT)
        s.model_size = dir_size(MODEL_ROOT)
    return s

class KishaOrb(Gtk.DrawingArea):
    def __init__(self):
        super().__init__()
        self.set_size_request(112, 112)
        self.phase = 0.0
        self.state = "STOPPED"
        self.connect("draw", self.on_draw)
        GLib.timeout_add(55, self.tick)

    def set_state(self, state):
        self.state = state
        self.queue_draw()

    def tick(self):
        self.phase = (self.phase + 0.055) % (math.pi * 2)
        self.queue_draw()
        return True

    def on_draw(self, widget, cr):
        a = widget.get_allocated_width()
        b = widget.get_allocated_height()
        cx, cy = a / 2, b / 2
        active = self.state in ("RUNNING", "STARTING", "DEGRADED")
        pulse = 0.5 + 0.5 * math.sin(self.phase)

        # Northern digital halo
        cr.set_line_width(2.0)
        if active:
            cr.set_source_rgba(0.20, 0.78, 0.95, 0.30 + 0.35 * pulse)
        else:
            cr.set_source_rgba(0.26, 0.39, 0.49, 0.32)
        cr.arc(cx, cy, 46 + (3 * pulse if active else 0), 0, math.pi * 2)
        cr.stroke()

        # Hair silhouette
        cr.set_source_rgb(0.035, 0.075, 0.115)
        cr.arc(cx, cy - 2, 40, 0, math.pi * 2)
        cr.fill()

        # Face
        cr.set_source_rgb(0.83, 0.69, 0.62)
        cr.arc(cx, cy - 1, 27, 0, math.pi * 2)
        cr.fill()

        # Dark wavy hair framing + glacial-blue strands
        cr.set_line_cap(1)
        for i in range(9):
            ang = -2.7 + i * 0.65
            x0 = cx + math.cos(ang) * 25
            y0 = cy - 7 + math.sin(ang) * 25
            cr.set_line_width(8)
            cr.set_source_rgb(0.025, 0.055, 0.085)
            cr.move_to(x0, y0)
            cr.curve_to(x0 + 12, y0 + 9, x0 - 8, y0 + 23, x0 + 4, y0 + 38)
            cr.stroke()
        for i in (1, 4, 7):
            ang = -2.7 + i * 0.65
            x0 = cx + math.cos(ang) * 25
            y0 = cy - 7 + math.sin(ang) * 25
            cr.set_line_width(2.5)
            cr.set_source_rgba(0.11, 0.65, 0.96, 0.95)
            cr.move_to(x0, y0)
            cr.curve_to(x0 + 10, y0 + 8, x0 - 5, y0 + 21, x0 + 3, y0 + 34)
            cr.stroke()

        # Eyes
        cr.set_source_rgb(0.10, 0.55, 0.93)
        cr.arc(cx - 9, cy - 3, 2.8, 0, math.pi * 2)
        cr.arc(cx + 9, cy - 3, 2.8, 0, math.pi * 2)
        cr.fill()

        # Small Lake Superior current mark
        cr.set_line_width(2.2)
        cr.set_source_rgb(0.30, 0.84, 0.95)
        for off in (-3, 3):
            cr.move_to(cx - 14, cy + 18 + off)
            cr.curve_to(cx - 5, cy + 12 + off, cx + 2, cy + 24 + off, cx + 14, cy + 16 + off)
            cr.stroke()
        return False

class KishaRoleImage(Gtk.Image):
    def __init__(self, role="digital", max_w=150, max_h=190):
        super().__init__()
        self.role=role
        self.max_w=max_w; self.max_h=max_h
        self.reload()

    def reload(self):
        if SAFE_MODE:
            self.set_from_icon_name("avatar-default", Gtk.IconSize.DIALOG)
            self.set_tooltip_text("Kisha (Safe Mode)")
            return
        p=role_assets.role_path(self.role)
        try:
            pix=GdkPixbuf.Pixbuf.new_from_file(str(p))
            w,h=pix.get_width(),pix.get_height()
            scale=min(self.max_w/max(1,w),self.max_h/max(1,h))
            nw=max(1,int(w*scale)); nh=max(1,int(h*scale))
            pix=pix.scale_simple(nw,nh,GdkPixbuf.InterpType.BILINEAR)
            self.set_from_pixbuf(pix)
            self.set_tooltip_text(role_assets.ROLE_TITLES.get(self.role,"Kisha"))
        except Exception:
            self.set_from_icon_name("avatar-default",Gtk.IconSize.DIALOG)

class RoleHeader(Gtk.Box):
    def __init__(self, role, title, subtitle):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL,spacing=14)
        self.get_style_context().add_class("hero-card")
        self.set_border_width(10)
        self.pack_start(KishaRoleImage(role,92,118),False,False,0)
        b=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=3)
        rt=Gtk.Label(label=role_assets.ROLE_TITLES.get(role,"Kisha"),xalign=0); rt.get_style_context().add_class("kisha-label")
        t=Gtk.Label(label=title,xalign=0); t.get_style_context().add_class("status-title")
        sub=Gtk.Label(label=subtitle,xalign=0); sub.set_line_wrap(True); sub.get_style_context().add_class("muted")
        b.pack_start(rt,False,False,0); b.pack_start(t,False,False,0); b.pack_start(sub,False,False,0)
        self.pack_start(b,True,True,0)

class SplashWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.set_decorated(False); self.set_position(Gtk.WindowPosition.CENTER); self.set_default_size(470,430)
        box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8); box.set_border_width(18); box.get_style_context().add_class("hero-card"); self.add(box)
        box.pack_start(KishaRoleImage("digital",260,300),True,True,0)
        t=Gtk.Label(label="SUPERIOR MI LABS / COMFYUI"); t.set_name("brand-title"); box.pack_start(t,False,False,0)
        self.status=Gtk.Label(label="Kisha is scanning the local runtime…"); self.status.get_style_context().add_class("muted"); box.pack_start(self.status,False,False,0)
        sp=Gtk.Spinner(); sp.start(); box.pack_start(sp,False,False,4)
        self.show_all()

class RecoveryWindow(Gtk.ApplicationWindow):
    """Minimal window that stays usable even if a feature page fails during startup."""
    def __init__(self, app, error_text):
        super().__init__(application=app)
        self.set_title(APP_NAME + " - Recovery Mode")
        self.set_default_size(760, 520)
        self.set_position(Gtk.WindowPosition.CENTER)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        outer.set_border_width(16)
        self.add(outer)

        title = Gtk.Label(label="Superior MI Labs Workstation entered Recovery Mode", xalign=0)
        title.get_style_context().add_class("status-title")
        outer.pack_start(title, False, False, 0)

        note = Gtk.Label(
            label=(
                "The main interface hit a startup error. Your ComfyUI installation, models, "
                "characters, presets, and outputs were not modified by this recovery screen."
            ),
            xalign=0,
        )
        note.set_line_wrap(True)
        outer.pack_start(note, False, False, 0)

        view = Gtk.TextView()
        view.set_editable(False)
        view.set_cursor_visible(False)
        view.set_monospace(True)
        view.get_buffer().set_text(str(error_text))
        sc = Gtk.ScrolledWindow()
        sc.add(view)
        outer.pack_start(sc, True, True, 0)

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        crash = Gtk.Button(label="Open Crash Folder")
        crash.connect("clicked", lambda *_: platform_support.open_target(CACHE_DIR))
        safe = Gtk.Button(label="Restart in Safe Mode")
        safe.connect("clicked", self._restart_safe)
        quitb = Gtk.Button(label="Quit")
        quitb.connect("clicked", lambda *_: app.quit())
        buttons.pack_start(crash, False, False, 0)
        buttons.pack_start(safe, False, False, 0)
        buttons.pack_end(quitb, False, False, 0)
        outer.pack_start(buttons, False, False, 0)
        self.show_all()

    def _restart_safe(self, *_):
        launcher = shutil.which("smi-comfyui")
        if launcher:
            subprocess.Popen([launcher, "--safe"], start_new_session=True)
        self.get_application().quit()

class Metric(Gtk.Box):
    def __init__(self, title):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.set_hexpand(True)
        self.get_style_context().add_class("card")
        t = Gtk.Label(label=title, xalign=0)
        t.get_style_context().add_class("muted")
        self.value = Gtk.Label(label="—", xalign=0)
        self.value.get_style_context().add_class("metric-value")
        self.bar = Gtk.ProgressBar()
        self.bar.set_show_text(False)
        self.pack_start(t, False, False, 0)
        self.pack_start(self.value, False, False, 0)
        self.pack_start(self.bar, False, False, 2)

class AppWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.cfg = ensure_config()
        self.busy = False
        self.last_state = None
        self.last_status = None
        self.log_errors_only = False
        self.active_runs = {}
        self.last_queue = []
        self.characters_cache = []
        self.last_generated_workflow = None
        self.last_generated_workflow_path = None
        startup_guard.stage("window-init", "constructing lightweight shell")
        self.set_title(APP_NAME)
        self.set_default_size(980, 735)
        self.set_position(Gtk.WindowPosition.CENTER)
        try:
            self.set_icon_from_file(str(role_assets.app_icon_path()))
        except Exception:
            self.set_icon_name("superior-mi-comfyui")
        startup_guard.stage("window-build", "building primary UI")
        self._build()
        self.show_all()
        startup_guard.complete()
        self.refresh(full=False)
        GLib.timeout_add_seconds(max(1, int(self.cfg["refresh_seconds"])), self.refresh)
        if not SAFE_MODE:
            # Heavy initialization happens after the window is already visible.
            GLib.idle_add(self._safe_idle, self._post_window_init, "post-window initialization")

    def _post_window_init(self):
        startup_guard.stage("post-init", "seeding characters and starting background monitors")
        try:
            character_library.seed_bundled_characters(overwrite=False)
        except Exception:
            write_crash(traceback.format_exc(), "character seed")
        try:
            self.refresh(full=True)
        except Exception:
            write_crash(traceback.format_exc(), "full refresh")
        try:
            GLib.timeout_add_seconds(2, self.refresh_queue_monitor)
        except Exception:
            write_crash(traceback.format_exc(), "queue monitor startup")
        try:
            self.refresh_beginner_status()
        except Exception:
            write_crash(traceback.format_exc(), "beginner status")
        if not self.cfg.get("onboarding_complete", False) or not setup_helper.comfy_state().get("complete"):
            GLib.timeout_add(700, self._deferred_setup)
        return False

    def _safe_idle(self, fn, context):
        try:
            fn()
        except Exception:
            write_crash(traceback.format_exc(), context)
        return False

    def _deferred_setup(self):
        try:
            self.show_setup_guide(force=False)
        except Exception:
            write_crash(traceback.format_exc(), "first-run setup")
        return False

    def _failure_page(self, label, exc):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_border_width(18)
        title = Gtk.Label(label=f"{label} could not be loaded", xalign=0)
        title.get_style_context().add_class("status-title")
        msg = Gtk.Label(
            label=(
                "This feature page failed, but the rest of the Workstation can continue. "
                "The error was recorded in the crash log."
            ),
            xalign=0,
        )
        msg.set_line_wrap(True)
        details = Gtk.TextView()
        details.set_editable(False)
        details.set_cursor_visible(False)
        details.set_monospace(True)
        details.get_buffer().set_text(str(exc))
        sc = Gtk.ScrolledWindow()
        sc.set_min_content_height(180)
        sc.add(details)
        box.pack_start(title, False, False, 0)
        box.pack_start(msg, False, False, 0)
        box.pack_start(sc, True, True, 0)
        return box

    def _append_page_safe(self, label, builder):
        try:
            page = builder()
        except Exception as exc:
            write_crash(traceback.format_exc(), f"page build: {label}")
            page = self._failure_page(label, exc)
        self.tabs.append_page(page, Gtk.Label(label=label))

    def _build(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(outer)

        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        top.set_border_width(14)
        top.set_name("topbar")

        brand = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        title = Gtk.Label(label="SUPERIOR MI LABS / COMFYUI", xalign=0)
        title.set_name("brand-title")
        subtitle = Gtk.Label(label="Local media runtime control center • People • Planet • Progress", xalign=0)
        subtitle.set_name("brand-subtitle")
        brand.pack_start(title, False, False, 0)
        brand.pack_start(subtitle, False, False, 0)
        top.pack_start(brand, True, True, 0)

        self.spinner = Gtk.Spinner()
        top.pack_end(self.spinner, False, False, 5)

        self.top_open_ui = Gtk.Button(label="Open ComfyUI")
        self.top_open_ui.connect("clicked", lambda *_: open_url(self.cfg["browser_url"]))
        top.pack_end(self.top_open_ui, False, False, 0)
        self.top_update_btn = Gtk.Button(label="Check Updates")
        self.top_update_btn.connect("clicked", lambda *_: self.check_updates())
        top.pack_end(self.top_update_btn, False, False, 0)
        self.top_runtime_btn = Gtk.Button(label="Start ComfyUI")
        self.top_runtime_btn.connect("clicked", lambda *_: self._top_runtime_action())
        top.pack_end(self.top_runtime_btn, False, False, 0)
        self.top_runtime_label = Gtk.Label(label="ComfyUI: checking…")
        self.top_runtime_label.get_style_context().add_class("muted")
        top.pack_end(self.top_runtime_label, False, False, 3)
        help_btn = Gtk.Button(label="Kisha Help")
        help_btn.connect("clicked", lambda *_: self.show_kisha_help())
        top.pack_end(help_btn, False, False, 0)
        setup_btn = Gtk.Button(label="Setup Guide")
        setup_btn.connect("clicked", lambda *_: self.show_setup_guide(force=True))
        top.pack_end(setup_btn, False, False, 0)
        refresh = Gtk.Button(label="Refresh")
        refresh.connect("clicked", lambda *_: self.refresh(full=True))
        top.pack_end(refresh, False, False, 0)
        outer.pack_start(top, False, False, 0)

        self.tabs = Gtk.Notebook()
        self.tabs.set_scrollable(True)
        outer.pack_start(self.tabs, True, True, 0)
        # Build only the first page at startup. The rest are lazy-loaded when
        # selected so a broken advanced feature cannot make the whole app vanish.
        if SAFE_MODE:
            self._append_page_safe("Runtime", self._dashboard)
            self._append_page_safe("Logs", self._logs)
            self._append_page_safe("Utilities", self._utilities)
            self._append_page_safe("About", self._about)
            return

        self._append_page_safe("Create", self._create)
        self._lazy_pages = {}
        for title, builder in (
            ("Library", self._library),
            ("Activity", self._activity),
            ("Advanced", self._advanced),
            ("Help", self._help_page),
        ):
            shell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            shell.set_border_width(18)
            loading = Gtk.Label(label=f"{title} will load when opened.", xalign=0)
            loading.get_style_context().add_class("muted")
            shell.pack_start(loading, False, False, 0)
            idx = self.tabs.append_page(shell, Gtk.Label(label=title))
            self._lazy_pages[idx] = (shell, builder, title)
        self.tabs.connect("switch-page", self._on_switch_lazy_page)

    def _on_switch_lazy_page(self, notebook, page, page_num):
        item = getattr(self, "_lazy_pages", {}).pop(page_num, None)
        if not item:
            return
        shell, builder, title = item
        startup_guard.stage("lazy-page", title)
        try:
            built = builder()
        except Exception as exc:
            write_crash(traceback.format_exc(), f"lazy page: {title}")
            built = self._failure_page(title, exc)
        for child in list(shell.get_children()):
            shell.remove(child)
        shell.pack_start(built, True, True, 0)
        shell.show_all()

    def check_updates(self):
        self.top_update_btn.set_sensitive(False)
        self.top_update_btn.set_label("Checking…")
        def task():
            try:
                return 0, update_manager.check_for_updates()
            except Exception as exc:
                return 1, str(exc)
        def done(result):
            self.top_update_btn.set_sensitive(True)
            self.top_update_btn.set_label("Check Updates")
            rc, value = result
            if rc:
                self.dialog("Update check", value, Gtk.MessageType.INFO)
                return
            info = value
            if not info.available:
                self.dialog(
                    "Workstation is current",
                    f"Installed: {info.current_version}\\nPublished: {info.latest_version}\\nChannel: {info.channel}\\n\\n{info.notes}".strip(),
                )
                return
            d = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.NONE,
                text=f"Workstation {info.latest_version} is available",
            )
            d.format_secondary_text(
                f"Installed: {info.current_version}\\nChannel: {info.channel}\\n\\n{info.notes}\\n\\n"
                "Updates are downloaded only from the Superior-MI-Labs GitHub repository and must pass SHA-256 verification."
            )
            d.add_button("Later", Gtk.ResponseType.CANCEL)
            d.add_button("Open Repository", 20)
            d.add_button("Sync Development Source", 21)
            if info.deb_url and info.deb_sha256:
                d.add_button("Download & Install", Gtk.ResponseType.OK)
            response = d.run()
            d.destroy()
            if response == 20:
                open_url(info.repo_url)
            elif response == 21:
                self._sync_development_source()
            elif response == Gtk.ResponseType.OK:
                self._download_and_install_update(info)
        self.background(task, done, "Checking GitHub for Workstation updates…")

    def _sync_development_source(self):
        self.top_update_btn.set_sensitive(False)
        self.top_update_btn.set_label("Syncing source…")
        def progress(msg):
            GLib.idle_add(self.top_update_btn.set_label, msg[:28])
        def task():
            try:
                path = update_manager.sync_development_source(progress=progress)
                return 0, str(path)
            except Exception as exc:
                return 1, str(exc)
        def done(result):
            self.top_update_btn.set_sensitive(True)
            self.top_update_btn.set_label("Check Updates")
            if result[0]:
                self.dialog("Development source sync failed", result[1], Gtk.MessageType.ERROR)
                return
            self.dialog(
                "Development source synchronized",
                f"Latest repository source is at:\\n{result[1]}\\n\\n"
                "This does not modify the installed /opt package. Qualified package updates still use the verified .deb path.",
            )
        self.background(task, done, "Syncing development source…")

    def _download_and_install_update(self, info):
        def prog(done, total):
            if total:
                pct=int(done*100/total)
                GLib.idle_add(self.top_update_btn.set_label, f"Downloading {pct}%")
        def task():
            try:
                path=update_manager.download_update(info,prog)
                return 0,str(path)
            except Exception as exc:
                return 1,str(exc)
        def done(result):
            self.top_update_btn.set_label("Check Updates")
            if result[0]:
                self.dialog("Update download failed",result[1],Gtk.MessageType.ERROR)
                return
            path=Path(result[1])
            if self.confirm("Install update?", f"Verified package:\\n{path}\\n\\nAdministrator authorization is required to install it."):
                try:
                    update_manager.install_deb(path)
                except Exception as exc:
                    self.dialog("Could not start installer",str(exc),Gtk.MessageType.ERROR)
        self.background(task,done,"Downloading verified update…")

    def _top_runtime_action(self):
        if self.last_status and self.last_status.pids:
            self.stop_runtime()
        else:
            # Ensure the one-click ComfyUI bridge is present before a fresh start.
            comfy_integration.ensure_bridge()
            self.start_runtime()

    def _lazy_notebook(self, specs, *, attr_name=None, preload_index=0):
        """Create a notebook whose pages are built only when selected.

        Each page owns one shell container for its entire lifetime. Builders
        return a widget exactly once, and that widget is attached only to the
        corresponding shell. This enforces GTK's single-parent invariant.
        """
        notebook = Gtk.Notebook()
        notebook.set_scrollable(True)
        pending = {}

        for title, builder in specs:
            shell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            shell.set_border_width(8)
            label = Gtk.Label(label=f"{title} will load when opened.", xalign=0)
            label.get_style_context().add_class("muted")
            shell.pack_start(label, False, False, 0)
            idx = notebook.append_page(shell, Gtk.Label(label=title))
            pending[idx] = (shell, builder, title)

        def load_page(page_num):
            item = pending.pop(page_num, None)
            if not item:
                return False
            shell, builder, title = item
            startup_guard.stage("lazy-subpage", title)
            try:
                built = builder()
            except Exception as exc:
                write_crash(traceback.format_exc(), f"lazy subpage: {title}")
                built = self._failure_page(title, exc)
            for child in list(shell.get_children()):
                shell.remove(child)
            shell.pack_start(built, True, True, 0)
            shell.show_all()
            return False

        def on_switch(_notebook, _page, page_num):
            load_page(page_num)

        notebook.connect("switch-page", on_switch)
        if attr_name:
            setattr(self, attr_name, notebook)
        GLib.idle_add(load_page, preload_index)
        return notebook

    def _library(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        outer.set_border_width(10)
        outer.pack_start(RoleHeader("explorer", "Library", "Blueprints describe how to create. Packs provide the models they need. Characters provide reusable identity inputs. They are one system."), False, False, 0)
        notebook = self._lazy_notebook(
            (
                ("Blueprints", self._presets),
                ("Starter Packs", self._starter_packs),
                ("Characters", self._characters),
                ("Components", self._picks),
            ),
            attr_name="library_tabs",
            preload_index=0,
        )
        outer.pack_start(notebook, True, True, 0)
        return outer

    def _activity(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        outer.set_border_width(10)
        outer.pack_start(RoleHeader("analyst", "Activity", "Current work, measured performance, and finished outputs in one place."), False, False, 0)
        nb = self._lazy_notebook(
            (
                ("Jobs + Benchmarks", self._queue_benchmarks),
                ("Outputs", self._gallery),
            ),
            preload_index=0,
        )
        outer.pack_start(nb, True, True, 0)
        return outer

    def _advanced(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        outer.set_border_width(10)
        outer.pack_start(RoleHeader("researcher", "Advanced", "Technical runtime, model inventory, diagnostics, logs, and settings. Most users do not need this area for ordinary creation."), False, False, 0)
        nb = self._lazy_notebook(
            (
                ("Runtime", self._dashboard),
                ("Models", self._models),
                ("Logs", self._logs),
                ("Diagnostics", self._utilities),
                ("Settings", self._settings),
            ),
            preload_index=0,
        )
        outer.pack_start(nb, True, True, 0)
        return outer

    def _help_page(self):
        sc = Gtk.ScrolledWindow()
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        page.set_border_width(18)
        sc.add(page)
        page.pack_start(RoleHeader("reflection", "Help", "Kisha explains the beginner path first. Technical details stay available when you need them."), False, False, 0)
        updates = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        updates.get_style_context().add_class("card")
        check = Gtk.Button(label="Check for Updates")
        check.get_style_context().add_class("suggested-action")
        check.connect("clicked", lambda *_: self.check_updates())
        repo = Gtk.Button(label="Open GitHub Repository")
        repo.connect("clicked", lambda *_: open_url("https://github.com/Superior-MI-Labs/Superior-MI-ComfyUI-Workstation"))
        updates.pack_start(check, False, False, 0)
        updates.pack_start(repo, False, False, 0)
        page.pack_start(updates, False, False, 0)
        topics = [
            ("First 10 minutes", "1. Install a Starter Pack in Library.  2. Start ComfyUI.  3. Go to Create.  4. Pick Image, Character Image, or Video from Image.  5. Press Generate. The output and progress stay visible in Create."),
            ("Blueprints vs Packs", "A Blueprint is a creation recipe. A Pack is the set of models/components required to run it. Installing a Pack makes several Blueprints ready at once."),
            ("Characters", "Characters are image references stored under ~/Models/Media/Characters. Superior MI examples live under the Superior-MI-Labs folder. Create your own folders and drop images inside; the Workstation discovers them recursively."),
            ("Open in ComfyUI", "Blueprints and generated creations are imported into ComfyUI's workflow library automatically. With the bundled bridge active, the selected workflow also opens directly in the graph."),
            ("Video", "Wan2.2 5B is exposed as Image → Video in the beginner UI because a real source image makes the input contract explicit. Generate or choose a still first, then animate it."),
        ]
        for title, body in topics:
            exp = Gtk.Expander(label=title)
            lab = Gtk.Label(label=body, xalign=0)
            lab.set_line_wrap(True)
            lab.set_margin_top(8); lab.set_margin_bottom(8); lab.set_margin_start(12); lab.set_margin_end(12)
            exp.add(lab)
            page.pack_start(exp, False, False, 0)
        page.pack_start(self._about(), False, False, 0)
        return sc

    def _dashboard(self):
        sc = Gtk.ScrolledWindow()
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        page.set_border_width(18)
        sc.add(page)

        hero = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        hero.set_border_width(14)
        hero.get_style_context().add_class("hero-card")
        self.orb = KishaOrb()
        hero.pack_start(KishaRoleImage("digital",105,135), False, False, 0)
        hero.pack_start(self.orb, False, False, 0)

        htext = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        k = Gtk.Label(label="KISHA / RUNTIME SENTINEL", xalign=0)
        k.get_style_context().add_class("kisha-label")
        self.status_title = Gtk.Label(label="Checking runtime…", xalign=0)
        self.status_title.get_style_context().add_class("status-title")
        self.status_detail = Gtk.Label(label="", xalign=0)
        self.status_detail.set_line_wrap(True)
        self.status_detail.get_style_context().add_class("muted")
        self.cmdline_label = Gtk.Label(label="", xalign=0)
        self.cmdline_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.cmdline_label.get_style_context().add_class("muted")
        htext.pack_start(k, False, False, 0)
        htext.pack_start(self.status_title, False, False, 0)
        htext.pack_start(self.status_detail, False, False, 0)
        htext.pack_start(self.cmdline_label, False, False, 0)
        hero.pack_start(htext, True, True, 0)
        page.pack_start(hero, False, False, 0)

        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.start_btn = Gtk.Button(label="Start ComfyUI")
        self.start_btn.get_style_context().add_class("suggested-action")
        self.start_btn.connect("clicked", lambda *_: self.start_runtime())
        self.stop_btn = Gtk.Button(label="Stop")
        self.stop_btn.connect("clicked", lambda *_: self.stop_runtime())
        self.restart_btn = Gtk.Button(label="Restart")
        self.restart_btn.connect("clicked", lambda *_: self.restart_runtime())
        self.open_btn = Gtk.Button(label="Open UI")
        self.open_btn.connect("clicked", lambda *_: open_url(self.cfg["browser_url"]))
        for b in (self.start_btn, self.stop_btn, self.restart_btn, self.open_btn):
            controls.pack_start(b, False, False, 0)
        page.pack_start(controls, False, False, 0)

        metrics = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.gpu = Metric("GPU VRAM")
        self.ram = Metric("System RAM")
        self.disk = Metric("NVMe free")
        metrics.pack_start(self.gpu, True, True, 0)
        metrics.pack_start(self.ram, True, True, 0)
        metrics.pack_start(self.disk, True, True, 0)
        page.pack_start(metrics, False, False, 0)

        beginner = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        beginner.get_style_context().add_class("card")
        bt = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        bl = Gtk.Label(label="NEW HERE?", xalign=0); bl.get_style_context().add_class("kisha-label")
        self.beginner_status = Gtk.Label(label="Checking setup…", xalign=0); self.beginner_status.set_line_wrap(True)
        bt.pack_start(bl, False, False, 0); bt.pack_start(self.beginner_status, False, False, 0)
        beginner.pack_start(bt, True, True, 0)
        bguide = Gtk.Button(label="Guided Setup")
        bguide.get_style_context().add_class("suggested-action")
        bguide.connect("clicked", lambda *_: self.show_setup_guide(force=True))
        beginner.pack_end(bguide, False, False, 0)
        page.pack_start(beginner, False, False, 0)

        create = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        create.get_style_context().add_class("card")
        ct = Gtk.Label(label="WHAT DO YOU WANT TO MAKE?", xalign=0); ct.get_style_context().add_class("section-title")
        create.pack_start(ct, False, False, 0)
        crow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        for label, cat in (("Make an Image", "Image"), ("Make a Video", "Video"), ("Phone / Vertical", "Mobile"), ("Use Reference Images", "Character"), ("Anime / Cartoon / Anthro", "Style")):
            b = Gtk.Button(label=label)
            b.connect("clicked", lambda _b, c=cat: self._home_create_action(c))
            crow.pack_start(b, True, True, 0)
        create.pack_start(crow, False, False, 0)
        page.pack_start(create, False, False, 0)

        quick = Gtk.Grid()
        quick.set_column_spacing(8)
        quick.set_row_spacing(8)
        quick.get_style_context().add_class("card")
        buttons = [
            ("Models", MODEL_ROOT),
            ("Presets", PRESET_ROOT),
            ("Outputs", OUTPUT_ROOT),
            ("Inputs", INPUT_ROOT),
            ("Logs", LOG_ROOT),
            ("ComfyUI Folder", COMFY),
        ]
        for i, (label, path) in enumerate(buttons):
            b = Gtk.Button(label=label)
            b.connect("clicked", lambda _b, p=path: open_path(p))
            quick.attach(b, i % 3, i // 3, 1, 1)
        page.pack_start(quick, False, False, 0)

        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        info.get_style_context().add_class("card")
        self.build_label = Gtk.Label(label="", xalign=0)
        self.inventory_label = Gtk.Label(label="Model inventory: scan on Refresh", xalign=0)
        self.inventory_label.get_style_context().add_class("muted")
        info.pack_start(self.build_label, False, False, 0)
        info.pack_start(self.inventory_label, False, False, 0)
        page.pack_start(info, False, False, 0)
        return sc

    def _home_create_action(self, category):
        if category in ("Image","Mobile","Character","Video"):
            self.tabs.set_current_page(0)
            # Match the nearest beginner creation method.
            preferred = {
                "Image":"Text Image (FLUX.2 Klein 4B)",
                "Character":"Character Image (Qwen Image 2.1)",
                "Video":"Video from Image (Wan2.2 TI2V 5B)",
                "Mobile":"Text Image (Qwen Image 2.1)",
            }.get(category)
            if preferred and hasattr(self,"create_mode"):
                modes=list(creation_helper.installed_modes())
                if preferred in modes:
                    self.create_mode.set_active(modes.index(preferred))
            if category=="Mobile" and hasattr(self,"create_orientation"):
                self.create_orientation.set_active(1)
        else:
            self.open_preset_category("Style")

    def refresh_beginner_status(self):
        try:
            gpu = setup_helper.detect_gpu()
            cs = setup_helper.comfy_state()
            free = setup_helper.disk_free_gib()
            if cs.get("complete"):
                txt = f"ComfyUI is installed. {gpu.get('name','GPU')} • {gpu.get('vram_gib',0):.1f} GiB VRAM • {free:.0f} GiB disk free. Start with Library → Starter Packs, then use Create."
            elif cs.get("repo") or cs.get("main"):
                txt = f"ComfyUI looks partially installed. Guided Setup can finish or repair the environment. {gpu.get('name','GPU')} • {free:.0f} GiB free."
            else:
                txt = f"ComfyUI is not installed in the expected location yet. Guided Setup can install it for NVIDIA Linux systems. {gpu.get('name','GPU')} • {free:.0f} GiB free."
            if hasattr(self, "beginner_status"):
                self.beginner_status.set_text(txt)
        except Exception as e:
            if hasattr(self, "beginner_status"):
                self.beginner_status.set_text(f"Setup scan could not complete: {e}")
        return False

    def show_setup_guide(self, force=True):
        if not force and self.cfg.get("onboarding_complete", False) and setup_helper.comfy_state().get("complete"):
            return
        d = Gtk.Dialog(title="Kisha Guided Setup", transient_for=self, flags=0)
        d.add_button("Close", Gtk.ResponseType.CLOSE)
        d.set_default_size(780, 650)
        box = d.get_content_area()
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        outer.set_border_width(16)
        box.pack_start(outer, True, True, 0)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        header.pack_start(KishaRoleImage("digital", 150, 150), False, False, 0)
        htxt = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        t = Gtk.Label(label="KISHA / FIRST-RUN GUIDE", xalign=0); t.get_style_context().add_class("kisha-label")
        sub = Gtk.Label(label="You do not need to know Python, CUDA, model folders, or node graphs to get started. This guide checks the computer first, then only offers actions that fit the detected system.", xalign=0)
        sub.set_line_wrap(True)
        htxt.pack_start(t, False, False, 0); htxt.pack_start(sub, False, False, 0)
        header.pack_start(htxt, True, True, 0)
        outer.pack_start(header, False, False, 0)

        status_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        status_box.get_style_context().add_class("card")
        hardware = Gtk.Label(label="Scanning hardware…", xalign=0); hardware.set_line_wrap(True)
        comfy = Gtk.Label(label="Checking ComfyUI…", xalign=0); comfy.set_line_wrap(True)
        storage = Gtk.Label(label="Checking storage…", xalign=0)
        status_box.pack_start(hardware, False, False, 0)
        status_box.pack_start(comfy, False, False, 0)
        status_box.pack_start(storage, False, False, 0)
        outer.pack_start(status_box, False, False, 0)

        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        install = Gtk.Button(label="Install / Finish ComfyUI")
        install.get_style_context().add_class("suggested-action")
        repair = Gtk.Button(label="Repair Launchers")
        start = Gtk.Button(label="Start ComfyUI")
        openui = Gtk.Button(label="Open ComfyUI")
        picks = Gtk.Button(label="Choose Starter Packs")
        presets = Gtk.Button(label="Browse Blueprints")
        for b in (install, repair, start, openui, picks, presets): actions.pack_start(b, False, False, 0)
        outer.pack_start(actions, False, False, 0)

        starter = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        starter_label = Gtk.Label(label="Beginner picks:", xalign=0)
        starter_label.get_style_context().add_class("kisha-label")
        starter.pack_start(starter_label, False, False, 0)
        starter_image = Gtk.Button(label="Image Starter Pack")
        starter_image.connect("clicked", lambda *_: (d.response(Gtk.ResponseType.CLOSE), self.open_pack_by_id("starter-image")))
        starter_video = Gtk.Button(label="Video Starter Pack")
        starter_video.connect("clicked", lambda *_: (d.response(Gtk.ResponseType.CLOSE), self.open_pack_by_id("starter-video")))
        starter.pack_start(starter_image, False, False, 0)
        starter.pack_start(starter_video, False, False, 0)
        outer.pack_start(starter, False, False, 0)

        tip = Gtk.Label(label="Recommended beginner path: 1) install ComfyUI, 2) install one Starter Pack, 3) start ComfyUI, 4) use Create. Blueprints and generated setups can be imported into ComfyUI automatically; drag-and-drop is optional.", xalign=0)
        tip.set_line_wrap(True); tip.get_style_context().add_class("muted")
        outer.pack_start(tip, False, False, 0)

        progress_sc = Gtk.ScrolledWindow(); progress_sc.set_min_content_height(220)
        progress_view = Gtk.TextView(); progress_view.set_editable(False); progress_view.set_cursor_visible(False); progress_view.set_monospace(True); progress_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        progress_sc.add(progress_view); outer.pack_start(progress_sc, True, True, 0)
        progress_buf = progress_view.get_buffer()
        progress_buf.set_text("Kisha is ready. No changes have been made yet.\n")

        finish = Gtk.CheckButton(label="I understand where ComfyUI, models, Blueprints, characters, and outputs live. Do not show this automatically next time.")
        finish.set_active(bool(self.cfg.get("onboarding_complete", False)))
        outer.pack_start(finish, False, False, 0)

        def append(msg):
            end = progress_buf.get_end_iter(); progress_buf.insert(end, str(msg) + "\n")
            mark = progress_buf.create_mark(None, progress_buf.get_end_iter(), False)
            progress_view.scroll_to_mark(mark, 0.05, True, 0, 1)
            return False

        def update_state():
            gpu = setup_helper.detect_gpu(); cs = setup_helper.comfy_state(); free = setup_helper.disk_free_gib()
            hardware.set_text(f"Hardware: {gpu.get('vendor')} • {gpu.get('name')} • {gpu.get('vram_gib',0):.1f} GiB VRAM • driver {gpu.get('driver')} • reported CUDA {gpu.get('cuda_reported')}")
            storage.set_text(f"Storage: {free:.1f} GiB free in your home filesystem")
            if cs.get('complete'):
                comfy.set_text(f"ComfyUI: READY at {COMFY}")
            elif cs.get('repo') or cs.get('main'):
                comfy.set_text(f"ComfyUI: PARTIAL at {COMFY}. The guide can finish the Python environment.")
            else:
                comfy.set_text(f"ComfyUI: NOT INSTALLED at {COMFY}")
            install.set_sensitive(bool(gpu.get('nvidia_ok')) and not cs.get('complete'))
            repair.set_sensitive(bool(cs.get('complete')))
            start.set_sensitive(bool(cs.get('complete')))
            openui.set_sensitive(bool(cs.get('complete')))
            return gpu, cs

        def install_clicked(*_):
            gpu, cs = update_state()
            if not gpu.get('nvidia_ok'):
                self.dialog("Guided installer unavailable", "The built-in installer currently targets NVIDIA Linux systems. Open the official ComfyUI installation guide for AMD, Intel, Apple, or CPU setups.", Gtk.MessageType.WARNING)
                return
            if setup_helper.disk_free_gib() < 20:
                self.dialog("Low disk space", "Less than 20 GiB is free. ComfyUI plus PyTorch and models can require much more. Free some space before continuing.", Gtk.MessageType.WARNING)
                return
            if not self.confirm("Install ComfyUI?", "This will clone the official Comfy-Org/ComfyUI repository into ~/Projects/AI-Runtimes/ComfyUI, create its own .venv, install NVIDIA PyTorch using the current official cu130 path, install ComfyUI requirements, and create the Workstation start/stop helpers. Existing ComfyUI source revisions are not silently updated."):
                return
            for b in (install, repair, start, picks, presets): b.set_sensitive(False)
            progress_buf.set_text("")
            def worker():
                try:
                    result = setup_helper.install_comfyui_nvidia(progress=lambda m: GLib.idle_add(append, m))
                    GLib.idle_add(append, result)
                    GLib.idle_add(done_install, True, "")
                except Exception as e:
                    GLib.idle_add(done_install, False, str(e))
            threading.Thread(target=worker, daemon=True).start()

        def done_install(ok, error):
            if not ok:
                append("ERROR: " + error)
                self.dialog("ComfyUI setup did not finish", error, Gtk.MessageType.ERROR)
            else:
                notify("ComfyUI setup complete", "You can now install a Starter Pack and create.")
            update_state(); self.refresh_beginner_status(); self.refresh(full=True)
            picks.set_sensitive(True); presets.set_sensitive(True)
            return False

        def repair_clicked(*_):
            try:
                append(setup_helper.repair_launchers()); update_state(); self.refresh_beginner_status()
            except Exception as e:
                self.dialog("Launcher repair failed", str(e), Gtk.MessageType.ERROR)

        def start_clicked(*_):
            self.start_runtime(); append("Start request sent. The top status will change from starting to running when ComfyUI is ready.")

        def picks_clicked(*_):
            self.tabs.set_current_page(1)
            if hasattr(self, "library_tabs"):
                self.library_tabs.set_current_page(1)
            d.response(Gtk.ResponseType.CLOSE)

        def presets_clicked(*_):
            self.tabs.set_current_page(1)
            if hasattr(self, "library_tabs"):
                self.library_tabs.set_current_page(0)
            d.response(Gtk.ResponseType.CLOSE)

        install.connect("clicked", install_clicked)
        repair.connect("clicked", repair_clicked)
        start.connect("clicked", start_clicked)
        openui.connect("clicked", lambda *_: open_url(self.cfg['browser_url']))
        picks.connect("clicked", picks_clicked)
        presets.connect("clicked", presets_clicked)
        update_state()
        d.show_all()
        d.run()
        self.cfg["onboarding_complete"] = bool(finish.get_active())
        save_config(self.cfg)
        d.destroy()
        self.refresh_beginner_status()

    def _create(self):
        sc = Gtk.ScrolledWindow()
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        page.set_border_width(16)
        sc.add(page)
        page.pack_start(RoleHeader("everyday", "Create", "A simple creation surface over the same ComfyUI graphs. Pick the result you want; model details stay in Library and Advanced."), False, False, 0)

        status = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        status.get_style_context().add_class("card")
        self.create_status = Gtk.Label(label="Scanning installed creation packs…", xalign=0)
        self.create_status.set_line_wrap(True)
        status.pack_start(self.create_status, True, True, 0)
        packs = Gtk.Button(label="Get Starter Packs")
        packs.connect("clicked", lambda *_: self.open_library_section(1))
        status.pack_end(packs, False, False, 0)
        page.pack_start(status, False, False, 0)

        # Basic creation controls.
        grid = Gtk.Grid()
        grid.set_row_spacing(10); grid.set_column_spacing(12)
        grid.get_style_context().add_class("card")
        self.create_mode = Gtk.ComboBoxText()
        self.create_mode.connect("changed", lambda *_: self.create_mode_changed())

        self.create_character = Gtk.ComboBoxText()
        self.create_source_entry = Gtk.Entry()
        self.create_source_entry.set_editable(False)
        self.create_source_entry.set_placeholder_text("Choose an image to animate")
        choose_source = Gtk.Button(label="Choose Image…")
        choose_source.connect("clicked", lambda *_: self.choose_create_source())
        latest_source = Gtk.Button(label="Use Latest Output")
        latest_source.connect("clicked", lambda *_: self.use_latest_output_as_source())
        source_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        source_row.pack_start(self.create_source_entry, True, True, 0)
        source_row.pack_start(choose_source, False, False, 0)
        source_row.pack_start(latest_source, False, False, 0)
        self.create_source_row = source_row

        self.create_orientation = Gtk.ComboBoxText()
        for x in ("Square", "Phone Portrait", "Landscape"):
            self.create_orientation.append_text(x)
        self.create_orientation.set_active(0)
        self.create_quality = Gtk.ComboBoxText()
        for x in ("Fast", "Normal", "Quality"):
            self.create_quality.append_text(x)
        self.create_quality.set_active(1)

        rows = [
            ("mode", "Create", self.create_mode),
            ("character", "Character", self.create_character),
            ("source_image", "Source image", source_row),
            ("format", "Format", self.create_orientation),
            ("quality", "Quality", self.create_quality),
        ]
        self.create_rows = {}
        for i, (key, label, widget) in enumerate(rows):
            lab = Gtk.Label(label=label, xalign=0)
            grid.attach(lab, 0, i, 1, 1)
            grid.attach(widget, 1, i, 1, 1)
            self.create_rows[key] = (lab, widget)

        self.create_contract = Gtk.Label(label="", xalign=0)
        self.create_contract.set_line_wrap(True)
        self.create_contract.get_style_context().add_class("muted")
        grid.attach(self.create_contract, 0, len(rows), 2, 1)
        page.pack_start(grid, False, False, 0)

        prompt_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7)
        prompt_card.get_style_context().add_class("card")
        lab = Gtk.Label(label="Describe what you want", xalign=0); lab.get_style_context().add_class("section-title")
        prompt_card.pack_start(lab, False, False, 0)
        self.create_prompt = Gtk.TextView()
        self.create_prompt.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.create_prompt.set_size_request(-1, 115)
        self.create_prompt.get_buffer().set_text("A cinematic northern Michigan scene with natural posture, detailed Superior MI apparel, and clean professional lighting.")
        prompt_card.pack_start(self.create_prompt, False, False, 0)
        page.pack_start(prompt_card, False, False, 0)

        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.create_queue_btn = Gtk.Button(label="Generate")
        self.create_queue_btn.get_style_context().add_class("suggested-action")
        self.create_queue_btn.connect("clicked", lambda *_: self.create_quick_workflow(queue_now=True))
        self.create_workflow_btn = Gtk.Button(label="Open Setup in ComfyUI")
        self.create_workflow_btn.connect("clicked", lambda *_: self.create_quick_workflow(queue_now=False))
        library = Gtk.Button(label="Choose Blueprint")
        library.connect("clicked", lambda *_: self.open_library_section(0))
        actions.pack_start(self.create_queue_btn, False, False, 0)
        actions.pack_start(self.create_workflow_btn, False, False, 0)
        actions.pack_start(library, False, False, 0)
        page.pack_start(actions, False, False, 0)

        # Unified run/result surface.
        result = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        result.get_style_context().add_class("hero-card")
        result.set_border_width(12)
        h = Gtk.Label(label="CREATION STATUS", xalign=0); h.get_style_context().add_class("kisha-label")
        result.pack_start(h, False, False, 0)
        self.create_stage = Gtk.Label(label="Ready", xalign=0)
        self.create_stage.get_style_context().add_class("section-title")
        self.create_detail = Gtk.Label(label="Nothing is running.", xalign=0)
        self.create_detail.set_line_wrap(True)
        self.create_detail.get_style_context().add_class("muted")
        self.create_progress = Gtk.ProgressBar()
        self.create_progress.set_show_text(True)
        result.pack_start(self.create_stage, False, False, 0)
        result.pack_start(self.create_detail, False, False, 0)
        result.pack_start(self.create_progress, False, False, 0)

        self.create_preview = Gtk.Image()
        self.create_preview.set_size_request(340, 220)
        result.pack_start(self.create_preview, False, False, 4)
        outrow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.create_open_output = Gtk.Button(label="Open Output")
        self.create_open_output.set_sensitive(False)
        self.create_open_output.connect("clicked", lambda *_: self.open_last_create_output())
        open_activity = Gtk.Button(label="All Outputs")
        open_activity.connect("clicked", lambda *_: self.tabs.set_current_page(2))
        outrow.pack_start(self.create_open_output, False, False, 0)
        outrow.pack_start(open_activity, False, False, 0)
        result.pack_start(outrow, False, False, 0)
        page.pack_start(result, False, False, 0)

        self.create_result = Gtk.Label(label="", xalign=0)
        self.create_result.set_line_wrap(True)
        self.create_result.set_selectable(True)
        self.create_result.get_style_context().add_class("muted")
        page.pack_start(self.create_result, False, False, 0)

        self.create_source_path = ""
        self.last_create_output = ""
        self.create_running = False
        GLib.idle_add(self.refresh_create_panel)
        return sc

    def refresh_create_panel(self):
        modes = creation_helper.installed_modes()
        self.characters_cache = character_library.scan_characters()
        current_mode = self._normalized_create_mode() if hasattr(self, "create_mode") else None
        self.create_mode.remove_all()
        keys = list(modes)
        for mode, ready in modes.items():
            label = mode if ready else f"{mode}  [install pack]"
            self.create_mode.append_text(label)
        idx = keys.index(current_mode) if current_mode in keys else 0
        if keys:
            self.create_mode.set_active(idx)

        self.create_character.remove_all()
        for c in self.characters_cache:
            collection = c.collection or "Custom"
            self.create_character.append(c.uid, f"{c.name}  •  {collection}")
        if self.characters_cache:
            self.create_character.set_active(0)

        ready_count = sum(1 for v in modes.values() if v)
        runtime = "running" if self.last_status and self.last_status.http else "stopped"
        self.create_status.set_text(
            f"{ready_count}/{len(modes)} creation methods ready • {len(self.characters_cache)} characters • ComfyUI {runtime}"
        )
        self.create_mode_changed()
        return False

    def _normalized_create_mode(self):
        text = self.create_mode.get_active_text() or ""
        return text.replace("  [install pack]", "").replace("  [models missing]", "")

    def _set_create_row_visible(self, key, visible):
        row = getattr(self, "create_rows", {}).get(key)
        if not row:
            return
        for widget in row:
            widget.set_visible(bool(visible))

    def create_mode_changed(self):
        if not hasattr(self, "create_character"):
            return
        mode = self._normalized_create_mode()
        if mode not in creation_helper.MODES:
            return

        caps = creation_helper.mode_capabilities(mode)
        needs_character = bool(caps["character"])
        needs_source = bool(caps["source_image"])

        # The simple Create surface mirrors the selected Blueprint. Controls
        # that the graph cannot consume are not shown at all.
        self._set_create_row_visible("character", needs_character)
        self._set_create_row_visible("source_image", needs_source)
        self._set_create_row_visible("format", bool(caps["format"]))
        self._set_create_row_visible("quality", bool(caps["quality"]))

        semantic = ["Prompt"]
        if needs_character:
            semantic.append(f"Character reference ({caps['reference_slots']} slot{'s' if caps['reference_slots'] != 1 else ''})")
        if needs_source:
            semantic.append("Source image")
        if caps["format"]:
            semantic.append("Output format")
        if caps["quality"]:
            semantic.append("Quality")
        self.create_contract.set_text("This setup uses: " + " • ".join(semantic))

        ready = creation_helper.installed_modes().get(mode, False)
        has_inputs = (
            (not needs_character or bool(self.characters_cache))
            and (not needs_source or bool(self.create_source_path))
        )
        self.create_workflow_btn.set_sensitive(ready and has_inputs and not self.create_running)
        running = bool(self.last_status and self.last_status.http)
        self.create_queue_btn.set_sensitive(ready and running and has_inputs and not self.create_running)

    def _create_prompt_text(self):
        buf = self.create_prompt.get_buffer()
        return buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True).strip()

    def _active_character(self):
        uid = self.create_character.get_active_id()
        if not uid:
            return None
        return character_library.find_character(uid, self.characters_cache)

    def choose_create_source(self):
        d = Gtk.FileChooserDialog(
            title="Choose source image",
            parent=self,
            action=Gtk.FileChooserAction.OPEN,
        )
        d.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
        f = Gtk.FileFilter(); f.set_name("Images")
        for pat in ("*.png","*.jpg","*.jpeg","*.webp"):
            f.add_pattern(pat)
        d.add_filter(f)
        if d.run() == Gtk.ResponseType.OK:
            self.create_source_path = d.get_filename() or ""
            self.create_source_entry.set_text(self.create_source_path)
        d.destroy()
        self.create_mode_changed()

    def use_latest_output_as_source(self):
        if self.last_create_output and Path(self.last_create_output).suffix.lower() in (".png",".jpg",".jpeg",".webp"):
            self.create_source_path = self.last_create_output
            self.create_source_entry.set_text(self.create_source_path)
            self.create_mode_changed()
            return
        rows = gallery_helper.scan(limit=30)
        image = next((r for r in rows if r.get("type")=="Image"), None)
        if image:
            self.create_source_path = image["path"]
            self.create_source_entry.set_text(self.create_source_path)
            self.create_mode_changed()
        else:
            self.dialog("No image output yet", "Generate an image first or choose a source image.", Gtk.MessageType.INFO)

    def _build_current_create_workflow(self):
        mode = self._normalized_create_mode()
        prompt = self._create_prompt_text()
        orientation = self.create_orientation.get_active_text() or "Square"
        quality = self.create_quality.get_active_text() or "Normal"
        caps = creation_helper.mode_capabilities(mode)
        character = self._active_character() if caps.get("character") else None
        source = self.create_source_path if caps.get("source_image") else None
        return mode, creation_helper.build_workflow(mode, prompt, orientation, quality, character, source_image=source), character

    def _workflow_label(self, mode, character=None):
        quality = self.create_quality.get_active_text() or "Normal"
        orientation = self.create_orientation.get_active_text() or "Square"
        return f"{character.name if character else mode}_{quality}_{orientation}_{datetime.now():%H%M%S}"

    def create_quick_workflow(self, queue_now=False):
        try:
            mode, workflow, character = self._build_current_create_workflow()
            label = self._workflow_label(mode, character)

            if not (self.last_status and self.last_status.http):
                raise RuntimeError("Start ComfyUI first so the Workstation can validate this setup against your local node contracts.")

            # Reconcile the Blueprint with the exact /object_info contract of the
            # running ComfyUI before saving or queueing. This catches node API
            # drift before it reaches execute().
            workflow, _runtime_info = comfy_integration.prepare_api_prompt(
                self.cfg["browser_url"], workflow
            )

            path = creation_helper.save_workflow(workflow, label)
            self.last_generated_workflow = workflow
            self.last_generated_workflow_path = path

            if not queue_now:
                self.open_api_workflow_in_comfy(workflow, label)
                self.create_result.set_text(f"Opened in ComfyUI and saved to its workflow library.\nLocal technical copy: {path}")
                return

            # Every Creation is also a saved ComfyUI workflow, so Create and Library never diverge.
            comfy_integration.import_api_workflow(
                self.cfg["browser_url"], workflow, label, folder="Superior MI/Creations", open_now=False
            )
            self._start_create_generation(workflow, label)
        except Exception as exc:
            self.create_result.set_text(str(exc))
            self.dialog("Could not create", str(exc), Gtk.MessageType.ERROR)

    def open_api_workflow_in_comfy(self, workflow, label, folder="Superior MI"):
        ok,msg = comfy_integration.ensure_bridge()
        result = comfy_integration.import_api_workflow(self.cfg["browser_url"], workflow, label, folder=folder)
        open_url(self.cfg["browser_url"])
        if not result.get("bridge_active"):
            self.create_result.set_text(
                f"Workflow imported as {result['path']}.\n\n"
                "The Superior MI bridge is installed but is not active in the current ComfyUI process yet. "
                "Restart ComfyUI once; after that Open in ComfyUI will load the graph directly."
            )
        return result

    def _start_create_generation(self, workflow, label):
        if self.create_running:
            return
        self.create_running = True
        self.create_progress.set_fraction(0)
        self.create_progress.set_text("0%")
        self.create_stage.set_text("Queued")
        self.create_detail.set_text("Sending the workflow to ComfyUI…")
        self.create_preview.clear()
        self.create_open_output.set_sensitive(False)
        self.create_result.set_text("")
        self.create_mode_changed()

        def cb(event):
            GLib.idle_add(self._apply_create_progress, event)

        def worker():
            try:
                result = execution_client.queue_and_monitor(workflow, self.cfg["browser_url"], cb)
                GLib.idle_add(self._finish_create_generation, 0, result, label)
            except Exception as exc:
                GLib.idle_add(self._finish_create_generation, 1, {"error":str(exc)}, label)
        threading.Thread(target=worker, daemon=True).start()

    def _apply_create_progress(self, event):
        frac = max(0.0, min(1.0, float(event.get("percent",0) or 0)))
        self.create_progress.set_fraction(frac)
        self.create_progress.set_text(f"{int(frac*100)}%")
        self.create_stage.set_text(str(event.get("stage") or event.get("state") or "Working"))
        elapsed = float(event.get("elapsed",0) or 0)
        detail = str(event.get("detail") or "")
        self.create_detail.set_text(f"{detail}   •   {elapsed:.1f}s elapsed")
        return False

    def _finish_create_generation(self, rc, result, label):
        self.create_running = False
        self.create_mode_changed()
        if rc:
            self.create_stage.set_text("Generation failed")
            self.create_detail.set_text(result.get("error","Unknown error"))
            self.create_result.set_text(result.get("error","Unknown error"))
            return False
        outputs = result.get("outputs",[]) or []
        self.create_progress.set_fraction(1.0); self.create_progress.set_text("100%")
        self.create_stage.set_text("Complete")
        if outputs:
            out = outputs[0].get("path") or ""
            self.last_create_output = out
            self.create_detail.set_text(f"Saved: {out or outputs[0].get('filename','output')}")
            if out and Path(out).exists():
                self._show_create_output(out)
                self.create_open_output.set_sensitive(True)
        else:
            self.create_detail.set_text("ComfyUI completed the workflow. Open Activity → Outputs to inspect saved files.")
        notify("Creation complete", label)
        return False

    def _show_create_output(self, path):
        p = Path(path)
        if p.suffix.lower() in (".png",".jpg",".jpeg",".webp"):
            try:
                pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(p), 620, 340, True)
                self.create_preview.set_from_pixbuf(pix)
            except Exception:
                self.create_preview.set_from_icon_name("image-x-generic", Gtk.IconSize.DIALOG)
        else:
            try:
                preview_dir=CACHE_DIR / "video-previews"
                preview_dir.mkdir(parents=True,exist_ok=True)
                token=hashlib.sha1(str(p).encode("utf-8")).hexdigest()[:12]
                thumb=preview_dir / f"{token}.jpg"
                if not thumb.exists() or thumb.stat().st_mtime < p.stat().st_mtime:
                    subprocess.run(["ffmpeg","-y","-ss","0.2","-i",str(p),"-frames:v","1","-vf","scale=620:-1",str(thumb)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=20,check=False)
                if thumb.exists():
                    pix=GdkPixbuf.Pixbuf.new_from_file_at_scale(str(thumb),620,340,True)
                    self.create_preview.set_from_pixbuf(pix)
                else:
                    self.create_preview.set_from_icon_name("video-x-generic", Gtk.IconSize.DIALOG)
            except Exception:
                self.create_preview.set_from_icon_name("video-x-generic", Gtk.IconSize.DIALOG)

    def open_last_create_output(self):
        if self.last_create_output:
            platform_support.open_target(Path(self.last_create_output))

    def open_library_section(self, index=0):
        self.tabs.set_current_page(1)
        attempts = {"n": 0}
        def later():
            attempts["n"] += 1
            if hasattr(self, "library_tabs"):
                self.library_tabs.set_current_page(index)
                return False
            return attempts["n"] < 50
        GLib.timeout_add(80, later)

    def _characters(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        page.set_border_width(14)
        page.pack_start(RoleHeader("everyday", "Character Library", "Drop an image into the character folder and it becomes a selectable character. Subfolders become categories; optional same-name JSON sidecars add metadata."), False, False, 0)

        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.character_search = Gtk.SearchEntry(); self.character_search.set_placeholder_text("Search name, role, tag…")
        self.character_search.connect("search-changed", lambda *_: self.refresh_characters())
        self.character_kind = Gtk.ComboBoxText(); self.character_kind.append_text("All")
        self.character_kind.set_active(0); self.character_kind.connect("changed", lambda *_: self.refresh_characters())
        self.character_collection = Gtk.ComboBoxText(); self.character_collection.append_text("All collections")
        self.character_collection.set_active(0); self.character_collection.connect("changed", lambda *_: self.refresh_characters())
        refresh = Gtk.Button(label="Refresh"); refresh.connect("clicked", lambda *_: self.refresh_characters(reset_kinds=True))
        imp = Gtk.Button(label="Import Image…"); imp.connect("clicked", lambda *_: self.import_character_image())
        newfolder = Gtk.Button(label="New Folder…"); newfolder.connect("clicked", lambda *_: self.create_character_folder())
        folder = Gtk.Button(label="Open Character Folder"); folder.connect("clicked", lambda *_: open_path(character_library.USER_ROOT))
        bar.pack_start(self.character_search, True, True, 0)
        bar.pack_start(self.character_collection, False, False, 0)
        bar.pack_start(self.character_kind, False, False, 0)
        bar.pack_start(refresh, False, False, 0)
        bar.pack_start(imp, False, False, 0)
        bar.pack_start(newfolder, False, False, 0)
        bar.pack_start(folder, False, False, 0)
        page.pack_start(bar, False, False, 0)

        self.character_summary = Gtk.Label(label="", xalign=0); self.character_summary.get_style_context().add_class("kisha-label")
        page.pack_start(self.character_summary, False, False, 0)

        paned = Gtk.Paned.new(Gtk.Orientation.HORIZONTAL)
        page.pack_start(paned, True, True, 0)
        self.character_store = Gtk.ListStore(GdkPixbuf.Pixbuf, str, str)
        self.character_icons = Gtk.IconView.new()
        self.character_icons.set_model(self.character_store)
        self.character_icons.set_pixbuf_column(0); self.character_icons.set_text_column(1)
        self.character_icons.set_item_width(190); self.character_icons.set_margin(8); self.character_icons.set_spacing(8); self.character_icons.set_row_spacing(12); self.character_icons.set_column_spacing(10)
        self.character_icons.connect("selection-changed", lambda *_: self.on_character_selected())
        self.character_icons.connect("item-activated", lambda *_: self.character_make_image())
        left = Gtk.ScrolledWindow(); left.set_min_content_width(610); left.add(self.character_icons)
        paned.pack1(left, True, False)

        right_sc = Gtk.ScrolledWindow(); right_sc.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8); right.set_border_width(12); right.get_style_context().add_class("card")
        right_sc.add(right)
        self.character_preview = Gtk.Image(); right.pack_start(self.character_preview, False, False, 0)
        self.character_title = Gtk.Label(label="Select a character", xalign=0); self.character_title.get_style_context().add_class("section-title"); right.pack_start(self.character_title, False, False, 0)
        self.character_detail = Gtk.Label(label="", xalign=0); self.character_detail.set_line_wrap(True); self.character_detail.set_selectable(True); right.pack_start(self.character_detail, False, False, 0)
        self.character_use_btn = Gtk.Button(label="Use in Create"); self.character_use_btn.set_sensitive(False); self.character_use_btn.get_style_context().add_class("suggested-action"); self.character_use_btn.connect("clicked", lambda *_: self.character_use_in_create())
        self.character_workflow_btn = Gtk.Button(label="Create Qwen Character Workflow"); self.character_workflow_btn.set_sensitive(False); self.character_workflow_btn.connect("clicked", lambda *_: self.character_make_image())
        open_img = Gtk.Button(label="Open Reference Image"); open_img.connect("clicked", lambda *_: self.open_selected_character())
        for b in (self.character_use_btn, self.character_workflow_btn, open_img): right.pack_start(b, False, False, 0)
        paned.pack2(right_sc, False, False)
        GLib.idle_add(self.refresh_characters, True)
        return page

    def refresh_characters(self, reset_kinds=False):
        self.characters_cache = character_library.scan_characters()
        if reset_kinds and hasattr(self, "character_kind"):
            active = self.character_kind.get_active_text() or "All"
            self.character_kind.remove_all(); self.character_kind.append_text("All")
            kinds = character_library.categories(self.characters_cache)
            for k in kinds: self.character_kind.append_text(k)
            choices = ["All"] + kinds
            self.character_kind.set_active(choices.index(active) if active in choices else 0)
            if hasattr(self, "character_collection"):
                active_collection = self.character_collection.get_active_text() or "All collections"
                self.character_collection.remove_all(); self.character_collection.append_text("All collections")
                collections = character_library.collections(self.characters_cache)
                for c in collections: self.character_collection.append_text(c)
                cchoices = ["All collections"] + collections
                self.character_collection.set_active(cchoices.index(active_collection) if active_collection in cchoices else 0)
        search = (self.character_search.get_text() if hasattr(self, "character_search") else "").strip().lower()
        kind = (self.character_kind.get_active_text() if hasattr(self, "character_kind") else "All") or "All"
        collection = (self.character_collection.get_active_text() if hasattr(self, "character_collection") else "All collections") or "All collections"
        self.character_store.clear()
        visible = []
        for c in self.characters_cache:
            hay = " ".join([c.name,c.role,c.kind,c.identity,c.pronouns,c.body_type,c.species," ".join(c.tags)]).lower()
            if search and search not in hay: continue
            if kind != "All" and c.kind != kind: continue
            if collection != "All collections" and c.collection != collection: continue
            visible.append(c)
            try:
                pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(character_library.thumbnail_path(c)), 180, 235, True)
            except Exception:
                pix = None
            label = c.name + (f"\n{c.role}" if c.role else "")
            self.character_store.append([pix, label, c.uid])
        groups = {}
        for c in self.characters_cache: groups[c.kind] = groups.get(c.kind,0)+1
        group_text = " • ".join(f"{k}: {v}" for k,v in sorted(groups.items()))
        self.character_summary.set_text(f"{len(self.characters_cache)} characters discovered • {len(visible)} shown" + (f" • {group_text}" if group_text else ""))
        if hasattr(self, "create_character"):
            self.refresh_create_panel()
        return False

    def _selected_character(self):
        paths = self.character_icons.get_selected_items()
        if not paths: return None
        itr = self.character_store.get_iter(paths[0])
        uid = self.character_store.get_value(itr, 2)
        return character_library.find_character(uid, self.characters_cache)

    def on_character_selected(self):
        c = self._selected_character()
        self.character_use_btn.set_sensitive(bool(c)); self.character_workflow_btn.set_sensitive(bool(c))
        if not c:
            self.character_title.set_text("Select a character"); self.character_detail.set_text(""); self.character_preview.clear(); return
        self.character_title.set_text(c.name)
        parts = [
            f"Role: {c.role}" if c.role else "",
            f"Type: {c.kind}" if c.kind else "",
            f"Identity: {c.identity} ({c.pronouns})" if c.identity or c.pronouns else "",
            f"Body: {c.body_type}" if c.body_type else "",
            f"Species: {c.species}" if c.species else "",
            f"Tags: {', '.join(c.tags)}" if c.tags else "",
            f"Collection: {c.collection}" if c.collection else "",
            f"File: {c.image_path}",
        ]
        if c.warnings: parts.append("Warnings: " + "; ".join(c.warnings))
        self.character_detail.set_text("\n".join(x for x in parts if x))
        try:
            pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(c.image_path), 330, 440, True)
            self.character_preview.set_from_pixbuf(pix)
        except Exception:
            self.character_preview.set_from_icon_name("image-missing", Gtk.IconSize.DIALOG)

    def character_use_in_create(self):
        c = self._selected_character()
        if not c: return
        self.tabs.set_current_page(0)
        # Character Image is the first mode in the current catalog.
        self.create_mode.set_active(0)
        for i in range(len(self.characters_cache)):
            if self.create_character.get_active_id() == c.uid: break
            self.create_character.set_active(i)
            if self.create_character.get_active_id() == c.uid: break
        self.create_prompt.grab_focus()

    def character_make_image(self):
        c = self._selected_character()
        if not c: return
        self.character_use_in_create()
        self.create_quick_workflow(queue_now=False)

    def open_selected_character(self):
        c = self._selected_character()
        if c: platform_support.open_target(c.image_path)

    def create_character_folder(self):
        d=Gtk.Dialog(title="New Character Folder",transient_for=self,flags=0)
        d.add_button("Cancel",Gtk.ResponseType.CANCEL); d.add_button("Create",Gtk.ResponseType.OK)
        entry=Gtk.Entry(); entry.set_placeholder_text("Example: My Story / Heroes")
        box=d.get_content_area(); box.set_border_width(14); box.pack_start(Gtk.Label(label="Folder name or nested path",xalign=0),False,False,4); box.pack_start(entry,False,False,4)
        d.show_all()
        if d.run()==Gtk.ResponseType.OK:
            raw=entry.get_text().strip().replace("\\\\","/")
            parts=[p.strip() for p in raw.split("/") if p.strip() and p.strip() not in (".","..")]
            if parts:
                target=character_library.USER_ROOT
                for p in parts:
                    safe="".join(c if c.isalnum() or c in " _-" else "_" for c in p).strip()
                    if safe: target=target/safe
                target.mkdir(parents=True,exist_ok=True)
                open_path(target)
                self.refresh_characters()
        d.destroy()

    def import_character_image(self):
        d = Gtk.FileChooserDialog(title="Import Character Reference", transient_for=self, action=Gtk.FileChooserAction.OPEN)
        d.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, "Import", Gtk.ResponseType.OK)
        filt = Gtk.FileFilter(); filt.set_name("Images");
        for pat in ("*.png","*.jpg","*.jpeg","*.webp","*.PNG","*.JPG","*.JPEG","*.WEBP"): filt.add_pattern(pat)
        d.add_filter(filt)
        if d.run() == Gtk.ResponseType.OK:
            src = Path(d.get_filename())
            dest_dir = character_library.USER_ROOT / "Custom"
            dest_dir.mkdir(parents=True, exist_ok=True)
            dst = dest_dir / src.name
            n = 2
            while dst.exists():
                dst = dest_dir / f"{src.stem} {n}{src.suffix}"
                n += 1
            shutil.copy2(src, dst)
            d.destroy()
            self.refresh_characters(reset_kinds=True)
            self.dialog("Character imported", f"{dst.name}\n\nThe filename becomes the default character name. Add a same-name .json sidecar later if you want roles, tags, pronouns, species, or other metadata.")
            return
        d.destroy()

    def _models(self):
        page=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=10); page.set_border_width(14)
        page.pack_start(RoleHeader("analyst","Model Library","Inspect the actual model files ComfyUI can see, detect broken symlinks and physical duplicates, and export a reproducible manifest."),False,False,0)
        bar=Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,spacing=8)
        for label,fn in (("Rescan",self.refresh_models),("Export Manifest",self.export_model_manifest),("Open Canonical Models",lambda: open_path(MODEL_ROOT)),("Open ComfyUI Models",lambda: open_path(COMFY/"models"))):
            b=Gtk.Button(label=label); b.connect("clicked",lambda _b,f=fn: f()); bar.pack_start(b,False,False,0)
        page.pack_start(bar,False,False,0)
        self.model_summary=Gtk.Label(label="",xalign=0); self.model_summary.get_style_context().add_class("kisha-label"); page.pack_start(self.model_summary,False,False,0)
        self.model_store=Gtk.ListStore(str,str,str,str,str,str)
        tree=Gtk.TreeView(model=self.model_store)
        for i,title in enumerate(("Status","Category","File","Size","Origin","Location")):
            r=Gtk.CellRendererText(); c=Gtk.TreeViewColumn(title,r,text=i); c.set_resizable(True); tree.append_column(c)
        sc=Gtk.ScrolledWindow(); sc.add(tree); page.pack_start(sc,True,True,0)
        self.model_notes=Gtk.Label(label="",xalign=0); self.model_notes.set_line_wrap(True); self.model_notes.get_style_context().add_class("muted"); page.pack_start(self.model_notes,False,False,0)
        GLib.idle_add(self.refresh_models)
        return page

    def refresh_models(self):
        rows=model_library.scan(); sm=model_library.summary(rows); self.model_store.clear()
        for r in rows:
            loc=r['target'] if r['symlink'] else r['path']
            self.model_store.append([r['status'],r['category'],r['name'],r['size_h'],r['origin'],loc])
        self.model_summary.set_text(f"{sm['entries']} visible entries • {sm['physical_files']} physical files • {model_library.human(sm['physical_bytes'])} • {sm['broken']} broken links • {sm['duplicate_names']} duplicate-name groups")
        notes=[]
        br=model_library.broken_links(rows); dup=model_library.duplicate_report(rows)
        if br: notes.append(f"Broken links need repair: {len(br)}")
        if dup: notes.append(f"Potential duplicate physical assets: {len(dup)} groups")
        if not notes: notes.append("Model library looks structurally clean: no broken symlinks or duplicate physical basenames detected.")
        self.model_notes.set_text(" • ".join(notes)); return False

    def export_model_manifest(self):
        p=model_library.export_manifest(); self.dialog("Model manifest exported",str(p)); notify("Model manifest exported",str(p))

    def _queue_benchmarks(self):
        page=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=10); page.set_border_width(14)
        page.pack_start(RoleHeader("analyst","Queue + Benchmarks","Watch live ComfyUI generations and automatically record elapsed time, detected models, resolution, steps, frames, and peak VRAM while this app is open."),False,False,0)
        controls=Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,spacing=8)
        self.queue_label=Gtk.Label(label="Queue: checking…",xalign=0); controls.pack_start(self.queue_label,True,True,0)
        ir=Gtk.Button(label="Interrupt Current"); ir.get_style_context().add_class("destructive-action"); ir.connect("clicked",lambda *_: self.interrupt_current_generation()); controls.pack_end(ir,False,False,0)
        ex=Gtk.Button(label="Export CSV"); ex.connect("clicked",lambda *_: self.export_benchmarks()); controls.pack_end(ex,False,False,0)
        cl=Gtk.Button(label="Clear Records"); cl.connect("clicked",lambda *_: self.clear_benchmarks()); controls.pack_end(cl,False,False,0)
        page.pack_start(controls,False,False,0)
        self.bench_store=Gtk.ListStore(str,str,str,str,str,str,str,str)
        tree=Gtk.TreeView(model=self.bench_store)
        for i,title in enumerate(("Finished","Elapsed","Peak VRAM","Resolution","Steps","Frames","Status","Models")):
            r=Gtk.CellRendererText(); c=Gtk.TreeViewColumn(title,r,text=i); c.set_resizable(True); tree.append_column(c)
        sc=Gtk.ScrolledWindow(); sc.add(tree); page.pack_start(sc,True,True,0)
        self.bench_note=Gtk.Label(label="Automatic timing starts when a prompt is observed in the running queue. Peak VRAM is sampled at the app refresh cadence.",xalign=0); self.bench_note.set_line_wrap(True); self.bench_note.get_style_context().add_class("muted"); page.pack_start(self.bench_note,False,False,0)
        GLib.idle_add(self.refresh_benchmarks)
        return page

    def refresh_benchmarks(self):
        self.bench_store.clear()
        for r in reversed(benchmark_store.load()[-300:]):
            ev=f"{float(r.get('elapsed_s',0)):.1f}s" if r.get('elapsed_s') not in ('',None) else ''
            pv=f"{float(r.get('peak_vram_gib',0)):.2f} GiB" if r.get('peak_vram_gib') else ''
            self.bench_store.append([str(r.get('finished','')),ev,pv,str(r.get('resolution','')),str(r.get('steps','')),str(r.get('frames','')),str(r.get('status','')),str(r.get('models',''))])
        return False

    def refresh_queue_monitor(self):
        if not self.cfg.get('auto_benchmark',True): return True
        if not self.last_status or not self.last_status.http:
            self.queue_label.set_text("Queue: ComfyUI offline") if hasattr(self,'queue_label') else None
            return True
        def worker():
            try: items=benchmark_store.queue_items(self.cfg['browser_url'])
            except Exception: items=[]
            GLib.idle_add(self._apply_queue_items,items)
        threading.Thread(target=worker,daemon=True).start(); return True

    def _apply_queue_items(self,items):
        now=time.time(); current={x['id']:x for x in items}; running=[x for x in items if x['state']=='running']; pending=[x for x in items if x['state']=='pending']
        if hasattr(self,'queue_label'): self.queue_label.set_text(f"Queue: {len(running)} running • {len(pending)} pending")
        peak=(self.last_status.gpu_used/(1024**3)) if self.last_status and self.last_status.gpu_used else 0
        for x in running:
            pid=x['id']
            if pid not in self.active_runs:
                meta=benchmark_store.summarize_prompt(x.get('prompt') or {})
                self.active_runs[pid]={"started":now,"peak":peak,"meta":meta}
            else: self.active_runs[pid]['peak']=max(self.active_runs[pid].get('peak',0),peak)
        done=[]
        for pid,rec in list(self.active_runs.items()):
            if pid not in current:
                status=benchmark_store.history_status(self.cfg['browser_url'],pid)
                row={"finished":datetime.now().strftime('%Y-%m-%d %H:%M:%S'),"prompt_id":pid,"elapsed_s":round(now-rec['started'],2),"peak_vram_gib":round(rec.get('peak',0),3),"status":status,**rec['meta']}
                benchmark_store.add(row); done.append(pid)
        for pid in done: self.active_runs.pop(pid,None)
        if done and hasattr(self,'bench_store'): self.refresh_benchmarks()
        self.last_queue=items
        return False

    def interrupt_current_generation(self):
        if not self.confirm("Interrupt current generation?","This asks ComfyUI to interrupt the active generation. Pending jobs are not deleted."): return
        def task():
            try:
                req=urllib.request.Request(self.cfg['browser_url'].rstrip('/')+'/interrupt',data=b'',method='POST',headers={'User-Agent':APP_NAME})
                with urllib.request.urlopen(req,timeout=3) as r: return 0,f"HTTP {r.status}"
            except Exception as e: return 1,str(e)
        self.background(task,lambda r: self.dialog("Interrupt sent" if r[0]==0 else "Interrupt failed",r[1],Gtk.MessageType.INFO if r[0]==0 else Gtk.MessageType.ERROR),"Interrupting generation…")

    def export_benchmarks(self):
        p=benchmark_store.export_csv(); self.dialog("Benchmarks exported",str(p))

    def clear_benchmarks(self):
        if self.confirm("Clear benchmark records?","This removes the app's local benchmark history only. ComfyUI outputs are untouched."):
            benchmark_store.clear(); self.refresh_benchmarks()

    def _gallery(self):
        page=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=10); page.set_border_width(14)
        page.pack_start(RoleHeader("everyday","Output Gallery","Browse recent ComfyUI images and videos without hunting through folders. Images preview in-app; videos open with your normal desktop player."),False,False,0)
        bar=Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,spacing=8)
        rf=Gtk.Button(label="Refresh Gallery"); rf.connect("clicked",lambda *_: self.refresh_gallery()); bar.pack_start(rf,False,False,0)
        of=Gtk.Button(label="Open Output Folder"); of.connect("clicked",lambda *_: open_path(OUTPUT_ROOT)); bar.pack_start(of,False,False,0); page.pack_start(bar,False,False,0)
        pan=Gtk.Paned.new(Gtk.Orientation.HORIZONTAL); page.pack_start(pan,True,True,0)
        self.gallery_store=Gtk.ListStore(str,str,str,str)
        tree=Gtk.TreeView(model=self.gallery_store); self.gallery_tree=tree
        for i,title in enumerate(("Type","File","Modified","Path")):
            r=Gtk.CellRendererText(); c=Gtk.TreeViewColumn(title,r,text=i); c.set_resizable(True); tree.append_column(c)
        tree.get_selection().connect('changed',self.on_gallery_selected)
        sc=Gtk.ScrolledWindow(); sc.set_min_content_width(520); sc.add(tree); pan.pack1(sc,True,False)
        right=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8); right.set_border_width(10); right.get_style_context().add_class('card')
        self.gallery_preview=Gtk.Image(); right.pack_start(self.gallery_preview,True,True,0)
        self.gallery_info=Gtk.Label(label='Select an output.',xalign=0); self.gallery_info.set_line_wrap(True); right.pack_start(self.gallery_info,False,False,0)
        op=Gtk.Button(label='Open Selected'); op.connect('clicked',lambda *_: self.open_gallery_selected()); right.pack_start(op,False,False,0)
        pan.pack2(right,False,False); GLib.idle_add(self.refresh_gallery); return page

    def refresh_gallery(self):
        self.gallery_rows=gallery_helper.scan(); self.gallery_store.clear()
        for r in self.gallery_rows: self.gallery_store.append([r['type'],r['name'],r['time'],r['path']])
        return False

    def _gallery_selected_path(self):
        m,it=self.gallery_tree.get_selection().get_selected(); return Path(m[it][3]) if it else None

    def on_gallery_selected(self,*_):
        p=self._gallery_selected_path()
        if not p: return
        self.gallery_info.set_text(str(p))
        if p.suffix.lower() in gallery_helper.IMG:
            try:
                pix=GdkPixbuf.Pixbuf.new_from_file(str(p)); w,h=pix.get_width(),pix.get_height(); scale=min(390/max(1,w),420/max(1,h),1.0); pix=pix.scale_simple(max(1,int(w*scale)),max(1,int(h*scale)),GdkPixbuf.InterpType.BILINEAR); self.gallery_preview.set_from_pixbuf(pix)
            except Exception: self.gallery_preview.clear()
        else: self.gallery_preview.set_from_icon_name('video-x-generic',Gtk.IconSize.DIALOG)

    def open_gallery_selected(self):
        p=self._gallery_selected_path()
        if p: subprocess.Popen(['xdg-open',str(p)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

    def _logs(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        page.set_border_width(14)
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.log_path_label = Gtk.Label(label="No log selected", xalign=0)
        self.log_path_label.set_ellipsize(Pango.EllipsizeMode.END)
        bar.pack_start(self.log_path_label, True, True, 0)
        b1 = Gtk.Button(label="Refresh Log")
        b1.connect("clicked", lambda *_: self.refresh_log())
        b2 = Gtk.ToggleButton(label="Errors Only")
        b2.connect("toggled", self.toggle_errors)
        b3 = Gtk.Button(label="Open Log Folder")
        b3.connect("clicked", lambda *_: open_path(LOG_ROOT))
        bar.pack_end(b3, False, False, 0)
        bar.pack_end(b2, False, False, 0)
        bar.pack_end(b1, False, False, 0)
        page.pack_start(bar, False, False, 0)

        sc = Gtk.ScrolledWindow()
        self.log_view = Gtk.TextView()
        self.log_view.set_editable(False)
        self.log_view.set_cursor_visible(False)
        self.log_view.set_monospace(True)
        self.log_view.set_wrap_mode(Gtk.WrapMode.NONE)
        sc.add(self.log_view)
        page.pack_start(sc, True, True, 0)
        return page

    def _utilities(self):
        sc = Gtk.ScrolledWindow()
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        page.set_border_width(16)
        sc.add(page)

        page.pack_start(RoleHeader("field","Field Utilities","Diagnostics, repair, backup, cleanup, and environment inspection without creating a second runtime authority."),False,False,0)

        intro = Gtk.Label(
            label="Conservative maintenance tools. Destructive operations are scoped and confirmed.",
            xalign=0,
        )
        intro.set_line_wrap(True)
        intro.get_style_context().add_class("muted")
        page.pack_start(intro, False, False, 0)

        sections = [
            ("Diagnostics", [
                ("Run Health Check", self.health_check),
                ("Export Diagnostics", self.export_diagnostics),
                ("Export Reproducibility Snapshot", self.export_repro_snapshot),
                ("Open Workstation Crash Log", self.open_crash_log),
                ("Check ComfyUI Updates", self.check_comfy_updates),
                ("Check Python Packages", self.pip_check),
                ("Inspect Port 8188", self.port_diagnostics),
            ]),
            ("Repair", [
                ("Repair GGUF Dependencies", self.repair_gguf),
                ("Repair Desktop / Start Menu Entry", self.repair_desktop),
                ("Install / Repair Hugging Face CLI", self.repair_hf_cli),
                ("Verify ComfyUI Git State", self.git_state),
            ]),
            ("Cleanup", [
                ("Clear ComfyUI Temp Files", self.clear_temp),
                ("Remove Logs Older Than 30 Days", self.clean_old_logs),
            ]),
            ("Application", [
                ("Reset Control Center Settings", self.reset_settings),
                ("Uninstall Control Center", self.uninstall_self),
            ]),
        ]
        for title, items in sections:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7)
            box.get_style_context().add_class("card")
            lab = Gtk.Label(label=title, xalign=0)
            lab.get_style_context().add_class("section-title")
            box.pack_start(lab, False, False, 0)
            for label, fn in items:
                b = Gtk.Button(label=label)
                b.set_halign(Gtk.Align.FILL)
                if "Uninstall" in label:
                    b.get_style_context().add_class("destructive-action")
                b.connect("clicked", lambda _b, f=fn: f())
                box.pack_start(b, False, False, 0)
            page.pack_start(box, False, False, 0)

        self.utility_output = Gtk.TextView()
        self.utility_output.set_editable(False)
        self.utility_output.set_cursor_visible(False)
        self.utility_output.set_monospace(True)
        self.utility_output.set_size_request(-1, 180)
        usp = Gtk.ScrolledWindow()
        usp.set_min_content_height(180)
        usp.add(self.utility_output)
        page.pack_start(usp, True, True, 0)
        return sc

    def _settings(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        page.set_border_width(18)

        grid = Gtk.Grid()
        grid.set_row_spacing(10)
        grid.set_column_spacing(12)
        grid.get_style_context().add_class("card")

        self.host_entry = Gtk.Entry()
        self.host_entry.set_text(str(self.cfg["host"]))
        self.port_spin = Gtk.SpinButton.new_with_range(1, 65535, 1)
        self.port_spin.set_value(int(self.cfg["port"]))
        self.url_entry = Gtk.Entry()
        self.url_entry.set_text(str(self.cfg["browser_url"]))
        self.refresh_spin = Gtk.SpinButton.new_with_range(1, 30, 1)
        self.refresh_spin.set_value(int(self.cfg["refresh_seconds"]))

        self.auto_bench_check = Gtk.CheckButton(label="Automatically record observed generation benchmarks")
        self.auto_bench_check.set_active(bool(self.cfg.get("auto_benchmark", True)))
        self.splash_check = Gtk.CheckButton(label="Show Kisha startup splash (disabled during pre-release qualification)")
        self.splash_check.set_active(bool(self.cfg.get("splash", True)))
        rows = [
            ("Host", self.host_entry),
            ("Port", self.port_spin),
            ("Browser URL", self.url_entry),
            ("Refresh interval (sec)", self.refresh_spin),
        ]
        for i, (label, widget) in enumerate(rows):
            l = Gtk.Label(label=label, xalign=0)
            grid.attach(l, 0, i, 1, 1)
            grid.attach(widget, 1, i, 1, 1)
        page.pack_start(grid, False, False, 0)
        page.pack_start(self.auto_bench_check, False, False, 0)
        page.pack_start(self.splash_check, False, False, 0)

        note = Gtk.Label(
            label=(
                "Start/stop intentionally uses your existing Qualification launcher scripts when present. "
                "The control center does not create a competing ComfyUI runtime path."
            ),
            xalign=0,
        )
        note.set_line_wrap(True)
        note.get_style_context().add_class("muted")
        page.pack_start(note, False, False, 0)

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        save = Gtk.Button(label="Save Settings")
        save.get_style_context().add_class("suggested-action")
        save.connect("clicked", lambda *_: self.save_settings())
        guide = Gtk.Button(label="Run Guided Setup Again")
        guide.connect("clicked", lambda *_: self.show_setup_guide(force=True))
        buttons.pack_start(save, False, False, 0)
        buttons.pack_start(guide, False, False, 0)
        page.pack_start(buttons, False, False, 0)
        return page


    def _presets(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        page.set_border_width(14)

        page.pack_start(RoleHeader("everyday","Blueprints","Reusable creation recipes. Each Blueprint declares the Pack/models it needs and can open directly in ComfyUI."),False,False,0)

        intro = Gtk.Label(
            label="Blueprints are the single recipe system used by Create, Starter Packs, Characters, and ComfyUI. READY means its required model Pack is already available.",
            xalign=0,
        )
        intro.set_line_wrap(True)
        intro.get_style_context().add_class("muted")
        page.pack_start(intro, False, False, 0)

        tools = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bscan = Gtk.Button(label="Scan Installed Models")
        bscan.connect("clicked", lambda *_: self.refresh_presets())
        ball = Gtk.Button(label="Sync Ready Blueprints to ComfyUI")
        ball.get_style_context().add_class("suggested-action")
        ball.connect("clicked", lambda *_: self.install_all_presets())
        bopen = Gtk.Button(label="Open Technical Workflow Folder")
        bopen.connect("clicked", lambda *_: open_path(PRESET_ROOT / "Superior-MI-Labs"))
        tools.pack_start(bscan, False, False, 0)
        tools.pack_start(ball, False, False, 0)
        tools.pack_start(bopen, False, False, 0)
        tools.pack_end(Gtk.Label(label="Category"), False, False, 0)
        self.preset_category_filter = Gtk.ComboBoxText()
        for cat in ("All", "Image", "Video", "Mobile", "Character", "Style", "Benchmark"):
            self.preset_category_filter.append_text(cat)
        self.preset_category_filter.set_active(0)
        self.preset_category_filter.connect("changed", lambda *_: self.refresh_presets())
        tools.pack_end(self.preset_category_filter, False, False, 0)
        page.pack_start(tools, False, False, 0)

        self.preset_detect_label = Gtk.Label(label="", xalign=0)
        self.preset_detect_label.get_style_context().add_class("kisha-label")
        page.pack_start(self.preset_detect_label, False, False, 0)

        paned = Gtk.Paned.new(Gtk.Orientation.HORIZONTAL)
        page.pack_start(paned, True, True, 0)

        self.preset_store = Gtk.ListStore(str, str, str, str, str)
        self.preset_tree = Gtk.TreeView(model=self.preset_store)
        for idx,title in enumerate(("Category","Preset","Family","Status")):
            rend=Gtk.CellRendererText()
            col=Gtk.TreeViewColumn(title,rend,text=idx+1 if idx<4 else 4)
            self.preset_tree.append_column(col)
        self.preset_tree.get_selection().connect("changed", self.on_preset_selected)
        left=Gtk.ScrolledWindow()
        left.set_min_content_width(520)
        left.add(self.preset_tree)
        paned.pack1(left, True, False)

        right_sc=Gtk.ScrolledWindow(); right_sc.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC)
        right=Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        right.set_border_width(12)
        right.get_style_context().add_class("card")
        right_sc.add(right)
        lab=Gtk.Label(label="BLUEPRINT DETAILS", xalign=0)
        lab.get_style_context().add_class("section-title")
        right.pack_start(lab, False, False, 0)
        self.preset_detail = Gtk.Label(label="Select a Blueprint.", xalign=0)
        self.preset_detail.set_line_wrap(True)
        self.preset_detail.set_selectable(True)
        details_sc = Gtk.ScrolledWindow()
        details_sc.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        details_sc.set_min_content_height(190)
        details_sc.add(self.preset_detail)
        right.pack_start(details_sc, True, True, 0)
        self.preset_install_btn = Gtk.Button(label="Open in ComfyUI")
        self.preset_install_btn.set_sensitive(False)
        self.preset_install_btn.connect("clicked", lambda *_: self.install_selected_preset())
        right.pack_start(self.preset_install_btn, False, False, 0)

        sep=Gtk.Separator()
        right.pack_start(sep, False, False, 4)
        q=Gtk.Label(label="QUICK BLUEPRINT FILTER", xalign=0)
        q.get_style_context().add_class("section-title")
        right.pack_start(q, False, False, 0)
        self.builder_family = Gtk.ComboBoxText()
        self.builder_family.connect("changed", lambda *_: self.populate_builder_profiles())
        self.builder_profile = Gtk.ComboBoxText()
        build=Gtk.Button(label="Open Matching Blueprint")
        build.get_style_context().add_class("suggested-action")
        build.connect("clicked", lambda *_: self.build_quick_preset())
        right.pack_start(Gtk.Label(label="Detected model family", xalign=0), False, False, 0)
        right.pack_start(self.builder_family, False, False, 0)
        right.pack_start(Gtk.Label(label="Easy profile", xalign=0), False, False, 0)
        right.pack_start(self.builder_profile, False, False, 0)
        right.pack_start(build, False, False, 0)
        note=Gtk.Label(label="This only exposes compatible local model families. Opening a Blueprint imports it into ComfyUI and loads the graph through the Workstation bridge.", xalign=0)
        note.set_line_wrap(True)
        note.get_style_context().add_class("muted")
        right.pack_start(note, False, False, 0)
        paned.pack2(right_sc, False, False)

        GLib.idle_add(self.refresh_presets)
        return page

    def refresh_presets(self):
        entries=preset_manager.load_manifest()
        files=preset_manager.scan_model_files()
        fams=preset_manager.detect_families(files)
        self.preset_store.clear()
        category = self.preset_category_filter.get_active_text() if hasattr(self, "preset_category_filter") else "All"
        for e in entries:
            if category and category != "All" and e.get("category") != category:
                continue
            ok=preset_manager.compatible(e,files)
            self.preset_store.append([e["id"],e["category"],e["title"],e["family"],"READY" if ok else "MISSING MODELS"])
        ready=[k for k,v in fams.items() if v]
        self.preset_detect_label.set_text("Detected: " + (", ".join(ready) if ready else "No supported preset families detected yet"))
        active=self.builder_family.get_active_text()
        self.builder_family.remove_all()
        for fam in sorted(ready):
            self.builder_family.append_text(fam)
        if ready:
            self.builder_family.set_active(0)
        self.populate_builder_profiles()
        return False

    def open_preset_category(self, category):
        self.tabs.set_current_page(1)
        if hasattr(self, "library_tabs"):
            self.library_tabs.set_current_page(0)
        if hasattr(self, "preset_category_filter"):
            options = ["All", "Image", "Video", "Mobile", "Character", "Style", "Benchmark"]
            try:
                self.preset_category_filter.set_active(options.index(category))
            except ValueError:
                self.preset_category_filter.set_active(0)
            self.refresh_presets()

    def _selected_preset_entry(self):
        model,itr=self.preset_tree.get_selection().get_selected()
        if not itr:
            return None
        pid=model[itr][0]
        for e in preset_manager.load_manifest():
            if e["id"]==pid:
                return e
        return None

    def on_preset_selected(self, *_):
        e=self._selected_preset_entry()
        if not e:
            self.preset_install_btn.set_sensitive(False)
            return
        ok=preset_manager.compatible(e)
        req=", ".join(e.get("required_files",[]))
        self.preset_detail.set_text(
            f"{e['title']}\n\n{e['description']}\n\nCategory: {e['category']}\nFamily: {e['family']}\nProfile: {e['profile']}\n\nRequired:\n{req}\n\nStatus: {'READY' if ok else 'Missing one or more required model files'}"
        )
        self.preset_install_btn.set_sensitive(ok)

    def install_selected_preset(self):
        e=self._selected_preset_entry()
        if not e:
            return
        if not preset_manager.compatible(e):
            stack_id = blueprint_manager.FAMILY_STACK.get(e.get("family",""), "")
            msg = "This Blueprint needs a model Pack first."
            if stack_id:
                msg += "\n\nOpen Starter Packs or Components to install its requirements."
            self.dialog("Blueprint is not ready", msg, Gtk.MessageType.WARNING)
            return
        if not (self.last_status and self.last_status.http):
            self.dialog("Start ComfyUI", "ComfyUI must be running to import and open a Blueprint.", Gtk.MessageType.INFO)
            return
        wf = json.loads((preset_manager.BUNDLE / e["path"]).read_text())
        result = self.open_api_workflow_in_comfy(wf, e["title"], folder="Superior MI/Blueprints")
        self.dialog("Blueprint opened", f"Imported into ComfyUI as:\n{result['path']}")

    def install_all_presets(self):
        if not (self.last_status and self.last_status.http):
            self.dialog("Start ComfyUI", "ComfyUI must be running to sync Blueprints into its workflow library.", Gtk.MessageType.INFO)
            return
        files=preset_manager.scan_model_files()
        entries=[e for e in preset_manager.load_manifest() if preset_manager.compatible(e,files)]
        if not entries:
            self.dialog("No ready Blueprints", "Install a Starter Pack first.", Gtk.MessageType.INFO)
            return
        def task():
            synced=[]
            for e in entries:
                wf=json.loads((preset_manager.BUNDLE / e["path"]).read_text())
                r=comfy_integration.import_api_workflow(
                    self.cfg["browser_url"], wf, e["title"], folder="Superior MI/Blueprints", open_now=False
                )
                synced.append(r["path"])
            return 0, synced
        def done(r):
            if r[0]:
                self.dialog("Blueprint sync failed",str(r[1]),Gtk.MessageType.ERROR)
            else:
                self.dialog("Blueprints synced",f"{len(r[1])} ready Blueprints are now in ComfyUI → Workflows → Superior MI → Blueprints.")
        self.background(task,done,"Syncing Blueprints to ComfyUI…")

    def populate_builder_profiles(self):
        fam=self.builder_family.get_active_text()
        self.builder_profile.remove_all()
        if not fam:
            return
        files=preset_manager.scan_model_files()
        seen=[]
        for e in preset_manager.load_manifest():
            if e["family"]==fam and preset_manager.compatible(e,files) and e["profile"] not in seen:
                seen.append(e["profile"])
                self.builder_profile.append_text(e["profile"])
        if seen:
            self.builder_profile.set_active(0)

    def build_quick_preset(self):
        fam=self.builder_family.get_active_text()
        prof=self.builder_profile.get_active_text()
        if not fam or not prof:
            self.dialog("Nothing selected","Choose an installed model family and profile.",Gtk.MessageType.WARNING)
            return
        for e in preset_manager.load_manifest():
            if e["family"]==fam and e["profile"]==prof and preset_manager.compatible(e):
                model=self.preset_store
                itr=model.get_iter_first()
                while itr:
                    if model[itr][0]==e["id"]:
                        self.preset_tree.get_selection().select_iter(itr)
                        self.install_selected_preset()
                        return
                    itr=model.iter_next(itr)
        self.dialog("No matching Blueprint","The selected family/profile recipe was not found.",Gtk.MessageType.ERROR)

    def _starter_packs(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        page.set_border_width(12)
        page.pack_start(RoleHeader("explorer", "Starter Packs", "One-click dependency bundles. Install a Pack once; every compatible Blueprint becomes ready automatically."), False, False, 0)

        intro = Gtk.Label(label="For a new user, start here. Packs install model components into the canonical ~/Models/Media library and symlink them into ComfyUI. Existing assets are detected and skipped.", xalign=0)
        intro.set_line_wrap(True); intro.get_style_context().add_class("muted")
        page.pack_start(intro, False, False, 0)

        paned = Gtk.Paned.new(Gtk.Orientation.HORIZONTAL)
        page.pack_start(paned, True, True, 0)
        self.pack_store = Gtk.ListStore(str,str,str,str)
        self.pack_tree = Gtk.TreeView(model=self.pack_store)
        for idx,title in enumerate(("Pack","For","Status")):
            r=Gtk.CellRendererText(); self.pack_tree.append_column(Gtk.TreeViewColumn(title,r,text=idx+1))
        self.pack_tree.get_selection().connect("changed", self.on_pack_selected)
        left=Gtk.ScrolledWindow(); left.add(self.pack_tree); left.set_min_content_width(470)
        paned.pack1(left, True, False)

        right_sc=Gtk.ScrolledWindow()
        right_sc.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC)
        right=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8); right.set_border_width(12); right.get_style_context().add_class("card")
        right_sc.add(right)
        self.pack_title=Gtk.Label(label="Select a Starter Pack",xalign=0); self.pack_title.get_style_context().add_class("section-title")
        self.pack_detail=Gtk.Label(label="",xalign=0); self.pack_detail.set_line_wrap(True); self.pack_detail.set_selectable(True)
        self.pack_auth=Gtk.CheckButton(label="I have applicable authorization / rights for restricted components")
        self.pack_auth.set_no_show_all(True)
        self.pack_install=Gtk.Button(label="Install Pack"); self.pack_install.get_style_context().add_class("suggested-action")
        self.pack_install.connect("clicked",lambda *_: self.install_selected_pack())
        self.pack_open=Gtk.Button(label="Open a Ready Blueprint"); self.pack_open.connect("clicked",lambda *_: self.open_pack_blueprint())
        self.pack_progress=Gtk.Label(label="",xalign=0); self.pack_progress.set_line_wrap(True); self.pack_progress.get_style_context().add_class("muted")
        for w in (self.pack_title,self.pack_detail,self.pack_auth,self.pack_install,self.pack_open,self.pack_progress):
            right.pack_start(w,False,False,0)
        paned.pack2(right_sc, True, False)
        GLib.idle_add(self.refresh_packs)
        return page

    def refresh_packs(self):
        self.pack_store.clear()
        for p in blueprint_manager.load_packs():
            self.pack_store.append([p["id"], p["title"], p.get("audience",""), blueprint_manager.pack_status(p)])
        return False

    def open_pack_by_id(self, pack_id):
        self.tabs.set_current_page(1)
        if hasattr(self,"library_tabs"):
            self.library_tabs.set_current_page(1)
        self.refresh_packs()
        model=self.pack_store
        itr=model.get_iter_first()
        while itr:
            if model[itr][0]==pack_id:
                self.pack_tree.get_selection().select_iter(itr)
                try:
                    self.pack_tree.scroll_to_cell(model.get_path(itr),None,True,0.3,0.0)
                except Exception:
                    pass
                return
            itr=model.iter_next(itr)

    def _selected_pack(self):
        model,itr=self.pack_tree.get_selection().get_selected()
        if not itr: return None
        return blueprint_manager.get_pack(model[itr][0])

    def on_pack_selected(self,*_):
        p=self._selected_pack()
        if not p: return
        status=blueprint_manager.pack_status(p)
        caps="\n".join("• "+x for x in p.get("capabilities",[]))
        stacks=blueprint_manager.pack_stacks(p)
        components="\n".join("• "+x.get("title","") for x in stacks)
        restricted=any(x.get("license_restricted") for x in stacks)
        known_sizes=[float(x.get("approx_download_gb") or 0) for x in stacks if x.get("approx_download_gb") is not None]
        size_line=f"\nApprox. download: {sum(known_sizes):.1f} GB" if known_sizes and len(known_sizes)==len(stacks) else ""
        self.pack_title.set_text(f"{p.get('badge','PACK')}  •  {p['title']}")
        self.pack_detail.set_text(
            f"{p['description']}\n\nStatus: {status}\nSuggested VRAM: {p.get('recommended_vram_gb','?')} GB+{size_line}"
            f"\n\nCapabilities:\n{caps}\n\nComponents:\n{components}"
        )
        self.pack_auth.set_visible(restricted)
        self.pack_auth.set_active(False)
        self.pack_install.set_sensitive(status!="INSTALLED")
        self.pack_open.set_sensitive(status=="INSTALLED")

    def install_selected_pack(self):
        p=self._selected_pack()
        if not p: return
        stacks=blueprint_manager.pack_stacks(p)
        restricted=any(x.get("license_restricted") for x in stacks)
        authorized=self.pack_auth.get_active()
        if restricted and not authorized:
            self.dialog("Authorization acknowledgement required","One or more components in this Pack have restricted terms. Review the source/license notes in Components first.",Gtk.MessageType.WARNING)
            return
        if not self.confirm("Install Starter Pack?", f"{p['title']}\n\nExisting model files are detected and skipped. Downloads are stored once under ~/Models/Media."):
            return
        def prog(msg): GLib.idle_add(self.pack_progress.set_text,msg)
        def task():
            try: return 0,pack_manager.install_pack(p,authorized=authorized,progress=prog)
            except Exception as e: return 1,str(e)
        def done(r):
            self.pack_progress.set_text("")
            if r[0]: self.dialog("Pack install failed",r[1],Gtk.MessageType.ERROR)
            else:
                self.dialog("Pack ready","The Pack is installed. Its Blueprints are now available.")
                self.refresh_packs(); self.refresh_presets(); self.refresh_create_panel()
        self.background(task,done,f"Installing {p['title']}…")

    def open_pack_blueprint(self):
        p=self._selected_pack()
        if not p: return
        family=p.get("default_blueprint_family","")
        self.library_tabs.set_current_page(0)
        self.refresh_presets()
        model=self.preset_store
        itr=model.get_iter_first()
        while itr:
            if model[itr][3]==family and model[itr][4]=="READY":
                self.preset_tree.get_selection().select_iter(itr)
                self.install_selected_preset()
                return
            itr=model.iter_next(itr)
        self.dialog("No ready Blueprint","The Pack is installed, but no compatible Blueprint was found.",Gtk.MessageType.WARNING)

    def _picks(self):
        page=Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        page.set_border_width(14)
        page.pack_start(RoleHeader("explorer","Components","Advanced model stacks, quantizations, accelerators, and add-ons. Starter Packs group these into easier installs."),False,False,0)
        intro=Gtk.Label(label="This is the advanced component catalog behind Starter Packs. Install individual stacks here when you want manual control.",xalign=0)
        intro.set_line_wrap(True)
        intro.get_style_context().add_class("muted")
        page.pack_start(intro,False,False,0)

        self.pick_hw_label=Gtk.Label(label="",xalign=0)
        self.pick_hw_label.get_style_context().add_class("kisha-label")
        page.pack_start(self.pick_hw_label,False,False,0)

        bar=Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,spacing=8)
        scan=Gtk.Button(label="Rescan Catalog")
        scan.connect("clicked",lambda *_: self.refresh_picks())
        src=Gtk.Button(label="Open Selected Source")
        src.connect("clicked",lambda *_: self.open_selected_stack_source())
        wf=Gtk.Button(label="Install Official Workflows")
        wf.connect("clicked",lambda *_: self.install_selected_stack_workflows())
        bar.pack_start(scan,False,False,0)
        bar.pack_start(src,False,False,0)
        bar.pack_start(wf,False,False,0)
        page.pack_start(bar,False,False,0)

        paned=Gtk.Paned.new(Gtk.Orientation.HORIZONTAL)
        page.pack_start(paned,True,True,0)
        self.pick_store=Gtk.ListStore(str,str,str,str,str)
        self.pick_tree=Gtk.TreeView(model=self.pick_store)
        for idx,title in enumerate(("Tier","Stack","Type","Status")):
            rend=Gtk.CellRendererText()
            col=Gtk.TreeViewColumn(title,rend,text=idx+1)
            self.pick_tree.append_column(col)
        self.pick_tree.get_selection().connect("changed",self.on_pick_selected)
        ls=Gtk.ScrolledWindow()
        ls.set_min_content_width(510)
        ls.add(self.pick_tree)
        paned.pack1(ls,True,False)

        right_sc=Gtk.ScrolledWindow(); right_sc.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC)
        right=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=9)
        right.set_border_width(12)
        right.get_style_context().add_class("card")
        right_sc.add(right)
        self.pick_title=Gtk.Label(label="Select a stack",xalign=0)
        self.pick_title.get_style_context().add_class("section-title")
        self.pick_detail=Gtk.Label(label="",xalign=0)
        self.pick_detail.set_line_wrap(True)
        self.pick_license=Gtk.Label(label="",xalign=0)
        self.pick_license.set_line_wrap(True)
        self.pick_license.get_style_context().add_class("muted")
        self.pick_auth=Gtk.CheckButton(label="I have applicable authorization / rights for this restricted model")
        self.pick_auth.set_no_show_all(True)
        self.pick_download=Gtk.Button(label="Download / Install Selected Stack")
        self.pick_download.get_style_context().add_class("suggested-action")
        self.pick_download.connect("clicked",lambda *_: self.download_selected_stack())
        self.pick_open_setup=Gtk.Button(label="Open Setup in ComfyUI")
        self.pick_open_setup.connect("clicked",lambda *_: self.open_selected_stack_setup())
        self.pick_progress=Gtk.Label(label="",xalign=0)
        self.pick_progress.set_line_wrap(True)
        self.pick_progress.get_style_context().add_class("muted")
        for w in (self.pick_title,self.pick_detail,self.pick_license,self.pick_auth,self.pick_download,self.pick_open_setup,self.pick_progress):
            right.pack_start(w,False,False,0)
        paned.pack2(right_sc,False,False)

        GLib.idle_add(self.refresh_picks)
        return page

    def _gpu_vram_gb(self):
        try:
            s=collect_status(self.cfg)
            return s.gpu_total/(1024**3) if s.gpu_total else 0
        except Exception:
            return 0

    def refresh_picks(self):
        stacks=stack_manager.load_catalog()
        names=stack_manager.scan_names()
        vram=self._gpu_vram_gb()
        self.pick_hw_label.set_text(f"Detected GPU VRAM: {vram:.1f} GiB • stacks near this tier are the best starting point")
        self.pick_store.clear()
        for st in stacks:
            status=stack_manager.stack_status(st,names)
            fit="MATCH" if st.get("vram_min",0)<=vram+0.5 and (st.get("vram_target",999)>=vram-8 or vram>=st.get("vram_min",0)) else ""
            tier=(fit+"  " if fit else "")+st.get("tier","")
            self.pick_store.append([st["id"],tier,st["title"],st["type"],status])
        return False

    def open_stack_by_id(self, stack_id):
        self.tabs.set_current_page(1)
        GLib.timeout_add(100, lambda: (self.library_tabs.set_current_page(3), False)[1] if hasattr(self, "library_tabs") else True)
        self.refresh_picks()
        model = self.pick_store
        itr = model.get_iter_first()
        while itr:
            if model[itr][0] == stack_id:
                self.pick_tree.get_selection().select_iter(itr)
                try:
                    path = model.get_path(itr)
                    self.pick_tree.scroll_to_cell(path, None, True, 0.35, 0.0)
                except Exception:
                    pass
                return
            itr = model.iter_next(itr)

    def _selected_stack(self):
        model,itr=self.pick_tree.get_selection().get_selected()
        if not itr:
            return None
        sid=model[itr][0]
        for st in stack_manager.load_catalog():
            if st["id"]==sid:
                return st
        return None

    def on_pick_selected(self,*_):
        st=self._selected_stack()
        if not st:
            return
        status=stack_manager.stack_status(st)
        self.pick_title.set_text(st["title"])
        ready="\n".join("• "+x for x in st.get('readiness',[]))
        size=st.get('approx_download_gb')
        size_line=f"\nApprox. curated download: {size} GB" if size else ""
        self.pick_detail.set_text(f"{st['description']}\n\nTier: {st.get('tier')}\nCatalog status: {st.get('status')}\nLocal status: {status}{size_line}"+(f"\n\nReadiness:\n{ready}" if ready else ""))
        self.pick_license.set_text("License / usage note:\n"+st.get("license_note","Review source terms."))
        restricted=bool(st.get("license_restricted"))
        self.pick_auth.set_visible(restricted)
        self.pick_auth.set_active(False)
        self.pick_download.set_sensitive(bool(st.get("assets")))
        if not st.get("assets"):
            self.pick_download.set_label("Informational / source-only entry")
        else:
            self.pick_download.set_label("Download / Install Selected Stack")
        self.pick_open_setup.set_sensitive(status=="INSTALLED" and bool(st.get("workflow_urls")))
        self.pick_progress.set_text("")

    def open_selected_stack_source(self):
        st=self._selected_stack()
        if st:
            open_url(st["source_url"])

    def install_selected_stack_workflows(self):
        st=self._selected_stack()
        if not st:
            return
        if not st.get("workflow_urls"):
            self.dialog("No workflow bundle","This catalog entry does not define downloadable ComfyUI workflows.")
            return
        def progress(msg):
            GLib.idle_add(self.pick_progress.set_text,msg)
        def task():
            try:
                return 0, stack_manager.install_workflows(st,progress)
            except Exception as e:
                return 1,str(e)
        def done(r):
            self.pick_progress.set_text("")
            if r[0]:
                self.dialog("Workflow download failed",r[1],Gtk.MessageType.ERROR)
                return
            paths=[Path(x.strip()) for x in str(r[1]).splitlines() if x.strip()]
            imported=[]
            if self.last_status and self.last_status.http:
                for p in paths:
                    try:
                        graph=json.loads(p.read_text())
                        saved=comfy_integration.store_ui_workflow(self.cfg["browser_url"],graph,p.name,folder="Superior MI/Official")
                        imported.append(saved)
                    except Exception as exc:
                        self.pick_progress.set_text(f"Downloaded but could not import {p.name}: {exc}")
                if imported:
                    comfy_integration.request_open_workflow(self.cfg["browser_url"],imported[0])
                    open_url(self.cfg["browser_url"])
            self.dialog("Official workflows ready",
                (f"Imported {len(imported)} workflow(s) into ComfyUI." if imported else "Downloaded the official workflow files. Start ComfyUI to import/open them automatically."))
        self.background(task,done,"Fetching official workflows…")

    def open_selected_stack_setup(self):
        st=self._selected_stack()
        if not st: return
        self.tabs.set_current_page(1)
        family_map={
            "flux2-klein-4b-fast":"FLUX.2 Klein 4B",
            "qwen-image-2.1-convrot":"Qwen Image 2.1",
            "wan2.2-ti2v-5b":"Wan2.2 TI2V 5B",
        }
        family=family_map.get(st.get("id"))
        if family:
            self.library_tabs.set_current_page(0)
            self.refresh_presets()
            model=self.preset_store; itr=model.get_iter_first()
            while itr:
                if model[itr][3]==family and model[itr][4]=="READY":
                    self.preset_tree.get_selection().select_iter(itr)
                    self.install_selected_preset()
                    return
                itr=model.iter_next(itr)
        # For stacks without a local API blueprint, install official workflows and open ComfyUI.
        if st.get("workflow_urls"):
            self.install_selected_stack_workflows()
        else:
            self.dialog("No ComfyUI setup yet","This component is an add-on and does not define a standalone workflow.",Gtk.MessageType.INFO)

    def download_selected_stack(self):
        st=self._selected_stack()
        if not st or not st.get("assets"):
            return
        authorized=self.pick_auth.get_active()
        if st.get("license_restricted") and not authorized:
            self.dialog("Authorization acknowledgement required",st.get("license_note","This model has restricted terms."),Gtk.MessageType.WARNING)
            return
        total=len(st.get("assets",[]))
        if not self.confirm("Download stack?",f"{st['title']}\n\nThis may download {total} model assets. Existing files are detected and skipped. Models are stored once under ~/Models/Media and symlinked into ComfyUI."):
            return
        def progress(msg):
            GLib.idle_add(self.pick_progress.set_text,msg)
        def task():
            try:
                return 0,stack_manager.download_stack(st,authorized,progress)
            except Exception as e:
                return 1,str(e)
        def done(r):
            self.pick_progress.set_text("")
            if r[0]:
                self.dialog("Stack install failed",r[1],Gtk.MessageType.ERROR)
            else:
                self.set_utility_output(r[1])
                self.dialog("Stack install complete",r[1])
                self.refresh_picks()
                self.refresh_presets()
        self.background(task,done,f"Installing {st['title']}…")

    def show_kisha_help(self):
        d=Gtk.Dialog(title="Kisha Help",transient_for=self,flags=0)
        d.add_button("Close",Gtk.ResponseType.CLOSE)
        d.set_default_size(720,500)
        box=d.get_content_area()
        outer=Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,spacing=18)
        outer.set_border_width(16)
        box.pack_start(outer,True,True,0)
        left=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8)
        left.pack_start(KishaRoleImage("reflection",175,220),False,False,0)
        orb=KishaOrb(); orb.set_size_request(90,90); left.pack_start(orb,False,False,0)
        name=Gtk.Label(label="KISHA / HELP")
        name.get_style_context().add_class("kisha-label")
        left.pack_start(name,False,False,0)
        topics={
          "First-time setup":"Use Setup Guide in the top bar. Kisha will detect your GPU, VRAM, driver, disk space, and whether ComfyUI is already installed. On supported NVIDIA Linux systems, Install / Finish ComfyUI creates the official checkout, isolated Python environment, current NVIDIA PyTorch path, requirements, and start/stop helpers. Then choose one starter model stack before adding more.",
          "How to use presets":"Open Presets, click Scan Installed Models, then choose any READY recipe. Install it and drag the resulting JSON from Qualification/presets/Superior-MI-Labs onto the ComfyUI graph. LoadImage placeholders need you to choose a real reference image before running.",
          "Choosing a Pack":"Library → Starter Packs is the easiest path. A Pack supplies the models/components needed by one or more Blueprints. Library → Components is the advanced view when you want individual quantizations, accelerators, or add-ons.",
          "Model library":"The app keeps canonical downloads under ~/Models/Media and symlinks them into ComfyUI/models. That avoids duplicate giant model files while keeping ComfyUI's normal loaders and directories.",
          "Runtime states":"RUNNING means the expected ComfyUI process exists and HTTP responds. STARTING means the process exists but the port is not ready. DEGRADED means the listener exists but health is not responding. PORT CONFLICT means another process owns the configured port.",
          "Character Library":"Characters are discovered recursively under ~/Models/Media/Characters. Any PNG/JPG/WEBP becomes a character automatically; its filename is the default name. Put characters in subfolders for categories. A same-name JSON file is optional metadata for role, tags, pronouns, species, body type, and stable IDs. The 21 Superior MI starter characters are seeded without overwriting user files.",
          "Reference characters":"For identity consistency, use the Character Library or Qwen Image 2.1 reference presets to create/approve canonical stills, then feed an approved still into Wan or another I2V model. Multi-reference identity is more reliable than seed-only character recreation.",
          "Performance":"Lower resolution, frame count and sampling steps first. Keep batch size at 1 on tighter GPUs. Do not randomly swap text encoders, VAEs, or model types across architectures: those are compatibility contracts, not style controls.",
          "Output gallery":"The Gallery tab shows recent images/videos from ComfyUI/output. Images preview inside the app; videos open in your desktop media player.",
          "Benchmarks":"Leave the control center open while generating. It watches the live ComfyUI queue and records elapsed time plus sampled peak VRAM, model filenames, resolution, steps and frame length when it can infer them from the prompt graph.",
          "Model health":"The Models tab scans both ComfyUI/models and ~/Models/Media, flags broken symlinks, and reports likely physical duplicate basenames. Export Manifest creates a reproducible JSON inventory without copying giant model files.",
          "Downloads & licenses":"Catalog downloads are convenience tooling, not a license grant. Restricted entries require explicit acknowledgement. Source and license links are kept with the stack so you can review them before downloading."
        }
        right=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=10)
        helptext=Gtk.Label(label="Choose a topic.",xalign=0)
        helptext.set_line_wrap(True)
        helptext.set_selectable(True)
        for title,body in topics.items():
            b=Gtk.Button(label=title)
            b.connect("clicked",lambda _b,t=title,body=body: helptext.set_text(f"{t}\n\n{body}"))
            left.pack_start(b,False,False,0)
        right.pack_start(helptext,True,True,0)
        outer.pack_start(left,False,False,0)
        outer.pack_start(right,True,True,0)
        d.show_all()
        d.run()
        d.destroy()

    def _about(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        page.set_border_width(24)
        page.pack_start(KishaRoleImage("reflection",240,300), False, False, 0)
        orb = KishaOrb(); orb.set_size_request(100, 100); page.pack_start(orb, False, False, 0)
        title = Gtk.Label(label="Superior MI Labs - ComfyUI Workstation")
        title.get_style_context().add_class("title-main")
        page.pack_start(title, False, False, 0)
        desc = Gtk.Label(
            label=(
                f"Version {VERSION}\n\n"
                "A local-first runtime utility for WolfCat-Studio. "
                "Designed around a single ComfyUI authority, observable state, safe maintenance, "
                "and Superior MI's northern technical visual language.\n\n"
                "Kisha serves here as the runtime sentinel and contextual help presence, not a second runtime or agent.\n\nVersion 2.2 adds a filesystem-driven expandable Character Library with 21 bundled Superior MI reference characters, a beginner Create surface that compiles simple choices into the existing ComfyUI pipeline, direct queue submission with node validation, and portability groundwork for future Windows/macOS builds."
            ),
            justify=Gtk.Justification.CENTER,
        )
        desc.set_line_wrap(True)
        page.pack_start(desc, False, False, 0)
        social = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        for label, url in SOCIAL_LINKS.items():
            b = Gtk.Button(label=label)
            b.connect("clicked", lambda _b, u=url: open_url(u))
            social.pack_start(b, False, False, 0)
        page.pack_start(social, False, False, 0)
        links_note = Gtk.Label(label="Superior MI Labs: GitHub • Hugging Face • Facebook", xalign=0)
        links_note.get_style_context().add_class("muted")
        page.pack_start(links_note, False, False, 0)
        return page

    def dialog(self, title, message, kind=Gtk.MessageType.INFO):
        d = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=kind,
            buttons=Gtk.ButtonsType.OK,
            text=title,
        )
        d.format_secondary_text(message)
        d.run()
        d.destroy()

    def confirm(self, title, message):
        d = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text=title,
        )
        d.format_secondary_text(message)
        result = d.run() == Gtk.ResponseType.OK
        d.destroy()
        return result

    def set_busy(self, busy, text=None):
        self.busy = busy
        if hasattr(self, "spinner"):
            self.spinner.start() if busy else self.spinner.stop()
        for name in ("start_btn", "stop_btn", "restart_btn"):
            b = getattr(self, name, None)
            if b is not None:
                b.set_sensitive(not busy)
        if text and hasattr(self, "status_detail"):
            self.status_detail.set_text(text)

    def background(self, fn, done=None, busy_text=None):
        if self.busy:
            return
        self.set_busy(True, busy_text)
        def worker():
            try:
                result = fn()
            except Exception as e:
                result = (999, str(e))
            GLib.idle_add(self._finish_bg, result, done)
        threading.Thread(target=worker, daemon=True).start()

    def _finish_bg(self, result, done):
        self.set_busy(False)
        if done:
            done(result)
        self.refresh(full=True)
        return False

    def refresh(self, full=False):
        def worker():
            s = collect_status(self.cfg, include_inventory=full)
            GLib.idle_add(self.apply_status, s, full)
        threading.Thread(target=worker, daemon=True).start()
        return True

    def apply_status(self, s, full=False):
        self.last_status = s
        try:
            if hasattr(self, "top_runtime_label"):
                self.top_runtime_label.set_text(f"ComfyUI: {s.state.lower()}")
            if hasattr(self, "top_runtime_btn"):
                self.top_runtime_btn.set_label("Stop ComfyUI" if s.pids else "Start ComfyUI")
            if hasattr(self, "orb"):
                self.orb.set_state(s.state)
            if hasattr(self, "status_title"):
                self.status_title.set_text(s.state)
            if hasattr(self, "status_detail"):
                self.status_detail.set_text(s.detail)
            if hasattr(self, "cmdline_label"):
                self.cmdline_label.set_text(s.cmdline or "Runtime command: none")

            if self.last_state != s.state:
                if s.state == "RUNNING":
                    notify("ComfyUI is running", s.detail)
                self.last_state = s.state

            for name, enabled in (
                ("start_btn", (not self.busy) and s.state in ("STOPPED",)),
                ("stop_btn", (not self.busy) and bool(s.pids)),
                ("restart_btn", (not self.busy) and bool(s.pids)),
            ):
                b = getattr(self, name, None)
                if b is not None:
                    b.set_sensitive(enabled)

            gu = (s.gpu_used / s.gpu_total) if s.gpu_total else 0
            if hasattr(self, "gpu"):
                self.gpu.bar.set_fraction(max(0, min(1, gu)))
                self.gpu.value.set_text(
                    f"{fmt_bytes(s.gpu_used)} / {fmt_bytes(s.gpu_total)} • {s.gpu_util}% • {s.gpu_temp}°C"
                    if s.gpu_total else "Unavailable"
                )
            ru = (s.ram_used / s.ram_total) if s.ram_total else 0
            if hasattr(self, "ram"):
                self.ram.bar.set_fraction(max(0, min(1, ru)))
                self.ram.value.set_text(f"{fmt_bytes(s.ram_used)} / {fmt_bytes(s.ram_total)}")
            du = 1 - (s.disk_free / s.disk_total) if s.disk_total else 0
            if hasattr(self, "disk"):
                self.disk.bar.set_fraction(max(0, min(1, du)))
                self.disk.value.set_text(f"{fmt_bytes(s.disk_free)} free")

            if hasattr(self, "build_label"):
                self.build_label.set_text(f"ComfyUI git: {s.git_head} • App: {VERSION}")
            if full and hasattr(self, "inventory_label"):
                self.inventory_label.set_text(
                    f"Canonical media model inventory: {s.model_count} model files • {fmt_bytes(s.model_size)}"
                )
            if hasattr(self, "log_view"):
                self.refresh_log()
            if hasattr(self, "create_queue_btn"):
                self.create_mode_changed()
        except Exception:
            write_crash(traceback.format_exc(), "runtime status update")
        return False

    def start_runtime(self):
        comfy_integration.ensure_bridge()
        s = collect_status(self.cfg)
        if s.state == "RUNNING":
            self.dialog("Already running", s.detail)
            return
        if s.state == "PORT CONFLICT":
            self.dialog("Port conflict", s.detail, Gtk.MessageType.ERROR)
            return
        if s.pids:
            self.dialog("Runtime already starting", s.detail)
            return

        def task():
            if START_HELPER.exists():
                return run_text(["bash", str(START_HELPER)], timeout=30)
            if FALLBACK_START.exists():
                log = LOG_ROOT / f"comfyui-control-{datetime.now():%Y%m%d-%H%M%S}.log"
                LOG_ROOT.mkdir(parents=True, exist_ok=True)
                with open(log, "ab") as fh:
                    subprocess.Popen(
                        ["bash", str(FALLBACK_START)],
                        cwd=RUNTIMES,
                        stdout=fh,
                        stderr=subprocess.STDOUT,
                        start_new_session=True,
                    )
                return 0, f"Started via {FALLBACK_START}"
            return 1, "No known ComfyUI start launcher was found."

        def done(result):
            rc, out = result
            if rc != 0:
                self.dialog("Start failed", out or f"Exit code {rc}", Gtk.MessageType.ERROR)
            else:
                notify("Starting ComfyUI", out or "Waiting for runtime health.")
        self.background(task, done, "Starting ComfyUI…")

    def stop_runtime(self):
        s = collect_status(self.cfg)
        if not s.pids:
            self.dialog("Already stopped", "No ComfyUI runtime process was found.")
            return

        def task():
            if STOP_HELPER.exists():
                rc, out = run_text(["bash", str(STOP_HELPER)], timeout=20)
                # Verify actual state. Only touch exact identified ComfyUI PIDs.
                for _ in range(20):
                    if not comfy_pids():
                        return rc, out or "Stopped via qualification helper."
                    time.sleep(0.25)
            for pid in comfy_pids():
                try:
                    os.kill(pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            for _ in range(24):
                if not comfy_pids():
                    return 0, "ComfyUI stopped."
                time.sleep(0.25)
            return 2, "ComfyUI did not exit after SIGTERM. It was not force-killed."

        def done(result):
            rc, out = result
            if rc != 0:
                self.dialog("Stop incomplete", out, Gtk.MessageType.WARNING)
            else:
                notify("ComfyUI stopped", out)
        self.background(task, done, "Stopping ComfyUI…")

    def restart_runtime(self):
        if not comfy_pids():
            self.start_runtime()
            return
        def task():
            if STOP_HELPER.exists():
                run_text(["bash", str(STOP_HELPER)], timeout=20)
            else:
                for pid in comfy_pids():
                    try:
                        os.kill(pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
            for _ in range(30):
                if not comfy_pids():
                    break
                time.sleep(0.25)
            if comfy_pids():
                return 2, "Existing ComfyUI process did not stop. Restart aborted."
            if START_HELPER.exists():
                return run_text(["bash", str(START_HELPER)], timeout=30)
            if FALLBACK_START.exists():
                log = LOG_ROOT / f"comfyui-control-{datetime.now():%Y%m%d-%H%M%S}.log"
                LOG_ROOT.mkdir(parents=True, exist_ok=True)
                with open(log, "ab") as fh:
                    subprocess.Popen(
                        ["bash", str(FALLBACK_START)],
                        cwd=RUNTIMES,
                        stdout=fh,
                        stderr=subprocess.STDOUT,
                        start_new_session=True,
                    )
                return 0, "Restarted."
            return 1, "No start helper found."
        def done(result):
            rc, out = result
            if rc != 0:
                self.dialog("Restart failed", out, Gtk.MessageType.ERROR)
            else:
                notify("ComfyUI restarting", out)
        self.background(task, done, "Restarting ComfyUI…")

    def toggle_errors(self, btn):
        self.log_errors_only = btn.get_active()
        self.refresh_log()

    def refresh_log(self):
        p = latest_log()
        if not p:
            self.log_path_label.set_text("No ComfyUI log found")
            self.log_view.get_buffer().set_text("")
            return
        self.log_path_label.set_text(str(p))
        try:
            lines = p.read_text(errors="replace").splitlines()[-int(self.cfg.get("log_lines", 350)):]
            if self.log_errors_only:
                keys = ("error", "traceback", "failed", "exception", "warning")
                lines = [x for x in lines if any(k in x.lower() for k in keys)]
            text = "\n".join(lines)
        except Exception as e:
            text = str(e)
        buf = self.log_view.get_buffer()
        buf.set_text(text)
        mark = buf.create_mark(None, buf.get_end_iter(), False)
        self.log_view.scroll_to_mark(mark, 0.05, True, 0, 1)

    def set_utility_output(self, text):
        self.utility_output.get_buffer().set_text(str(text))

    def open_crash_log(self):
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        if not LAST_CRASH_LOG.exists():
            LAST_CRASH_LOG.write_text("No crash has been recorded yet.\n")
        open_path(CACHE_DIR)
        self.set_utility_output(
            f"Latest crash:\n{LAST_CRASH_LOG}\n\nCumulative Python log:\n{CRASH_LOG}"
        )

    def health_check(self):
        def task():
            s = collect_status(self.cfg, include_inventory=True)
            checks = [
                ("ComfyUI directory", COMFY.exists(), str(COMFY)),
                ("Python venv", (COMFY / ".venv/bin/python").exists(), str(COMFY / ".venv/bin/python")),
                ("Start helper", START_HELPER.exists(), str(START_HELPER)),
                ("Stop helper", STOP_HELPER.exists(), str(STOP_HELPER)),
                ("Port reachable", s.port, f"{self.cfg['host']}:{self.cfg['port']}"),
                ("HTTP healthy", s.http, self.cfg["browser_url"]),
                ("Model root", MODEL_ROOT.exists(), str(MODEL_ROOT)),
                ("Preset root", PRESET_ROOT.exists(), str(PRESET_ROOT)),
            ]
            lines = ["SUPERIOR MI LABS / COMFYUI HEALTH CHECK", "=" * 48]
            for name, ok, detail in checks:
                lines.append(f"{'PASS' if ok else 'FAIL':4}  {name:20}  {detail}")
            lines += [
                "",
                f"Runtime state: {s.state}",
                f"PIDs: {s.pids or 'none'}",
                f"ComfyUI git: {s.git_head}",
                f"GPU: {s.gpu_name}",
                f"VRAM: {fmt_bytes(s.gpu_used)} / {fmt_bytes(s.gpu_total)}",
                f"Models: {s.model_count} files / {fmt_bytes(s.model_size)}",
            ]
            return 0, "\n".join(lines)
        self.background(task, lambda r: self.set_utility_output(r[1]), "Running health check…")

    def export_diagnostics(self):
        def task():
            d = HOME / "Downloads"
            d.mkdir(parents=True, exist_ok=True)
            out = d / f"Superior-MI-ComfyUI-Diagnostics-{datetime.now():%Y%m%d-%H%M%S}.txt"
            sections = []
            def add(title, cmd, cwd=None):
                rc, txt = run_text(cmd, timeout=20, cwd=cwd)
                sections.append(f"\n=== {title} (rc={rc}) ===\n{txt}\n")
            sections.append(f"{APP_NAME} diagnostics\nGenerated: {datetime.now().isoformat()}\n")
            add("NVIDIA", ["nvidia-smi"])
            if COMFY.exists():
                add("GIT STATUS", ["git", "status", "--short", "--branch"], COMFY)
                add("GIT HEAD", ["git", "rev-parse", "HEAD"], COMFY)
            py = COMFY / ".venv/bin/python"
            if py.exists():
                add("PYTHON/TORCH", [str(py), "-c",
                    "import sys; print(sys.version); "
                    "import torch; print('torch',torch.__version__); "
                    "print('torch cuda',torch.version.cuda); "
                    "print('cuda available',torch.cuda.is_available())"])
            add("PORT", ["bash", "-lc", f"ss -ltnp | grep ':{int(self.cfg['port'])} ' || true"])
            sections.append("\n=== PROCESS ===\n" + "\n".join(
                f"{pid}: {process_cmdline(pid)}" for pid in comfy_pids()
            ) + "\n")
            lp = latest_log()
            if lp:
                try:
                    tail = "\n".join(lp.read_text(errors="replace").splitlines()[-300:])
                    sections.append(f"\n=== LATEST LOG: {lp} ===\n{tail}\n")
                except Exception as e:
                    sections.append(f"\n=== LOG ERROR ===\n{e}\n")
            out.write_text("".join(sections))
            return 0, str(out)
        def done(result):
            self.set_utility_output(f"Diagnostics written to:\n{result[1]}")
            notify("Diagnostics exported", result[1])
        self.background(task, done, "Exporting diagnostics…")

    def pip_check(self):
        py = COMFY / ".venv/bin/python"
        uv = shutil.which("uv") or str(HOME / ".local/bin/uv")
        if not py.exists():
            self.dialog("Python venv missing", str(py), Gtk.MessageType.ERROR)
            return
        def task():
            if Path(uv).exists() or shutil.which("uv"):
                return run_text([uv, "pip", "check", "--python", str(py)], timeout=45)
            return 1, "uv was not found."
        self.background(task, lambda r: self.set_utility_output(r[1] or "Package check passed."), "Checking Python packages…")

    def port_diagnostics(self):
        def task():
            cmd = ["bash", "-lc", f"ss -ltnp | grep ':{int(self.cfg['port'])} ' || true; "
                                     f"echo; pgrep -af 'python.*main.py' || true"]
            return run_text(cmd, timeout=8)
        self.background(task, lambda r: self.set_utility_output(r[1] or "No listener/process found."), "Inspecting port…")

    def repair_gguf(self):
        if comfy_pids():
            self.dialog("Stop ComfyUI first", "Repair is intentionally blocked while the runtime is active.", Gtk.MessageType.WARNING)
            return
        node = COMFY / "custom_nodes/ComfyUI-GGUF"
        req = node / "requirements.txt"
        py = COMFY / ".venv/bin/python"
        uv = shutil.which("uv") or str(HOME / ".local/bin/uv")
        if not req.exists() or not py.exists():
            self.dialog("GGUF repair unavailable", f"Missing:\n{req}\nor\n{py}", Gtk.MessageType.ERROR)
            return
        if not self.confirm("Repair GGUF dependencies?", "Installs only ComfyUI-GGUF's declared requirements into the existing ComfyUI venv using uv."):
            return
        def task():
            return run_text([uv, "pip", "install", "--python", str(py), "-r", str(req)], timeout=300)
        self.background(task, lambda r: self.set_utility_output(r[1]), "Repairing GGUF dependencies…")

    def repair_desktop(self):
        if SYSTEM_INSTALL:
            self.dialog("System package installation", "This copy is installed system-wide. Reinstall the .deb package to repair the launcher or icon; your ComfyUI/model data will not be touched.")
            return
        installer = INSTALL_ROOT / "install.sh"
        if not installer.exists():
            self.dialog("Installer missing", str(installer), Gtk.MessageType.ERROR)
            return
        def task():
            return run_text(["bash", str(installer), "--repair"], timeout=40)
        self.background(task, lambda r: self.set_utility_output(r[1]), "Repairing desktop integration…")

    def git_state(self):
        if not COMFY.exists():
            self.dialog("ComfyUI missing", str(COMFY), Gtk.MessageType.ERROR)
            return
        def task():
            rc, a = run_text(["git", "status", "--short", "--branch"], cwd=COMFY)
            _, b = run_text(["git", "remote", "-v"], cwd=COMFY)
            _, c = run_text(["git", "log", "-1", "--oneline", "--decorate"], cwd=COMFY)
            return rc, f"{a}\n\n{c}\n\n{b}"
        self.background(task, lambda r: self.set_utility_output(r[1]), "Inspecting git state…")

    def export_repro_snapshot(self):
        def task():
            out=HOME/'Downloads'/f"Superior-MI-ComfyUI-Snapshot-{datetime.now():%Y%m%d-%H%M%S}.json"; out.parent.mkdir(parents=True,exist_ok=True)
            snap={"generated":datetime.now().isoformat(),"app_version":VERSION,"runtime":{"comfy":str(COMFY),"git_head":"","git_status":""},"custom_nodes":[],"models":model_library.scan(),"settings":self.cfg}
            if COMFY.exists():
                _,snap['runtime']['git_head']=run_text(['git','rev-parse','HEAD'],cwd=COMFY); _,snap['runtime']['git_status']=run_text(['git','status','--short','--branch'],cwd=COMFY)
                cn=COMFY/'custom_nodes'
                if cn.exists():
                    for d in sorted(cn.iterdir()):
                        if not d.is_dir(): continue
                        row={"name":d.name,"path":str(d)}
                        if (d/'.git').exists():
                            _,row['head']=run_text(['git','rev-parse','HEAD'],cwd=d); _,row['remote']=run_text(['git','remote','get-url','origin'],cwd=d)
                        snap['custom_nodes'].append(row)
            out.write_text(json.dumps(snap,indent=2)+"\n"); return 0,str(out)
        self.background(task,lambda r:self.set_utility_output('Snapshot written to:\n'+r[1]),'Exporting reproducibility snapshot…')

    def check_comfy_updates(self):
        if not (COMFY/'.git').exists(): self.dialog('Not a Git checkout',str(COMFY),Gtk.MessageType.WARNING); return
        def task():
            rc,a=run_text(['git','fetch','--quiet','origin'],timeout=45,cwd=COMFY)
            if rc: return rc,a
            _,branch=run_text(['git','branch','--show-current'],cwd=COMFY); _,local=run_text(['git','rev-parse','HEAD'],cwd=COMFY)
            _,upstream=run_text(['git','rev-parse','@{u}'],cwd=COMFY)
            _,counts=run_text(['git','rev-list','--left-right','--count','HEAD...@{u}'],cwd=COMFY)
            return 0,f"Branch: {branch}\nLocal: {local}\nUpstream: {upstream}\nAhead/behind: {counts}\n\nNo update is applied automatically."
        self.background(task,lambda r:self.set_utility_output(r[1]),'Checking upstream ComfyUI…')

    def repair_hf_cli(self):
        if not self.confirm(
            "Install / repair Hugging Face CLI?",
            "Creates an isolated helper environment for the Hugging Face CLI. It does not modify the ComfyUI virtual environment. If uv is installed it is used; otherwise a small Python venv is created under the Workstation data directory."
        ):
            return
        def task():
            uv = shutil.which("uv") or str(HOME / ".local/bin/uv")
            if shutil.which("uv") or Path(uv).exists():
                return run_text([uv, "tool", "install", "--force", "huggingface_hub"], timeout=240)
            toolenv = HOME / ".local/share/superior-mi-comfyui-tools/hf-cli-venv"
            bindir = HOME / ".local/bin"
            bindir.mkdir(parents=True, exist_ok=True)
            rc, out = run_text(["python3", "-m", "venv", str(toolenv)], timeout=120)
            if rc:
                return rc, out
            rc, out2 = run_text([
                str(toolenv / "bin/python"), "-m", "pip", "install", "--upgrade", "pip", "huggingface_hub"
            ], timeout=300)
            if rc:
                return rc, out + "\n" + out2
            hf = toolenv / "bin/hf"
            if not hf.exists():
                return 1, "huggingface_hub installed but hf executable was not found."
            target = bindir / "hf"
            if target.exists() or target.is_symlink():
                target.unlink()
            target.symlink_to(hf)
            return 0, (out + "\n" + out2 + "\nInstalled helper: " + str(target)).strip()
        self.background(
            task,
            lambda r: self.set_utility_output(r[1] or "Hugging Face CLI installed."),
            "Installing Hugging Face CLI…"
        )

    def clear_temp(self):
        if not TEMP_ROOT.exists():
            self.set_utility_output("No ComfyUI temp directory exists.")
            return
        if comfy_pids():
            self.dialog("Stop ComfyUI first", "Temp cleanup is blocked while ComfyUI is active.", Gtk.MessageType.WARNING)
            return
        if not self.confirm("Clear ComfyUI temp files?", f"This deletes contents of:\n{TEMP_ROOT}\n\nOutputs and models are not touched."):
            return
        def task():
            removed = 0
            for p in TEMP_ROOT.iterdir():
                try:
                    if p.is_dir() and not p.is_symlink():
                        shutil.rmtree(p)
                    else:
                        p.unlink()
                    removed += 1
                except Exception:
                    pass
            return 0, f"Removed {removed} temp entries from {TEMP_ROOT}"
        self.background(task, lambda r: self.set_utility_output(r[1]), "Clearing temp files…")

    def clean_old_logs(self):
        if not LOG_ROOT.exists():
            self.set_utility_output("No log directory exists.")
            return
        if not self.confirm("Remove old logs?", "Deletes ComfyUI qualification logs older than 30 days. Recent logs are preserved."):
            return
        def task():
            cutoff = time.time() - 30 * 86400
            removed = []
            for p in LOG_ROOT.glob("comfyui-*.log"):
                try:
                    if p.stat().st_mtime < cutoff:
                        p.unlink()
                        removed.append(p.name)
                except OSError:
                    pass
            return 0, f"Removed {len(removed)} old logs." + (("\n" + "\n".join(removed)) if removed else "")
        self.background(task, lambda r: self.set_utility_output(r[1]), "Cleaning old logs…")

    def reset_settings(self):
        if not self.confirm("Reset Control Center settings?", "Resets host, port, browser URL and refresh interval to defaults."):
            return
        self.cfg = dict(DEFAULT_CONFIG)
        save_config(self.cfg)
        self.host_entry.set_text(self.cfg["host"])
        self.port_spin.set_value(self.cfg["port"])
        self.url_entry.set_text(self.cfg["browser_url"])
        self.refresh_spin.set_value(self.cfg["refresh_seconds"])
        self.set_utility_output("Settings reset to defaults.")

    def uninstall_self(self):
        if not self.confirm(
            "Uninstall Workstation?",
            "Removes only the Superior MI Labs Workstation application. ComfyUI, models, presets, outputs and Qualification data are preserved."
        ):
            return
        if SYSTEM_INSTALL:
            if shutil.which("pkexec"):
                subprocess.Popen(["pkexec", "apt-get", "remove", "-y", "superior-mi-comfyui-workstation"], start_new_session=True)
                self.get_application().quit()
            else:
                self.dialog("Administrator helper unavailable", "Remove the package with:\n\nsudo apt remove superior-mi-comfyui-workstation", Gtk.MessageType.WARNING)
            return
        script = INSTALL_ROOT / "uninstall.sh"
        if not script.exists():
            self.dialog("Uninstaller missing", str(script), Gtk.MessageType.ERROR)
            return
        subprocess.Popen(
            ["bash", "-lc", f"sleep 1; bash {json.dumps(str(script))}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        self.get_application().quit()

    def save_settings(self):
        self.cfg["host"] = self.host_entry.get_text().strip() or "127.0.0.1"
        self.cfg["port"] = int(self.port_spin.get_value())
        self.cfg["browser_url"] = self.url_entry.get_text().strip() or f"http://{self.cfg['host']}:{self.cfg['port']}"
        self.cfg["refresh_seconds"] = int(self.refresh_spin.get_value())
        self.cfg["auto_benchmark"] = bool(self.auto_bench_check.get_active())
        self.cfg["splash"] = bool(self.splash_check.get_active())
        save_config(self.cfg)
        self.dialog("Settings saved", "Runtime monitoring will use the new values.")
        self.refresh(full=True)

class App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)

    def do_startup(self):
        Gtk.Application.do_startup(self)
        try:
            provider = Gtk.CssProvider()
            provider.load_from_data(CSS)
            screen = Gdk.Screen.get_default()
            if screen is not None:
                Gtk.StyleContext.add_provider_for_screen(
                    screen,
                    provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
                )
        except Exception:
            # Styling must never be able to prevent the application from opening.
            write_crash(traceback.format_exc(), "GTK CSS startup")

    def _show_recovery(self, text):
        try:
            RecoveryWindow(self, text).present()
        except Exception:
            write_crash(traceback.format_exc(), "recovery window")
            self.quit()

    def _open_main(self, splash=None):
        try:
            if splash is not None:
                splash.destroy()
            w = AppWindow(self)
            w.present()
        except Exception:
            text = traceback.format_exc()
            write_crash(text, "main window startup")
            try:
                if splash is not None:
                    splash.destroy()
            except Exception:
                pass
            self._show_recovery(text)
        return False

    def do_activate(self):
        win = self.props.active_window
        if win:
            win.present()
            return
        startup_guard.stage("activate", "opening main window directly")
        self._open_main()

if __name__ == "__main__":
    install_exception_hook()
    startup_guard.stage("python-main", "GTK application starting")
    try:
        rc = App().run([arg for arg in sys.argv if arg != "--safe"])
    except Exception:
        write_crash(traceback.format_exc(), "top-level application")
        raise
    sys.exit(rc)
