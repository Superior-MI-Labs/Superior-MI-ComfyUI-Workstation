#!/usr/bin/env bash
set -euo pipefail

REPO="Superior-MI-Labs/Superior-MI-ComfyUI-Workstation"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SEED="$ROOT/repo_seed"

command -v gh >/dev/null 2>&1 || {
  echo "ERROR: GitHub CLI (gh) is not installed."
  exit 1
}

gh auth status

if gh repo view "$REPO" >/dev/null 2>&1; then
  echo "Repository already exists: https://github.com/$REPO"
  exit 0
fi

gh repo create "$REPO" \
  --public \
  --description "Development repository for the Superior MI Labs ComfyUI Workstation. Pre-release; official release pending qualification."

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
cp -a "$SEED"/. "$TMP"/
cd "$TMP"
git init -b main
git add .
git -c user.name="Superior MI Labs" -c user.email="noreply@superior-mi.local" commit -m "Initialize pre-release Workstation repository"
git remote add origin "https://github.com/$REPO.git"
git push -u origin main

echo "Created: https://github.com/$REPO"
