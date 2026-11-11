"""Context builder and pipeline integration tests."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from pussy.config.models import PussyConfig
from pussy.core.pipeline import generate_context, scan_project
from pussy.formatters.markdown import MarkdownFormatter
from pussy.models.file_entry import FileCategory, ReadStatus


def make_project(root: Path, write_file) -> None:
    write_file(root, "src/main.py", "MAIN_UNIQUE = 'main-content'\n")
    write_file(root, "src/utils.py", "UTIL_UNIQUE = 'util-content'\n")
    write_file(root, "README.md", "# Project\n\nDocumentation body.\n")
    write_file(root, "requirements.txt", "requests==2.31.0\n")
    write_file(root, "schema.sql", "CREATE TABLE users (id INTEGER);\n")
    write_file(root, "tests/test_main.py", "def test_ok():\n    assert True\n")
    write_file(root, "Dockerfile", "FROM python:3.12\n")
    write_file(root, "logo.png", b"\x89PNG\r\n\x1a\n\x00binary")
    write_file(root, ".env", "SECRET_TOKEN=never-leak-this\n")
    write_file(root, ".env.example", "SECRET_TOKEN=change-me\n")
    write_file(root, "node_modules/pkg/index.js", "module.exports = 'ignored'\n")


def test_tree_matches_manifest(build_bundle, tmp_path: Path, write_file) -> None:
    make_project(tmp_path, write_file)
    bundle = build_bundle(tmp_path)
    for entry in bundle.entries:
        assert entry.relative_path.split("/")[-1] in bundle.tree
    assert "src/" in bundle.tree
    assert "tests/" in bundle.tree
    assert "node_modules" not in bundle.tree


def test_paths_and_contents_are_not_swapped(build_bundle, tmp_path: Path, write_file) -> None:
    write_file(tmp_path, "alpha.py", "ALPHA_MARKER = 111\n")
    write_file(tmp_path, "beta.py", "BETA_MARKER = 222\n")
    bundle = build_bundle(tmp_path)
    entries = {entry.relative_path: entry for entry in bundle.entries}
    assert entries["alpha.py"].content == "ALPHA_MARKER = 111\n"
    assert entries["beta.py"].content == "BETA_MARKER = 222\n"
    assert entries["alpha.py"].language == "Python"
    assert entries["alpha.py"].category is FileCategory.SOURCE_CODE


def test_sensitive_content_never_appears(build_bundle, tmp_path: Path, write_file) -> None:
    make_project(tmp_path, write_file)
    bundle = build_bundle(tmp_path)
    markdown = MarkdownFormatter().render(bundle)
    assert "never-leak-this" not in markdown
    assert ".env" in markdown  # path is reported
    entries = {entry.relative_path: entry for entry in bundle.entries}
    assert entries[".env"].is_sensitive
    assert not entries[".env"].included
    assert entries[".env"].content is None
    assert entries[".env.example"].included


def test_binary_is_excluded(build_bundle, tmp_path: Path, write_file) -> None:
    write_file(tmp_path, "logo.png", b"\x89PNG\r\n\x1a\n\x00binary")
    write_file(tmp_path, "blob.txt", b"\x00\x01\x02")
    bundle = build_bundle(tmp_path)
    entries = {entry.relative_path: entry for entry in bundle.entries}
    assert entries["logo.png"].is_binary
    assert not entries["logo.png"].included
    assert entries["blob.txt"].is_binary
    assert entries["blob.txt"].content is None


def test_context_mode_selects_content_categories(build_bundle, tmp_path: Path, write_file) -> None:
    make_project(tmp_path, write_file)
    write_file(tmp_path, "app.min.js", "var minified=true;\n")
    bundle = build_bundle(tmp_path)
    included = {entry.relative_path for entry in bundle.content_entries()}
    assert "src/main.py" in included
    assert "requirements.txt" in included
    assert "README.md" in included
    assert "schema.sql" in included
    assert "tests/test_main.py" in included
    assert "Dockerfile" in included
    assert "logo.png" not in included
    assert "app.min.js" not in included


def test_full_mode_includes_generated_and_unknown(build_bundle, tmp_path: Path, write_file) -> None:
    write_file(tmp_path, "app.min.js", "var minified=true;\n")
    write_file(tmp_path, "notes.xyz", "unknown but text\n")
    context = build_bundle(tmp_path)
    full = build_bundle(tmp_path, mode="full")
    context_paths = {entry.relative_path for entry in context.content_entries()}
    full_paths = {entry.relative_path for entry in full.content_entries()}
    assert "app.min.js" not in context_paths
    assert "app.min.js" in full_paths
    assert "notes.xyz" in full_paths
    assert full.stats.estimated_tokens >= context.stats.estimated_tokens


def test_overview_mode_reads_no_content(build_bundle, tmp_path: Path, write_file) -> None:
    make_project(tmp_path, write_file)
    bundle = build_bundle(tmp_path, mode="overview")
    assert all(entry.content is None for entry in bundle.entries)
    assert bundle.stats.files_included >= 1
    assert bundle.stats.estimated_tokens > 0
    markdown = MarkdownFormatter().render(bundle)
    assert "Project Overview" in markdown
    assert "Directory Structure" in markdown
    assert "## 6. Source Code" not in markdown


def test_tree_only_reads_no_content(build_bundle, tmp_path: Path, write_file) -> None:
    make_project(tmp_path, write_file)
    bundle = build_bundle(tmp_path, tree_only=True)
    assert all(entry.content is None for entry in bundle.entries)
    markdown = MarkdownFormatter().render(bundle)
    assert "Directory Structure" in markdown
    assert "Project Overview" not in markdown
    assert "main-content" not in markdown


def test_code_only_omits_overview_and_tree(build_bundle, tmp_path: Path, write_file) -> None:
    make_project(tmp_path, write_file)
    bundle = build_bundle(tmp_path, code_only=True)
    markdown = MarkdownFormatter().render(bundle)
    assert "Project Overview" not in markdown
    assert "Directory Structure" not in markdown
    assert "Dependencies" not in markdown
    assert "Git Information" not in markdown
    assert "Source Code" in markdown
    assert "main-content" in markdown


def test_extension_include_filter(build_bundle, tmp_path: Path, write_file) -> None:
    write_file(tmp_path, "main.py", "x = 1\n")
    write_file(tmp_path, "README.md", "README_UNIQUE\n")
    bundle = build_bundle(tmp_path, include_extensions={".py"})
    entries = {entry.relative_path: entry for entry in bundle.entries}
    assert entries["main.py"].included
    assert not entries["README.md"].included
    assert "include list" in (entries["README.md"].exclusion_reason or "")


def test_extension_exclude_filter(build_bundle, tmp_path: Path, write_file) -> None:
    write_file(tmp_path, "main.py", "x = 1\n")
    write_file(tmp_path, "README.md", "README_UNIQUE\n")
    bundle = build_bundle(tmp_path, exclude_extensions={".md"})
    entries = {entry.relative_path: entry for entry in bundle.entries}
    assert entries["main.py"].included
    assert not entries["README.md"].included


def test_max_file_size_is_recorded(build_bundle, tmp_path: Path, write_file) -> None:
    write_file(tmp_path, "small.py", "x = 1\n")
    write_file(tmp_path, "big.py", "y = 2\n" * 100)
    bundle = build_bundle(tmp_path, max_file_size=20)
    entries = {entry.relative_path: entry for entry in bundle.entries}
    assert entries["small.py"].read_status is ReadStatus.READ
    assert not entries["big.py"].included
    assert "exceeds limit" in (entries["big.py"].exclusion_reason or "")


def test_total_size_limit_is_recorded(build_bundle, tmp_path: Path, write_file) -> None:
    write_file(tmp_path, "first.py", "a" * 20 + "\n")
    write_file(tmp_path, "second.py", "b" * 20 + "\n")
    bundle = build_bundle(tmp_path, max_file_size=100, max_total_size=30)
    included = {entry.relative_path for entry in bundle.content_entries()}
    assert len(included) == 1
    assert any("total content limit" in (entry.exclusion_reason or "") for entry in bundle.entries)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions")
def test_unreadable_file_has_error_status(build_bundle, tmp_path: Path, write_file) -> None:
    if os.geteuid() == 0:
        pytest.skip("root bypasses file permissions")
    path = write_file(tmp_path, "blocked.py", "x = 1\n")
    path.chmod(0)
    try:
        bundle = build_bundle(tmp_path)
    finally:
        path.chmod(0o600)
    entry = next(item for item in bundle.entries if item.relative_path == "blocked.py")
    assert entry.read_status is ReadStatus.ERROR
    assert not entry.included
    markdown = MarkdownFormatter().render(bundle)
    assert "permission denied" in markdown


def test_skipped_directories_and_exclusions_are_reported(
    build_bundle, tmp_path: Path, write_file
) -> None:
    make_project(tmp_path, write_file)
    bundle = build_bundle(tmp_path)
    assert "node_modules" in bundle.project.skipped_directories
    markdown = MarkdownFormatter().render(bundle)
    assert "Skipped Directories" in markdown
    assert "sensitive file" in markdown


def test_project_overview_uses_detected_facts(build_bundle, tmp_path: Path, write_file) -> None:
    write_file(tmp_path, "manage.py", "import django\n")
    write_file(tmp_path, "requirements.txt", "django>=5\n")
    write_file(tmp_path, "shop/views.py", "def index(): pass\n")
    bundle = build_bundle(tmp_path)
    assert "Django" in bundle.project.frameworks
    assert "Python" in bundle.project.languages
    assert "pip" in bundle.project.package_managers
    assert "manage.py" in bundle.project.entry_points
    assert bundle.project.total_files >= 3
    assert bundle.project.category_counts


def test_git_can_be_disabled(tmp_path: Path, write_file) -> None:
    write_file(tmp_path, "main.py", "x = 1\n")
    config = PussyConfig(root=tmp_path, include_git=False)
    outcome = scan_project(config)
    assert outcome.git is None
    bundle = generate_context(config)
    assert bundle.git is None
    assert "Git analysis disabled." in MarkdownFormatter().render(bundle)


def test_statistics_are_internally_consistent(build_bundle, tmp_path: Path, write_file) -> None:
    make_project(tmp_path, write_file)
    bundle = build_bundle(tmp_path)
    stats = bundle.stats
    assert stats.files_included + stats.files_excluded == stats.total_files
    assert stats.files_included == len(bundle.content_entries())
    assert stats.characters > 0
    assert stats.bytes > 0
    assert stats.estimated_tokens > 0
    assert stats.approximate
