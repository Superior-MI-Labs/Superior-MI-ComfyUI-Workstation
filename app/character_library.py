from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

HOME = Path.home()
APP_ROOT = Path(__file__).resolve().parent.parent
BUNDLED_ROOT = APP_ROOT / "assets" / "characters" / "bundled"
USER_ROOT = HOME / "Models" / "Media" / "Characters"
BUNDLED_USER_ROOT = USER_ROOT / "Superior MI Characters"
LEGACY_BUNDLED_USER_ROOT = USER_ROOT / "Superior-MI-Labs"
COMFY_INPUT = HOME / "Projects" / "AI-Runtimes" / "ComfyUI" / "input"
SUPPORTED = {".png", ".jpg", ".jpeg", ".webp"}
IGNORED_DIRS = {".thumbs", ".cache", "__pycache__"}

@dataclass(frozen=True)
class Character:
    uid: str
    name: str
    image_path: Path
    relative_path: str
    source_root: str
    collection: str = ""
    kind: str = ""
    role: str = ""
    identity: str = ""
    pronouns: str = ""
    body_type: str = ""
    species: str = ""
    description: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)
    metadata_path: Path | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def group(self) -> str:
        return self.kind or "Other"


def _pretty_name(stem: str) -> str:
    text = stem.replace("_", " ").replace("-", " ")
    # Strip common asset suffixes so filename-only users still get sane names.
    suffixes = [
        "character sheet", "reference sheet", "concept sheet", "field guide",
        "futuristic character design sheet", "techwear character sheet",
        "sci fi character sheet", "cyber fashion character sheet",
        "cybertech field engineer", "futuristic security specialist",
        "arctic operations character sheet", "arctic explorer reference sheet",
        "futuristic interface strategist", "field logistics character sheet",
        "logistics character sheet", "futuristic streetwear concept sheet",
    ]
    low = text.lower().strip()
    for suffix in sorted(suffixes, key=len, reverse=True):
        if low.endswith(" " + suffix):
            text = text[: -(len(suffix) + 1)]
            break
    return " ".join(w.capitalize() for w in text.split()) or stem


def _safe_json(path: Path) -> tuple[dict, list[str]]:
    warnings: list[str] = []
    if not path.exists():
        return {}, warnings
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            warnings.append("Metadata sidecar is not a JSON object; ignored.")
            return {}, warnings
        return raw, warnings
    except Exception as exc:
        warnings.append(f"Metadata sidecar could not be read: {exc}")
        return {}, warnings


def _uid_for(path: Path, root: Path, meta: dict) -> str:
    explicit = str(meta.get("id") or "").strip()
    if explicit:
        return explicit
    rel = str(path.relative_to(root)).replace("\\", "/")
    return hashlib.sha1((str(root) + "::" + rel).encode("utf-8")).hexdigest()[:16]


def _iter_images(root: Path) -> Iterable[Path]:
    if not root.exists():
        return
    for p in sorted(root.rglob("*")):
        try:
            if any(part in IGNORED_DIRS or part.startswith(".") for part in p.relative_to(root).parts[:-1]):
                continue
            if p.is_file() and p.suffix.lower() in SUPPORTED and not p.name.startswith("."):
                yield p
        except (OSError, ValueError):
            continue


def _read_character(path: Path, root: Path, source_root: str) -> Character:
    meta_path = path.with_suffix(".json")
    meta, warnings = _safe_json(meta_path)
    rel = str(path.relative_to(root)).replace("\\", "/")
    inferred_kind = path.parent.name if path.parent != root else "Other"
    name = str(meta.get("name") or _pretty_name(path.stem)).strip()
    tags = meta.get("tags", [])
    if not isinstance(tags, list):
        tags = [str(tags)]
    return Character(
        uid=_uid_for(path, root, meta),
        name=name,
        image_path=path,
        relative_path=rel,
        source_root=source_root,
        collection=(
            "Superior MI Characters"
            if source_root == "bundled" or (source_root == "user" and (BUNDLED_USER_ROOT in path.parents or LEGACY_BUNDLED_USER_ROOT in path.parents) and str(meta.get("collection") or "") in ("", "Superior MI Labs", "Superior-MI-Labs"))
            else str(meta.get("collection") or path.parent.name).strip()
        ),
        kind=str(meta.get("kind") or inferred_kind).strip(),
        role=str(meta.get("role") or "").strip(),
        identity=str(meta.get("identity") or "").strip(),
        pronouns=str(meta.get("pronouns") or "").strip(),
        body_type=str(meta.get("body_type") or "").strip(),
        species=str(meta.get("species") or "").strip(),
        description=str(meta.get("description") or "").strip(),
        tags=tuple(str(x).strip() for x in tags if str(x).strip()),
        metadata_path=meta_path if meta_path.exists() else None,
        warnings=tuple(warnings),
    )


