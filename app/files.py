"""Safe path helpers and file operations for the local file manager."""

from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any


def default_root() -> Path:
    """Sensible default root: Windows Documents, else ~/Documents, else home."""
    if os.name == "nt":
        userprofile = os.environ.get("USERPROFILE")
        if userprofile:
            docs = Path(userprofile) / "Documents"
            if docs.is_dir():
                return docs.resolve()
    docs = Path.home() / "Documents"
    if docs.is_dir():
        return docs.resolve()
    return Path.home().resolve()


def get_root() -> Path:
    raw = os.environ.get("FILE_MANAGER_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return default_root()


def safe_resolve(rel: str, root: Path | None = None) -> Path:
    """Resolve a relative path under root; raise ValueError on traversal."""
    root = (root or get_root()).resolve()
    rel = (rel or "").replace("\\", "/").strip("/")
    if rel in ("", "."):
        return root

    candidate = (root / rel).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("Path escapes configured root directory") from exc
    return candidate


def to_rel(path: Path, root: Path | None = None) -> str:
    root = (root or get_root()).resolve()
    path = path.resolve()
    if path == root:
        return ""
    return path.relative_to(root).as_posix()


def _entry_info(path: Path, root: Path) -> dict[str, Any]:
    st = path.stat()
    is_dir = path.is_dir()
    return {
        "name": path.name,
        "path": to_rel(path, root),
        "is_dir": is_dir,
        "size": 0 if is_dir else st.st_size,
        "mtime": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
    }


def list_dir(rel: str = "") -> dict[str, Any]:
    root = get_root()
    target = safe_resolve(rel, root)
    if not target.exists():
        raise FileNotFoundError(f"Not found: {rel or '/'}")
    if not target.is_dir():
        raise NotADirectoryError(f"Not a directory: {rel}")

    entries: list[dict[str, Any]] = []
    for child in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        try:
            entries.append(_entry_info(child, root))
        except OSError:
            continue

    crumbs = [{"name": "根目录", "path": ""}]
    if rel:
        parts = rel.replace("\\", "/").strip("/").split("/")
        acc: list[str] = []
        for part in parts:
            if not part:
                continue
            acc.append(part)
            crumbs.append({"name": part, "path": "/".join(acc)})

    return {
        "root": str(root),
        "path": to_rel(target, root),
        "breadcrumb": crumbs,
        "entries": entries,
    }


def search_files(query: str, under: str = "") -> list[dict[str, Any]]:
    root = get_root()
    base = safe_resolve(under, root)
    if not base.is_dir():
        raise NotADirectoryError(f"Not a directory: {under}")

    q = (query or "").strip().lower()
    if not q:
        return []

    results: list[dict[str, Any]] = []
    for dirpath, dirnames, filenames in os.walk(base):
        # Skip hidden dirs lightly; still allow matching
        current = Path(dirpath)
        for name in dirnames + filenames:
            if q in name.lower():
                p = current / name
                try:
                    p.resolve().relative_to(root)
                    results.append(_entry_info(p, root))
                except (OSError, ValueError):
                    continue
        if len(results) >= 500:
            break
    return results


def rename_item(rel: str, new_name: str) -> dict[str, Any]:
    root = get_root()
    src = safe_resolve(rel, root)
    if not src.exists():
        raise FileNotFoundError(rel)
    new_name = new_name.strip().replace("/", "").replace("\\", "")
    if not new_name or new_name in (".", ".."):
        raise ValueError("Invalid new name")
    dest = src.parent / new_name
    safe_resolve(to_rel(dest, root), root)  # ensure still under root
    if dest.exists():
        raise FileExistsError(f"Already exists: {new_name}")
    src.rename(dest)
    return _entry_info(dest, root)


def copy_item(src_rel: str, dest_dir_rel: str) -> dict[str, Any]:
    root = get_root()
    src = safe_resolve(src_rel, root)
    dest_dir = safe_resolve(dest_dir_rel, root)
    if not src.exists():
        raise FileNotFoundError(src_rel)
    if not dest_dir.is_dir():
        raise NotADirectoryError(dest_dir_rel)

    dest = dest_dir / src.name
    if dest.exists():
        stem, suffix = src.stem, src.suffix
        n = 1
        while dest.exists():
            dest = dest_dir / f"{stem} (copy {n}){suffix}"
            n += 1

    if src.is_dir():
        shutil.copytree(src, dest)
    else:
        shutil.copy2(src, dest)
    return _entry_info(dest, root)


def move_item(src_rel: str, dest_dir_rel: str) -> dict[str, Any]:
    root = get_root()
    src = safe_resolve(src_rel, root)
    dest_dir = safe_resolve(dest_dir_rel, root)
    if not src.exists():
        raise FileNotFoundError(src_rel)
    if not dest_dir.is_dir():
        raise NotADirectoryError(dest_dir_rel)

    dest = dest_dir / src.name
    if dest.exists():
        raise FileExistsError(f"Target exists: {dest.name}")
    # Prevent moving a directory into itself
    if src.is_dir():
        try:
            dest_dir.resolve().relative_to(src.resolve())
            raise ValueError("Cannot move a folder into itself")
        except ValueError as e:
            if "into itself" in str(e):
                raise

    shutil.move(str(src), str(dest))
    return _entry_info(dest, root)


def delete_item(rel: str) -> None:
    root = get_root()
    target = safe_resolve(rel, root)
    if target == root:
        raise ValueError("Cannot delete root")
    if not target.exists():
        raise FileNotFoundError(rel)
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()


def mkdir(parent_rel: str, name: str) -> dict[str, Any]:
    root = get_root()
    parent = safe_resolve(parent_rel, root)
    if not parent.is_dir():
        raise NotADirectoryError(parent_rel)
    name = name.strip().replace("/", "").replace("\\", "")
    if not name or name in (".", ".."):
        raise ValueError("Invalid folder name")
    dest = parent / name
    if dest.exists():
        raise FileExistsError(name)
    dest.mkdir()
    return _entry_info(dest, root)


def read_text(rel: str, max_bytes: int = 2_000_000) -> dict[str, Any]:
    root = get_root()
    path = safe_resolve(rel, root)
    if not path.is_file():
        raise FileNotFoundError(rel)
    if path.stat().st_size > max_bytes:
        raise ValueError("File too large to edit in browser")
    raw = path.read_bytes()
    # Try common encodings
    for enc in ("utf-8", "utf-8-sig", "gbk", "latin-1"):
        try:
            text = raw.decode(enc)
            return {"path": to_rel(path, root), "encoding": enc, "content": text}
        except UnicodeDecodeError:
            continue
    raise ValueError("Unable to decode as text")


def write_text(rel: str, content: str, encoding: str = "utf-8") -> dict[str, Any]:
    root = get_root()
    path = safe_resolve(rel, root)
    if path.exists() and path.is_dir():
        raise IsADirectoryError(rel)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Ensure parent is still under root
    safe_resolve(to_rel(path.parent, root), root)
    path.write_text(content, encoding=encoding or "utf-8")
    return _entry_info(path, root)


def save_upload(parent_rel: str, filename: str, data: bytes) -> dict[str, Any]:
    root = get_root()
    parent = safe_resolve(parent_rel, root)
    if not parent.is_dir():
        raise NotADirectoryError(parent_rel)
    filename = Path(filename).name  # strip any path components
    if not filename or filename in (".", ".."):
        raise ValueError("Invalid filename")
    dest = parent / filename
    if dest.exists():
        stem, suffix = Path(filename).stem, Path(filename).suffix
        n = 1
        while dest.exists():
            dest = parent / f"{stem} ({n}){suffix}"
            n += 1
    dest.write_bytes(data)
    return _entry_info(dest, root)
