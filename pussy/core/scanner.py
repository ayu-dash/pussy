"""Recursive metadata-only directory scanner."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

from pussy.filters.ignore import IgnoreManager, IncludeManager
from pussy.filters.sensitive import is_sensitive_path
from pussy.models.file_entry import FileEntry
from pussy.utils.filesystem import is_within, path_key

ProgressCallback = Callable[[str], None]


@dataclass(slots=True)
class ScanResult:
    """Files and directories discovered during one scan."""

    root: Path
    files: list[FileEntry] = field(default_factory=list)
    directories: list[str] = field(default_factory=list)
    skipped_directories: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def file_count(self) -> int:
        """Number of discovered files (included and excluded)."""
        return len(self.files)

    @property
    def directory_count(self) -> int:
        """Number of traversed directories below the root."""
        return len(self.directories)


class Scanner:
    """Walk a project tree without reading file contents.

    Ignored directories are pruned before descent, which keeps scans of large
    ``node_modules``/``vendor`` trees fast.  Symlinks are skipped by default and
    are only followed when they stay inside the project root.
    """

    def __init__(
        self,
        root: Path,
        ignore: IgnoreManager,
        *,
        includes: IncludeManager | None = None,
        include_hidden: bool = True,
        follow_symlinks: bool = False,
        exclude_paths: Iterable[Path] = (),
    ) -> None:
        self.root = root.expanduser().resolve()
        self.ignore = ignore
        self.includes = includes or IncludeManager(())
        self.include_hidden = include_hidden
        self.follow_symlinks = follow_symlinks
        self.exclude_paths = {path_key(path) for path in exclude_paths}

    def scan(self, progress: ProgressCallback | None = None) -> ScanResult:
        """Scan the project and return metadata for every visited file."""
        result = ScanResult(root=self.root)
        if not self.root.is_dir():
            result.warnings.append(f"project root is not a directory: {self.root}")
            return result

        stack: list[tuple[Path, str, bool]] = [(self.root, "", False)]
        seen_directories: set[tuple[int, int]] = set()

        while stack:
            directory, relative_directory, parent_ignored = stack.pop()
            if self.follow_symlinks:
                try:
                    stat = directory.stat()
                except OSError as exc:
                    result.warnings.append(f"cannot stat {directory}: {exc}")
                    continue
                identity = (stat.st_dev, stat.st_ino)
                if identity in seen_directories:
                    result.warnings.append(f"skipping symlink loop at {relative_directory or '.'}")
                    continue
                seen_directories.add(identity)

            try:
                children = sorted(os.scandir(directory), key=lambda item: item.name.casefold())
            except PermissionError:
                result.warnings.append(
                    f"permission denied while reading {relative_directory or '.'}"
                )
                continue
            except OSError as exc:
                result.warnings.append(
                    f"cannot read directory {relative_directory or '.'}: {exc.strerror or exc}"
                )
                continue

            for child in children:
                name = child.name
                if not self.include_hidden and name.startswith("."):
                    continue
                relative_path = f"{relative_directory}/{name}" if relative_directory else name
                try:
                    self._visit(child, relative_path, result, stack, progress, parent_ignored)
                except OSError as exc:
                    result.warnings.append(f"cannot inspect {relative_path}: {exc.strerror or exc}")

        return result

    def _visit(
        self,
        child: os.DirEntry[str],
        relative_path: str,
        result: ScanResult,
        stack: list[tuple[Path, str, bool]],
        progress: ProgressCallback | None,
        parent_ignored: bool,
    ) -> None:
        path = Path(child.path)
        is_symlink = child.is_symlink()

        if child.is_dir(follow_symlinks=False):
            self._visit_directory(path, relative_path, result, stack, parent_ignored)
            return

        if child.is_file(follow_symlinks=False):
            self._add_file(
                path,
                relative_path,
                result,
                progress,
                is_symlink=False,
                parent_ignored=parent_ignored,
            )
            return

        if is_symlink:
            self._visit_symlink(path, relative_path, result, stack, progress, parent_ignored)
            return

        result.warnings.append(f"skipping special file: {relative_path}")

    def _visit_directory(
        self,
        path: Path,
        relative_path: str,
        result: ScanResult,
        stack: list[tuple[Path, str, bool]],
        parent_ignored: bool,
    ) -> None:
        decision = self.ignore.decide(relative_path, is_directory=True)
        ignored = decision.ignored or parent_ignored
        if ignored and not self.includes.may_match_under(relative_path):
            result.skipped_directories.append(relative_path)
            return
        result.directories.append(relative_path)
        stack.append((path, relative_path, ignored))

    def _visit_symlink(
        self,
        path: Path,
        relative_path: str,
        result: ScanResult,
        stack: list[tuple[Path, str, bool]],
        progress: ProgressCallback | None,
        parent_ignored: bool,
    ) -> None:
        if not self.follow_symlinks:
            return
        if not is_within(path, self.root):
            result.warnings.append(f"symlink outside project root skipped: {relative_path}")
            return
        try:
            target_is_dir = path.is_dir()
            target_is_file = path.is_file()
        except OSError:
            result.warnings.append(f"broken symlink skipped: {relative_path}")
            return
        if target_is_dir:
            self._visit_directory(path, relative_path, result, stack, parent_ignored)
        elif target_is_file:
            self._add_file(
                path,
                relative_path,
                result,
                progress,
                is_symlink=True,
                parent_ignored=parent_ignored,
            )
        else:
            result.warnings.append(f"broken symlink skipped: {relative_path}")

    def _add_file(
        self,
        path: Path,
        relative_path: str,
        result: ScanResult,
        progress: ProgressCallback | None,
        *,
        is_symlink: bool,
        parent_ignored: bool,
    ) -> None:
        if path_key(path) in self.exclude_paths:
            # Never include the file currently being generated in its own scan.
            if progress:
                progress(relative_path)
            return

        try:
            stat = path.stat()
        except OSError as exc:
            result.warnings.append(f"cannot stat {relative_path}: {exc.strerror or exc}")
            return

        sensitive = is_sensitive_path(relative_path)
        decision = self.ignore.decide(relative_path, is_directory=False)
        ignored = decision.ignored or parent_ignored
        forced = ignored and self.includes.matches_file(relative_path)

        included = not sensitive and (not ignored or forced)
        if sensitive:
            reason = "sensitive file (content blocked by security policy)"
        elif ignored and not forced:
            if decision.ignored:
                reason = f"ignored by {decision.source} pattern {decision.pattern!r}"
            else:
                reason = "ignored because a parent directory is excluded"
        else:
            reason = None

        entry = FileEntry(
            path=path,
            relative_path=relative_path,
            size=stat.st_size,
            modified_at=stat.st_mtime,
            is_sensitive=sensitive,
            is_symlink=is_symlink,
            included=included,
            exclusion_reason=reason,
        )
        if forced:
            entry.metadata["included_by_rule"] = "true"
        result.files.append(entry)
        if progress:
            progress(relative_path)
