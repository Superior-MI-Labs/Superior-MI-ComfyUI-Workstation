#!/usr/bin/env bash
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPAIR=0
if [[ "${1:-}" == "--repair" ]]; then REPAIR=1; fi
DEST="$HOME/.local/share/superior-mi-comfyui-control"
BIN="$HOME/.local/bin/smi-comfyui"
DESKTOP="$HOME/.local/share/applications/superior-mi-comfyui.desktop"
ICON_BASE="$HOME/.local/share/icons/hicolor"

printf '%s\n' "==================================================" \
  " SUPERIOR MI LABS - COMFYUI WORKSTATION v3.0" \
  "=================================================="

missing=()
python3 - <<'PY' >/dev/null 2>&1 || missing+=("python3-gi" "gir1.2-gtk-3.0")
import gi
gi.require_version("Gtk","3.0")
from gi.repository import Gtk, GdkPixbuf
PY
python3 - <<'PY' >/dev/null 2>&1 || missing+=("python3-cairo")
import cairo
PY
python3 - <<'PY' >/dev/null 2>&1 || missing+=("python3-websocket")
import websocket
PY
python3 -m venv --help >/dev/null 2>&1 || missing+=("python3-venv")
command -v xdg-open >/dev/null 2>&1 || missing+=("xdg-utils")
command -v curl >/dev/null 2>&1 || missing+=("curl")
command -v pgrep >/dev/null 2>&1 || missing+=("procps")
command -v git >/dev/null 2>&1 || missing+=("git")
command -v ffmpeg >/dev/null 2>&1 || missing+=("ffmpeg")
command -v notify-send >/dev/null 2>&1 || missing+=("libnotify-bin")
command -v zenity >/dev/null 2>&1 || missing+=("zenity")

if ((${#missing[@]})); then
  echo
  echo "Installing required desktop/runtime packages:"
  printf '  %s\n' "${missing[@]}"
  sudo apt-get update
  sudo apt-get install -y "${missing[@]}"
fi

mkdir -p \
  "$HOME/.local/bin" \
  "$HOME/.local/share/applications" \
  "$ICON_BASE/512x512/apps" \
  "$ICON_BASE/256x256/apps" \
  "$ICON_BASE/128x128/apps" \
  "$ICON_BASE/64x64/apps" \
  "$ICON_BASE/48x48/apps" \
  "$ICON_BASE/32x32/apps" \
  "$HOME/.config/superior-mi-comfyui-control" \
  "$HOME/.cache/superior-mi-comfyui-workstation"

if [[ $REPAIR -eq 0 ]]; then
  rm -rf "$DEST"
  mkdir -p "$DEST"
  cp -a "$SRC"/. "$DEST"/
else
  test -d "$DEST" || { echo "ERROR: installed application directory is missing: $DEST"; exit 1; }
fi
chmod +x "$DEST/app/main.py" "$DEST/install.sh" "$DEST/uninstall.sh"

cat > "$BIN" <<EOF
#!/usr/bin/env bash
set -uo pipefail
APP="$DEST/app/main.py"
DIAG="$DEST/app/diagnostics.py"
LOGDIR="\$HOME/.cache/superior-mi-comfyui-workstation"
mkdir -p "\$LOGDIR"
if [[ "\${1:-}" == "--diagnose" ]]; then
  shift
  /usr/bin/python3 "\$DIAG" "\$@"
  exit \$?
fi
LOG="\$LOGDIR/launcher-\$(date +%Y%m%d-%H%M%S).log"
ln -sfn "\$LOG" "\$LOGDIR/last-run.log" 2>/dev/null || true
/usr/bin/python3 "\$APP" "\$@" >>"\$LOG" 2>&1
rc=\$?
if [[ \$rc -ne 0 ]]; then
  cp -f "\$LOG" "\$LOGDIR/last-crash.log" 2>/dev/null || true
  if command -v zenity >/dev/null 2>&1; then
    zenity --error \
      --title="Superior MI Labs - ComfyUI Workstation" \
      --width=520 \
      --text="The Workstation hit an error and closed.\n\nCrash log:\n\$LOGDIR/last-crash.log\n\nTry the Safe Mode launcher from the application menu, or open the log from Utilities after it starts."
  elif command -v notify-send >/dev/null 2>&1; then
    notify-send "Superior MI Labs - ComfyUI Workstation" "Startup failed. See \$LOGDIR/last-crash.log"
  fi
fi
exit \$rc
EOF
chmod +x "$BIN"

cp -f "$DEST/assets/superior-mi-comfyui.png" "$ICON_BASE/512x512/apps/superior-mi-comfyui.png"
for sz in 256 128 64 48 32; do
  cp -f "$DEST/assets/superior-mi-comfyui-${sz}.png" "$ICON_BASE/${sz}x${sz}/apps/superior-mi-comfyui.png"
done

cat > "$DESKTOP" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=Superior MI Labs - ComfyUI Workstation
GenericName=Local AI Media Workstation
Comment=Install, start, monitor, maintain and explore local ComfyUI model stacks
Exec=$BIN
Icon=superior-mi-comfyui
Terminal=false
Categories=Graphics;Utility;Development;
Keywords=ComfyUI;AI;Superior MI;Image;Video;GPU;Kisha;
StartupNotify=true
StartupWMClass=com.superiormi.labs.comfyui
Actions=SafeMode;OpenUI;Models;Outputs;

[Desktop Action SafeMode]
Name=Open Workstation in Safe Mode
Exec=$BIN --safe

[Desktop Action OpenUI]
Name=Open ComfyUI Web UI
Exec=xdg-open http://127.0.0.1:8188

[Desktop Action Models]
Name=Open Model Library
Exec=xdg-open $HOME/Models/Media

[Desktop Action Outputs]
Name=Open ComfyUI Outputs
Exec=xdg-open $HOME/Projects/AI-Runtimes/ComfyUI/output
EOF

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$HOME/.local/share/applications" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -f "$ICON_BASE" >/dev/null 2>&1 || true
fi

PRESET_DST="$HOME/Projects/AI-Runtimes/Qualification/presets/Superior-MI-Labs"
if [[ -d "$DEST/preset_library" ]]; then
  mkdir -p "$PRESET_DST"
  cp -a "$DEST/preset_library"/. "$PRESET_DST"/
  rm -f "$PRESET_DST/index.json"
fi

# Seed the starter character library without overwriting user changes.
CHAR_SRC="$DEST/assets/characters/bundled"
CHAR_DST="$HOME/Models/Media/Characters/Superior-MI-Labs"
if [[ -d "$CHAR_SRC" ]]; then
  while IFS= read -r -d '' src; do
    rel="${src#"$CHAR_SRC"/}"
    dst="$CHAR_DST/$rel"
    mkdir -p "$(dirname "$dst")"
    if [[ ! -e "$dst" ]]; then
      cp -a "$src" "$dst"
    fi
  done < <(find "$CHAR_SRC" -type f -print0)
fi

echo
echo "PASS: Superior MI Labs - ComfyUI Workstation installed"
echo "Start menu: Superior MI Labs - ComfyUI Workstation"
echo "CLI: smi-comfyui"
echo "Safe mode: smi-comfyui --safe"
echo
echo "New users: open the app and choose Guided Setup."
