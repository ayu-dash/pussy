"""Directory scanner tests."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from pussy.core.scanner import Scanner
from pussy.filters.ignore import IgnoreManager, IncludeManager
from pussy.filters.sensitive import is_sensitive_path  # noqa: F401  (documents intent)


def test_empty_directory(tmp_path: Path) -> None:
    result = Scanner(tmp_path, IgnoreManager([])).scan()
    assert result.file_count == 0
    assert result.directory_count == 0
    assert result.warnings == []


def test_nested_structure_is_preserved(tmp_path: Path, write_file) -> None:
    write_file(tmp_path, "src/app/main.py", "print('app')\n")
    write_file(tmp_path, "src/app/utils/helpers.py", "def help_me(): pass\n")
    write_file(tmp_path, "README.md", "# Readme\n")
    result = Scanner(tmp_path, IgnoreManager([])).scan()
    assert {entry.relative_path for entry in result.files} == {
        "src/app/main.py",
        "src/app/utils/helpers.py",
        "README.md",
    }
    assert set(result.directories) == {"src", "src/app", "src/app/utils"}


def test_many_files(tmp_path: Path, write_file) -> None:
    for index in range(75):
        write_file(tmp_path, f"batch/{index:03d}.txt", str(index))
    result = Scanner(tmp_path, IgnoreManager([])).scan()
    assert result.file_count == 75
    assert result.directory_count == 1


def test_hidden_files_can_be_included_or_excluded(tmp_path: Path, write_file) -> None:
    write_file(tmp_path, ".hidden.py", "hidden = True\n")
    write_file(tmp_path, ".github/workflows/ci.yml", "name: ci\n")
    with_hidden = Scanner(tmp_path, IgnoreManager([]), include_hidden=True).scan()
    without_hidden = Scanner(tmp_path, IgnoreManager([]), include_hidden=False).scan()

    assert {entry.relative_path for entry in with_hidden.files} == {
        ".hidden.py",
        ".github/workflows/ci.yml",
    }
    assert without_hidden.file_count == 0


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions")
def test_permission_denied_is_a_warning(tmp_path: Path, write_file) -> None:
    if os.geteuid() == 0:
        pytest.skip("root bypasses directory permissions")
    blocked = tmp_path / "blocked"
    blocked.mkdir()
    (blocked / "secret.py").write_text("secret", encoding="utf-8")
    blocked.chmod(0)
    try:
        result = Scanner(tmp_path, IgnoreManager([])).scan()
    finally:
        blocked.chmod(0o700)
    assert any("permission denied" in warning.lower() for warning in result.warnings)
    assert result.file_count == 0


@pytest.mark.skipif(sys.platform == "win32", reason="symlink semantics")
def test_symlinks_are_not_followed_by_default(tmp_path: Path, write_file) -> None:
    target = write_file(tmp_path, "real.py", "print(1)\n")
    (tmp_path / "link.py").symlink_to(target)
    result = Scanner(tmp_path, IgnoreManager([])).scan()
    assert {entry.relative_path for entry in result.files} == {"real.py"}


@pytest.mark.skipif(sys.platform == "win32", reason="symlink semantics")
def test_internal_symlink_can_be_followed(tmp_path: Path, write_file) -> None:
    target = write_file(tmp_path, "real.py", "print(1)\n")
    (tmp_path / "link.py").symlink_to(target)
    result = Scanner(tmp_path, IgnoreManager([]), follow_symlinks=True).scan()
    paths = {entry.relative_path for entry in result.files}
    assert paths == {"real.py", "link.py"}
    assert next(entry for entry in result.files if entry.relative_path == "link.py").is_symlink


@pytest.mark.skipif(sys.platform == "win32", reason="symlink semantics")
def test_symlink_outside_root_is_rejected(
    tmp_path: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    outside = tmp_path_factory.mktemp("outside") / "secret.py"
    outside.write_text("outside", encoding="utf-8")
    (tmp_path / "link.py").symlink_to(outside)
    result = Scanner(tmp_path, IgnoreManager([]), follow_symlinks=True).scan()
    assert result.file_count == 0
    assert any("outside project root" in warning for warning in result.warnings)


@pytest.mark.skipif(sys.platform == "win32", reason="symlink semantics")
def test_symlink_loop_is_broken(tmp_path: Path, write_file) -> None:
    write_file(tmp_path, "sub/inside.py", "x = 1\n")
    (tmp_path / "sub" / "loop").symlink_to(tmp_path)
    result = Scanner(tmp_path, IgnoreManager([]), follow_symlinks=True).scan()
    assert result.file_count == 1
    assert any("loop" in warning for warning in result.warnings)


def test_unicode_and_spaces_in_names(tmp_path: Path, write_file) -> None:
    write_file(tmp_path, "src/файл с пробелом.py", "x = 1\n")
    write_file(tmp_path, "docs/日本語ガイド.md", "# guide\n")
    result = Scanner(tmp_path, IgnoreManager([])).scan()
    assert {entry.relative_path for entry in result.files} == {
        "src/файл с пробелом.py",
        "docs/日本語ガイド.md",
    }


def test_ignored_directories_are_pruned(tmp_path: Path, write_file) -> None:
    write_file(tmp_path, "node_modules/pkg/index.js", "module.exports = 1\n")
    write_file(tmp_path, "src/index.js", "export default 1\n")
    manager = IgnoreManager.from_sources(defaults=["node_modules/"])
    result = Scanner(tmp_path, manager).scan()
    assert "node_modules" in result.skipped_directories
    assert {entry.relative_path for entry in result.files} == {"src/index.js"}


def test_sensitive_file_is_recorded_but_excluded(tmp_path: Path, write_file) -> None:
    write_file(tmp_path, ".env", "DB_PASSWORD=hunter2\n")
    write_file(tmp_path, ".env.example", "DB_PASSWORD=change-me\n")
    result = Scanner(tmp_path, IgnoreManager([])).scan()
    entries = {entry.relative_path: entry for entry in result.files}
    assert entries[".env"].is_sensitive
    assert not entries[".env"].included
    assert "sensitive" in (entries[".env"].exclusion_reason or "")
    assert entries[".env.example"].included


def test_exact_output_path_is_never_scanned(tmp_path: Path, write_file) -> None:
    write_file(tmp_path, "main.py", "print(1)\n")
    output = write_file(tmp_path, "context.md", "# old context\n")
    result = Scanner(tmp_path, IgnoreManager([]), exclude_paths=[output]).scan()
    assert {entry.relative_path for entry in result.files} == {"main.py"}


def test_include_rule_reaches_into_ignored_directory(tmp_path: Path, write_file) -> None:
    write_file(tmp_path, "vendor/keep.py", "keep = True\n")
    write_file(tmp_path, "vendor/drop.py", "keep = False\n")
    ignore = IgnoreManager.from_sources(defaults=["vendor/"])
    includes = IncludeManager(["vendor/keep.py"])
    result = Scanner(tmp_path, ignore, includes=includes).scan()
    entries = {entry.relative_path: entry for entry in result.files}
    assert entries["vendor/keep.py"].included
    assert not entries["vendor/drop.py"].included
    assert "vendor" in result.directories


def test_progress_callback_receives_files(tmp_path: Path, write_file) -> None:
    write_file(tmp_path, "a.py", "a=1\n")
    write_file(tmp_path, "b.py", "b=1\n")
    seen: list[str] = []
    Scanner(tmp_path, IgnoreManager([])).scan(progress=seen.append)
    assert seen == ["a.py", "b.py"]


def test_missing_root_is_reported(tmp_path: Path) -> None:
    result = Scanner(tmp_path / "missing", IgnoreManager([])).scan()
    assert result.file_count == 0
    assert result.warnings
