"""Deterministic directory-tree rendering."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field


@dataclass(slots=True)
class _Node:
    directories: dict[str, _Node] = field(default_factory=dict)
    files: set[str] = field(default_factory=set)


def _insert(root: _Node, relative_path: str, *, is_directory: bool) -> None:
    parts = [part for part in relative_path.strip("/").split("/") if part]
    if not parts:
        return
    node = root
    for part in parts[:-1]:
        node = node.directories.setdefault(part, _Node())
    final = parts[-1]
    if is_directory:
        node.directories.setdefault(final, _Node())
    else:
        node.files.add(final)


def render_tree(
    root_name: str,
    directories: Iterable[str] = (),
    files: Iterable[str] = (),
    *,
    ascii_only: bool = False,
) -> str:
    """Render an indented tree from relative directory and file paths."""
    root = _Node()
    for directory in directories:
        _insert(root, directory, is_directory=True)
    for file_path in files:
        _insert(root, file_path, is_directory=False)

    branch, last_branch, vertical, blank = (
        ("|-- ", "`-- ", "|   ", "    ") if ascii_only else ("├── ", "└── ", "│   ", "    ")
    )
    display_name = root_name.rstrip("/") or root_name
    lines = [f"{display_name}/"]

    def walk(node: _Node, prefix: str) -> None:
        directory_names = sorted(node.directories, key=str.casefold)
        file_names = sorted(node.files, key=str.casefold)
        entries: list[tuple[str, bool]] = [(name, True) for name in directory_names]
        entries.extend((name, False) for name in file_names)
        for index, (name, is_directory) in enumerate(entries):
            is_last = index == len(entries) - 1
            connector = last_branch if is_last else branch
            suffix = "/" if is_directory else ""
            lines.append(f"{prefix}{connector}{name}{suffix}")
            if is_directory:
                walk(node.directories[name], prefix + (blank if is_last else vertical))

    walk(root, "")
    return "\n".join(lines) + "\n"
