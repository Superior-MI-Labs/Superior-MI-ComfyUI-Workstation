#!/usr/bin/env bash
set -euo pipefail

REPO="Superior-MI-Labs/Superior-MI-ComfyUI-Workstation"
TAG="v3.0.3-beta.1"
TITLE="Superior MI Labs ComfyUI Workstation v3.0.3 Public Beta"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOWNLOADS="$HOME/Downloads"
DEB="$DOWNLOADS/Superior-MI-Labs-ComfyUI-Workstation_3.0.3_all.deb"
ZIP="$DOWNLOADS/Superior-MI-Labs-ComfyUI-Workstation-v3.0.3-public-beta.zip"

for cmd in gh git rsync sha256sum zip; do
  command -v "$cmd" >/dev/null || { echo "ERROR: missing $cmd"; exit 1; }
done
gh auth status

[[ -f "$DEB" ]] || { echo "ERROR: missing $DEB"; exit 1; }

# Build the exact public source bundle from this tree.
rm -f "$ZIP"
(
  cd "$(dirname "$HERE")"
  zip -qr "$ZIP" "$(basename "$HERE")" -x '*/__pycache__/*' '*.pyc'
)

DEB_SHA="$(sha256sum "$DEB" | awk '{print $1}')"
ZIP_SHA="$(sha256sum "$ZIP" | awk '{print $1}')"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

gh repo clone "$REPO" "$TMP/repo"
rsync -a --delete --exclude='.git' "$HERE/" "$TMP/repo/"

cd "$TMP/repo"

python3 - "$DEB_SHA" "$ZIP_SHA" <<'PY'
import json, pathlib, sys
deb_sha, zip_sha = sys.argv[1:3]
p = pathlib.Path("update.json")
d = json.loads(p.read_text())
d.update({
    "version": "3.0.3",
    "channel": "public-beta",
    "status": "public beta",
    "deb_url": "https://github.com/Superior-MI-Labs/Superior-MI-ComfyUI-Workstation/releases/download/v3.0.3-beta.1/Superior-MI-Labs-ComfyUI-Workstation_3.0.3_all.deb",
    "zip_url": "https://github.com/Superior-MI-Labs/Superior-MI-ComfyUI-Workstation/releases/download/v3.0.3-beta.1/Superior-MI-Labs-ComfyUI-Workstation-v3.0.3-public-beta.zip",
    "sha256": {"deb": deb_sha, "zip": ""},
    "notes": "First public beta. Linux-first. Major GUI and Blueprint/template visual overhaul planned."
})
p.write_text(json.dumps(d, indent=2) + "\n")
PY

git add -A
if ! git diff --cached --quiet; then
  git commit -m "Publish v3.0.3 public beta source"
  git push origin main
fi

if gh release view "$TAG" --repo "$REPO" >/dev/null 2>&1; then
  gh release edit "$TAG" --repo "$REPO" --title "$TITLE" --notes-file RELEASE_NOTES_v3.0.3-beta.1.md --prerelease
else
  gh release create "$TAG" --repo "$REPO" --target main --title "$TITLE" --notes-file RELEASE_NOTES_v3.0.3-beta.1.md --prerelease
fi

gh release upload "$TAG" --repo "$REPO" \
  "$DEB#Linux Mint / Ubuntu / Debian package" \
  "$ZIP#Full public-beta source bundle" \
  --clobber

echo
echo "=== PUBLIC BETA RELEASE ==="
gh release view "$TAG" --repo "$REPO" --json url,name,tagName,isPrerelease
echo
echo "DEB SHA256: $DEB_SHA"
echo "ZIP SHA256: $ZIP_SHA"
