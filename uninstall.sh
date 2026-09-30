#!/usr/bin/env bash
set -euo pipefail
DEST="$HOME/.local/share/superior-mi-comfyui-control"
rm -f "$HOME/.local/bin/smi-comfyui"
rm -f "$HOME/.local/share/applications/superior-mi-comfyui.desktop"
for sz in 512 256 128 64 48 32; do
  rm -f "$HOME/.local/share/icons/hicolor/${sz}x${sz}/apps/superior-mi-comfyui.png"
done
rm -rf "$HOME/.config/superior-mi-comfyui-control"
rm -rf "$HOME/.cache/superior-mi-comfyui-workstation"
if [[ -d "$DEST" ]]; then
  (sleep 1; rm -rf "$DEST") >/dev/null 2>&1 &
fi
echo "PASS: Workstation removed."
echo "ComfyUI, models, presets, outputs, and Qualification data were preserved."
