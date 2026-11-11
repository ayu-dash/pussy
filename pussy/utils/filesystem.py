"""Filesystem helpers used across the pipeline."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def to_posix_relative(path: Path, root: Path) -> str:
    """Return *path* relative to *root* using forward slashes."""
    try:
        relative = path.resolve(strict=False).relative_to(root.resolve(strict=False))
    except ValueError:
        relative = path
    return relative.as_posix()


def is_within(path: Path, root: Path) -> bool:
    """Return True when *path* resolves inside *root* (including *root*)."""
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
    except (OSError, ValueError):
        return False
    return True


def safe_stat(path: Path) -> os.stat_result | None:
    """Stat a path without following symlinks, returning None on failure."""
    try:
        return path.stat(follow_symlinks=False)
    except OSError:
        return None


def write_atomic(path: Path, text: str, encoding: str = "utf-8") -> None:
    """Write text atomically, replacing *path* only after a complete write."""
    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding=encoding, newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def ensure_directory(path: Path) -> Path:
    """Create *path* (and parents) and return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def path_key(path: Path) -> str:
    """Return a normalized absolute string usable for exact-path exclusion."""
    return os.path.normcase(os.path.abspath(os.path.expanduser(str(path))))
