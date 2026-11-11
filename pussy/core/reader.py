"""Safe file content reader.

The reader is the only place that opens project files for content.  It refuses
to read sensitive or excluded entries, caps the number of bytes loaded, detects
binary data, and converts per-file failures into status records instead of
aborting the whole run.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from pussy.filters.extensions import BINARY_EXTENSIONS
from pussy.filters.size_limit import size_exclusion_reason
from pussy.models.file_entry import FileCategory, FileEntry, ReadStatus
from pussy.utils.encoding import (
    count_lines,
    decode_bytes,
    looks_binary,
    normalize_newlines,
)
from pussy.utils.size import human_size

ReaderProgress = Callable[[str], None]


class FileReader:
    """Read selected file entries with strict size and security limits."""

    def __init__(self, max_file_size: int, max_total_size: int) -> None:
        self.max_file_size = max_file_size
        self.max_total_size = max_total_size
        self._remaining = max_total_size

    def read_all(
        self, entries: Iterable[FileEntry], progress: ReaderProgress | None = None
    ) -> None:
        """Read every included entry, recording failures on each entry."""
        for entry in entries:
            self.read_entry(entry)
            if progress:
                progress(entry.relative_path)

    def read_entry(self, entry: FileEntry) -> None:
        """Populate one entry, or mark it excluded/error without raising."""
        if not entry.included or entry.is_sensitive:
            return

        if entry.suffix in BINARY_EXTENSIONS:
            self._mark_binary(entry, f"binary file ({entry.suffix})")
            return

        size_reason = size_exclusion_reason(entry, self.max_file_size)
        if size_reason:
            entry.exclude(size_reason)
            return

        if self._remaining <= 0:
            entry.exclude(f"total content limit {human_size(self.max_total_size)} reached")
            return

        limit = min(self.max_file_size, self._remaining)
        try:
            with entry.path.open("rb") as handle:
                data = handle.read(limit + 1)
        except FileNotFoundError:
            self._mark_error(entry, "file disappeared before it could be read")
            return
        except PermissionError:
            self._mark_error(entry, "permission denied while reading file")
            return
        except OSError as exc:
            self._mark_error(entry, f"cannot read file: {exc.strerror or exc}")
            return

        if len(data) > limit:
            if limit == self.max_file_size:
                entry.exclude(f"file size exceeds limit {human_size(self.max_file_size)}")
            else:
                entry.exclude(f"total content limit {human_size(self.max_total_size)} reached")
            return

        if looks_binary(data):
            self._mark_binary(entry, "binary content detected")
            return

        text, encoding = decode_bytes(data)
        text = normalize_newlines(text)
        entry.content = text
        entry.encoding = encoding
        entry.line_count = count_lines(text)
        entry.size = len(data)
        entry.read_status = ReadStatus.READ
        entry.included = True
        self._remaining -= len(data)

    @staticmethod
    def _mark_binary(entry: FileEntry, reason: str) -> None:
        entry.is_binary = True
        if entry.category is FileCategory.UNKNOWN:
            entry.category = FileCategory.BINARY
        entry.exclude(reason)

    @staticmethod
    def _mark_error(entry: FileEntry, message: str) -> None:
        entry.read_status = ReadStatus.ERROR
        entry.error = message
        entry.included = False
        entry.exclusion_reason = message
        entry.content = None
