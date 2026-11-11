"""Markdown, JSON and tree formatter tests."""

from __future__ import annotations

import io
import json
from pathlib import Path

from pussy.formatters.json import JsonFormatter
from pussy.formatters.markdown import MarkdownFormatter, fence
from pussy.formatters.tree import render_tree


def test_fence_uses_three_backticks_normally() -> None:
    output = fence("print('hello')", "Python")
    assert output.startswith("```python\n")
    assert output.endswith("\n```")


def test_fence_extends_for_nested_backticks() -> None:
    content = "```python\nprint('nested')\n```"
    output = fence(content, "Markdown")
    assert output.startswith("````markdown\n")
    assert output.endswith("\n````")
    assert content in output


def test_fence_handles_empty_text() -> None:
    assert fence("", "text") == "```text\n\n```"


def test_markdown_sections_and_file_content(build_bundle, tmp_path: Path, write_file) -> None:
    write_file(tmp_path, "src/main.py", "print('MARKER_123')\n")
    write_file(tmp_path, "README.md", "# Readme\n")
    write_file(tmp_path, ".env", "SECRET=do-not-leak\n")
    bundle = build_bundle(tmp_path)
    markdown = MarkdownFormatter().render(bundle)

    assert markdown.startswith("# Project Context\n")
    assert "## 1. Project Overview" in markdown
    assert "Project Metadata" in markdown
    assert "Directory Structure" in markdown
    assert "Dependencies" in markdown
    assert "Configuration Files" in markdown
    assert "Source Code" in markdown
    assert "Documentation" in markdown
    assert "Database" in markdown
    assert "Tests" in markdown
    assert "Infrastructure Files" in markdown
    assert "Git Information" in markdown
    assert "File Processing Report" in markdown
    assert "Context Statistics" in markdown
    assert "MARKER_123" in markdown
    assert "do-not-leak" not in markdown


def test_markdown_preserves_nested_fences(build_bundle, tmp_path: Path, write_file) -> None:
    write_file(
        tmp_path,
        "docs/example.md",
        "# Example\n\n```python\nprint('inside')\n```\n",
    )
    bundle = build_bundle(tmp_path)
    markdown = MarkdownFormatter().render(bundle)
    assert "````markdown" in markdown
    assert "print('inside')" in markdown


def test_markdown_render_to_stream(build_bundle, tmp_path: Path, write_file) -> None:
    write_file(tmp_path, "main.py", "x = 1\n")
    bundle = build_bundle(tmp_path)
    stream = io.StringIO()
    MarkdownFormatter().render_to(bundle, stream)
    assert stream.getvalue() == MarkdownFormatter().render(bundle)


def test_json_output_is_valid_and_structured(build_bundle, tmp_path: Path, write_file) -> None:
    write_file(tmp_path, "main.py", "x = 1\n")
    write_file(tmp_path, "README.md", "# hi\n")
    write_file(tmp_path, ".env", "TOKEN=secret\n")
    bundle = build_bundle(tmp_path)
    payload = json.loads(JsonFormatter().render(bundle))

    assert payload["schema_version"] == 1
    assert payload["generator"]["name"] == "pussy-cli"
    assert payload["mode"] == "context"
    assert payload["project"]["name"] == tmp_path.name
    assert payload["tree"]
    assert isinstance(payload["files"], list)
    assert "stats" in payload
    assert payload["git"] is None

    files = {item["path"]: item for item in payload["files"]}
    assert files["main.py"]["content"] == "x = 1\n"
    assert files["main.py"]["category"] == "source_code"
    assert files[".env"]["is_sensitive"] is True
    assert files[".env"]["included"] is False
    assert files[".env"]["content"] is None
    assert "secret" not in json.dumps(payload)


def test_json_report_lists_exclusions(build_bundle, tmp_path: Path, write_file) -> None:
    write_file(tmp_path, "main.py", "x = 1\n")
    write_file(tmp_path, ".env", "TOKEN=secret\n")
    payload = json.loads(JsonFormatter().render(build_bundle(tmp_path)))
    reasons = {
        item["path"]: item["exclusion_reason"] for item in payload["files"] if not item["included"]
    }
    assert "sensitive" in reasons[".env"]


def test_tree_renderer_sorts_directories_before_files() -> None:
    tree = render_tree(
        "project",
        directories=["src", "src/utils", "empty"],
        files=["README.md", "src/main.py", "src/utils/helper.py"],
    )
    assert tree.startswith("project/\n")
    assert "├── src/" in tree
    assert "└── README.md" in tree
    assert "empty/" in tree
    assert tree.index("src/") < tree.index("README.md")


def test_ascii_tree() -> None:
    tree = render_tree("project", ["src"], ["main.py"], ascii_only=True)
    assert "|-- src/" in tree
    assert "`-- main.py" in tree


def test_tree_handles_names_with_unicode() -> None:
    tree = render_tree("проект", ["src"], ["src/файл.py"])
    assert "проект/" in tree
    assert "файл.py" in tree
