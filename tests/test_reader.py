"""File reader tests: encodings, binary detection, limits and failures."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from pussy.core.reader import FileReader
from pussy.filters.extensions import language_for
from pussy.models.file_entry import FileCategory, FileEntry, ReadStatus


def make_entry(path: Path, relative: str | None = None, **kwargs: object) -> FileEntry:
    return FileEntry(
        path=path,
        relative_path=relative or path.name,
        size=path.stat().st_size if path.exists() else 0,
        **kwargs,  # type: ignore[arg-type]
    )


def reader(max_file_size: int = 1024, max_total_size: int = 10_000) -> FileReader:
    return FileReader(max_file_size=max_file_size, max_total_size=max_total_size)


def test_reads_utf8(tmp_path: Path) -> None:
    path = tmp_path / "main.py"
    path.write_text("print('héllo')\n", encoding="utf-8")
    entry = make_entry(path, "main.py", category=FileCategory.SOURCE_CODE)
    reader().read_entry(entry)
    assert entry.read_status is ReadStatus.READ
    assert entry.content == "print('héllo')\n"
    assert entry.encoding == "utf-8"
    assert entry.line_count == 1


def test_reads_utf8_bom(tmp_path: Path) -> None:
    path = tmp_path / "bom.txt"
    path.write_bytes(b"\xef\xbb\xbfhello\n")
    entry = make_entry(path)
    reader().read_entry(entry)
    assert entry.content == "hello\n"
    assert entry.encoding == "utf-8-sig"


def test_reads_utf16_with_bom(tmp_path: Path) -> None:
    path = tmp_path / "utf16.txt"
    path.write_bytes("hello unicode".encode("utf-16"))
    entry = make_entry(path)
    reader().read_entry(entry)
    assert entry.content == "hello unicode"
    assert entry.encoding == "utf-16"


def test_reads_legacy_cp1252(tmp_path: Path) -> None:
    path = tmp_path / "legacy.txt"
    path.write_bytes("café".encode("cp1252"))
    entry = make_entry(path)
    reader().read_entry(entry)
    assert entry.content == "café"
    assert entry.encoding == "cp1252"


def test_bom_binary_detection_does_not_reject_utf16(tmp_path: Path) -> None:
    path = tmp_path / "utf16.py"
    path.write_bytes("print('x')".encode("utf-16"))
    entry = make_entry(path)
    reader().read_entry(entry)
    assert entry.content == "print('x')"
    assert not entry.is_binary


def test_binary_content_is_excluded(tmp_path: Path) -> None:
    path = tmp_path / "blob.dat"
    path.write_bytes(b"\x00\x01\x02\x03binary")
    entry = make_entry(path)
    reader().read_entry(entry)
    assert entry.is_binary
    assert not entry.included
    assert entry.content is None
    assert entry.read_status is ReadStatus.SKIPPED
    assert entry.category is FileCategory.BINARY


def test_binary_extension_is_not_opened(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "image.png"
    path.write_bytes(b"not really a png")
    entry = make_entry(path, category=FileCategory.ASSETS)
    opened = False
    original_open = Path.open

    def tracking_open(self: Path, *args: object, **kwargs: object):
        nonlocal opened
        if self == path:
            opened = True
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", tracking_open)
    reader().read_entry(entry)
    assert not opened
    assert entry.is_binary
    assert entry.category is FileCategory.ASSETS


def test_empty_file_is_readable(tmp_path: Path) -> None:
    path = tmp_path / "empty.py"
    path.write_text("", encoding="utf-8")
    entry = make_entry(path)
    reader().read_entry(entry)
    assert entry.read_status is ReadStatus.READ
    assert entry.content == ""
    assert entry.line_count == 0


def test_file_over_size_limit_is_skipped(tmp_path: Path) -> None:
    path = tmp_path / "big.txt"
    path.write_text("x" * 100, encoding="utf-8")
    entry = make_entry(path)
    reader(max_file_size=10).read_entry(entry)
    assert not entry.included
    assert "exceeds limit" in (entry.exclusion_reason or "")


def test_file_at_size_limit_is_allowed(tmp_path: Path) -> None:
    path = tmp_path / "exact.txt"
    path.write_text("x" * 10, encoding="utf-8")
    entry = make_entry(path)
    reader(max_file_size=10).read_entry(entry)
    assert entry.read_status is ReadStatus.READ
    assert entry.content == "x" * 10


def test_total_size_limit_stops_reading(tmp_path: Path) -> None:
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("a" * 8, encoding="utf-8")
    second.write_text("b" * 8, encoding="utf-8")
    first_entry = make_entry(first, "first.txt")
    second_entry = make_entry(second, "second.txt")
    instance = reader(max_file_size=100, max_total_size=10)
    instance.read_all([first_entry, second_entry])
    assert first_entry.read_status is ReadStatus.READ
    assert not second_entry.included
    assert "total content limit" in (second_entry.exclusion_reason or "")


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions")
def test_permission_error_becomes_status(tmp_path: Path) -> None:
    if os.geteuid() == 0:
        pytest.skip("root bypasses file permissions")
    path = tmp_path / "blocked.txt"
    path.write_text("secret", encoding="utf-8")
    entry = make_entry(path)
    path.chmod(0)
    try:
        reader().read_entry(entry)
    finally:
        path.chmod(0o600)
    assert entry.read_status is ReadStatus.ERROR
    assert not entry.included
    assert "permission denied" in (entry.error or "")


def test_file_missing_after_scan_is_reported(tmp_path: Path) -> None:
    path = tmp_path / "gone.py"
    path.write_text("x = 1\n", encoding="utf-8")
    entry = make_entry(path)
    path.unlink()
    reader().read_entry(entry)
    assert entry.read_status is ReadStatus.ERROR
    assert not entry.included
    assert "disappeared" in (entry.error or "")


def test_sensitive_entry_is_never_opened(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / ".env"
    path.write_text("SECRET=value\n", encoding="utf-8")
    entry = make_entry(path, ".env", is_sensitive=True, included=True)
    original_open = Path.open
    opened = False

    def tracking_open(self: Path, *args: object, **kwargs: object):
        nonlocal opened
        if self == path:
            opened = True
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", tracking_open)
    reader().read_entry(entry)
    assert not opened
    assert entry.content is None


def test_newlines_are_normalized(tmp_path: Path) -> None:
    path = tmp_path / "crlf.txt"
    path.write_bytes(b"a\r\nb\rc\n")
    entry = make_entry(path)
    reader().read_entry(entry)
    assert entry.content == "a\nb\nc\n"
    assert entry.line_count == 3


def test_excluded_entry_is_not_read(tmp_path: Path) -> None:
    path = tmp_path / "ignored.py"
    path.write_text("x = 1\n", encoding="utf-8")
    entry = make_entry(path, included=False, exclusion_reason="ignored")
    reader().read_entry(entry)
    assert entry.read_status is ReadStatus.NOT_READ
    assert entry.content is None


def test_language_helpers() -> None:
    assert language_for("main.py") == "Python"
    assert language_for("Dockerfile") == "Dockerfile"
    assert language_for(".env") == "Dotenv"
    assert language_for("unknown.xyz") is None
