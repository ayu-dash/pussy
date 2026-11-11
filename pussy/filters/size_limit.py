"""File-size policy helpers."""

from __future__ import annotations

from pathlib import Path

from pussy.models.file_entry import FileEntry
from pussy.utils.size import human_size


def exceeds_limit(size: int, limit: int) -> bool:
    """Return True if a byte size is above the limit."""
    return limit >= 0 and size > limit


def size_exclusion_reason(entry: FileEntry, max_file_size: int) -> str | None:
    """Return an exclusion reason when an entry exceeds the size limit."""
    if exceeds_limit(entry.size, max_file_size):
        return f"file size {human_size(entry.size)} exceeds limit {human_size(max_file_size)}"
    return None


def directory_size(path: Path) -> int:
    """Sum regular-file sizes below a directory without following symlinks."""
    total = 0
    stack = [path]
    while stack:
        current = stack.pop()
        try:
            for child in current.iterdir():
                try:
                    if child.is_symlink():
                        continue
                    if child.is_dir():
                        stack.append(child)
                    elif child.is_file():
                        total += child.stat().st_size
                except OSError:
                    continue
        except OSError:
            continue
    return total