def scan_characters(include_bundled_fallback: bool = True) -> list[Character]:
    """Scan user character roots recursively.

    User files win over bundled files with the same relative path or metadata id. This means
    upgrades can ship starter characters without preventing users from replacing or extending them.
    """
    results: list[Character] = []
    seen_uid: set[str] = set()
    seen_rel: set[str] = set()

    roots: list[tuple[str, Path]] = [("user", USER_ROOT)]
    if include_bundled_fallback:
        roots.append(("bundled", BUNDLED_ROOT))

    for label, root in roots:
        for p in _iter_images(root) or []:
            c = _read_character(p, root, label)
            relkey = c.relative_path.lower()
            # User copy of a bundled path wins. Explicit metadata id also deduplicates.
            if c.uid in seen_uid or relkey in seen_rel:
                continue
            results.append(c)
            seen_uid.add(c.uid)
            seen_rel.add(relkey)
    results.sort(key=lambda c: (c.kind.lower(), c.name.lower(), c.relative_path.lower()))
    return results


def seed_bundled_characters(overwrite: bool = False) -> list[Path]:
    """Copy bundled starter characters into the persistent character library.

    Existing user files are never overwritten unless explicitly requested.
    """
    written: list[Path] = []
    if not BUNDLED_ROOT.exists():
        return written
    # One-time, non-destructive migration from the pre-3.0 starter collection name.
    if LEGACY_BUNDLED_USER_ROOT.exists() and not BUNDLED_USER_ROOT.exists():
        try:
            LEGACY_BUNDLED_USER_ROOT.rename(BUNDLED_USER_ROOT)
        except OSError:
            pass
    for src in BUNDLED_ROOT.rglob("*"):
        if not src.is_file():
            continue
        rel = src.relative_to(BUNDLED_ROOT)
        dst = BUNDLED_USER_ROOT / rel
        if dst.exists() and not overwrite:
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        written.append(dst)
    return written


def thumbnail_path(character: Character) -> Path:
    p = character.image_path.parent / ".thumbs" / character.image_path.name
    return p if p.exists() else character.image_path


def sanitize_filename(name: str) -> str:
    text = re.sub(r"[^A-Za-z0-9._ -]+", "", name).strip().replace(" ", "_")
    return text or "character"


def copy_to_comfy_input(character: Character) -> str:
    """Copy a character reference into ComfyUI/input and return the LoadImage-relative path."""
    if not character.image_path.exists():
        raise FileNotFoundError(character.image_path)
    sub = Path("Superior-MI-Characters")
    folder = COMFY_INPUT / sub
    folder.mkdir(parents=True, exist_ok=True)
    token = character.uid[:8]
    name = f"{sanitize_filename(character.name)}_{token}{character.image_path.suffix.lower()}"
    dst = folder / name
    # Replace only if content metadata differs, so repeated workflow creation is cheap.
    if not dst.exists() or dst.stat().st_size != character.image_path.stat().st_size or dst.stat().st_mtime < character.image_path.stat().st_mtime:
        shutil.copy2(character.image_path, dst)
    return str((sub / name).as_posix())


def categories(characters: list[Character] | None = None) -> list[str]:
    chars = characters if characters is not None else scan_characters()
    return sorted({c.kind or "Other" for c in chars}, key=str.lower)


def collections(characters: list[Character] | None = None) -> list[str]:
    chars = characters if characters is not None else scan_characters()
    return sorted({c.collection or "Custom" for c in chars}, key=str.lower)


def find_character(uid: str, characters: list[Character] | None = None) -> Character | None:
    for c in characters if characters is not None else scan_characters():
        if c.uid == uid:
            return c
    return None
