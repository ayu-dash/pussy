"""End-to-end CLI tests using Typer's CliRunner."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pussy.cli import app
from pussy.integrations.clipboard import ClipboardResult

runner = CliRunner()


@pytest.fixture
def project(tmp_path: Path, write_file) -> Path:
    write_file(tmp_path, "src/main.py", "def main():\n    return 'MAIN_UNIQUE'\n")
    write_file(tmp_path, "README.md", "# Demo\n\nREADME_UNIQUE_CONTENT\n")
    write_file(tmp_path, "requirements.txt", "requests==2.31.0\n")
    write_file(tmp_path, "tests/test_main.py", "def test_ok():\n    assert True\n")
    write_file(tmp_path, "node_modules/pkg/index.js", "NODE_MODULES_UNIQUE\n")
    write_file(tmp_path, ".env", "SECRET_TOKEN=NEVER_SHOW_THIS\n")
    write_file(tmp_path, ".env.example", "SECRET_TOKEN=change-me\n")
    write_file(tmp_path, "logo.png", b"\x89PNG\r\n\x1a\n\x00")
    return tmp_path


def invoke(arguments: list[str], **kwargs):
    return runner.invoke(app, arguments, env={"NO_COLOR": "1", "TERM": "dumb"}, **kwargs)


def test_help_lists_commands() -> None:
    result = invoke(["--help"])
    assert result.exit_code == 0
    for command in ("scan", "tree", "info", "generate", "init", "config"):
        assert command in result.output


def test_version() -> None:
    result = invoke(["--version"])
    assert result.exit_code == 0
    assert "1.0.0" in result.output


def test_scan_requires_existing_path(tmp_path: Path) -> None:
    result = invoke(["scan", str(tmp_path / "missing")])
    assert result.exit_code == 2
    assert "does not exist" in result.output


def test_scan_file_path_is_rejected(tmp_path: Path, write_file) -> None:
    path = write_file(tmp_path, "file.py", "x = 1\n")
    result = invoke(["scan", str(path)])
    assert result.exit_code == 2
    assert "not a directory" in result.output


def test_scan_project(project: Path) -> None:
    result = invoke(["scan", str(project)])
    assert result.exit_code == 0
    assert "Scan Summary" in result.output
    assert "Files by Category" in result.output
    assert "src/main.py" in result.output
    assert "NEVER_SHOW_THIS" not in result.output


def test_tree_command(project: Path) -> None:
    result = invoke(["tree", str(project)])
    assert result.exit_code == 0
    assert f"{project.name}/" in result.output
    assert "src/" in result.output
    assert "MAIN_UNIQUE" not in result.output
    assert "node_modules" not in result.output


def test_info_command(project: Path) -> None:
    result = invoke(["info", str(project)])
    assert result.exit_code == 0
    assert "Project Info" in result.output
    assert "Detected Technologies" in result.output
    assert "Python" in result.output


def test_generate_markdown_to_stdout(project: Path) -> None:
    result = invoke(["generate", str(project)])
    assert result.exit_code == 0
    assert result.stdout.startswith("# Project Context")
    assert "MAIN_UNIQUE" in result.stdout
    assert "README_UNIQUE_CONTENT" in result.stdout
    assert "NODE_MODULES_UNIQUE" not in result.stdout
    assert "NEVER_SHOW_THIS" not in result.stdout
    assert "requirements.txt" in result.stdout
    assert result.stderr == ""


def test_generate_json(project: Path) -> None:
    result = invoke(["generate", str(project), "--format", "json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == 1
    files = {item["path"]: item for item in payload["files"]}
    assert files["src/main.py"]["content"]
    assert files[".env"]["content"] is None
    assert "NEVER_SHOW_THIS" not in result.stdout


def test_generate_writes_output_file(project: Path) -> None:
    output = project / "context.md"
    result = invoke(["generate", str(project), "-o", str(output)])
    assert result.exit_code == 0
    assert output.is_file()
    assert result.stdout == ""
    assert "Wrote" in result.stderr
    assert "MAIN_UNIQUE" in output.read_text(encoding="utf-8")


def test_output_requires_force_to_overwrite(project: Path) -> None:
    output = project / "context.md"
    output.write_text("USER CONTENT", encoding="utf-8")
    result = invoke(["generate", str(project), "-o", str(output)])
    assert result.exit_code == 3
    assert "already exists" in result.output
    assert output.read_text(encoding="utf-8") == "USER CONTENT"

    forced = invoke(["generate", str(project), "-o", str(output), "--force"])
    assert forced.exit_code == 0
    assert "MAIN_UNIQUE" in output.read_text(encoding="utf-8")


def test_auto_save_creates_named_file(project: Path) -> None:
    result = invoke(["generate", str(project), "--save"])
    assert result.exit_code == 0
    generated = list(project.glob("pussy-context-*.md"))
    assert len(generated) == 1
    assert generated[0].read_text(encoding="utf-8").startswith("# Project Context")


def test_generated_files_are_not_rescanned(project: Path) -> None:
    first = invoke(["generate", str(project), "--save"])
    assert first.exit_code == 0
    second = invoke(["generate", str(project), "--format", "json"])
    assert second.exit_code == 0
    payload = json.loads(second.stdout)
    generated = [
        item for item in payload["files"] if Path(item["path"]).name.startswith("pussy-context-")
    ]
    assert generated, "previous export should be reported as an excluded file"
    assert all(item["included"] is False for item in generated)
    assert all(item["content"] is None for item in generated)
    assert all("pussy-context-" in (item["exclusion_reason"] or "") for item in generated)


def test_copy_success(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeClipboard:
        copied = ""

        def copy(self, text: str) -> ClipboardResult:
            FakeClipboard.copied = text
            return ClipboardResult(True, "fake-clip")

    monkeypatch.setattr("pussy.cli.ClipboardManager", FakeClipboard)
    result = invoke(["generate", str(project), "--copy"])
    assert result.exit_code == 0
    assert "MAIN_UNIQUE" in FakeClipboard.copied
    assert result.stdout == ""
    assert "Copied to clipboard" in result.stderr


def test_copy_failure_falls_back_to_stdout(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class FailingClipboard:
        def copy(self, text: str) -> ClipboardResult:
            return ClipboardResult(False, "", "no clipboard utilities")

    monkeypatch.setattr("pussy.cli.ClipboardManager", FailingClipboard)
    result = invoke(["generate", str(project), "--copy"])
    assert result.exit_code == 0
    assert "Clipboard copy failed" in result.stderr
    assert result.stdout.startswith("# Project Context")


def test_tree_only_omits_code(project: Path) -> None:
    result = invoke(["generate", str(project), "--tree-only"])
    assert result.exit_code == 0
    assert "Directory Structure" in result.stdout
    assert "Project Overview" not in result.stdout
    assert "MAIN_UNIQUE" not in result.stdout


def test_code_only_omits_overview(project: Path) -> None:
    result = invoke(["generate", str(project), "--code-only"])
    assert result.exit_code == 0
    assert "Project Overview" not in result.stdout
    assert "Directory Structure" not in result.stdout
    assert "Source Code" in result.stdout
    assert "MAIN_UNIQUE" in result.stdout


def test_tree_only_and_code_only_conflict(project: Path) -> None:
    result = invoke(["generate", str(project), "--tree-only", "--code-only"])
    assert result.exit_code == 2
    assert "cannot be used together" in result.output


def test_include_extensions(project: Path) -> None:
    result = invoke(["generate", str(project), "--include-ext", "py"])
    assert result.exit_code == 0
    assert "MAIN_UNIQUE" in result.stdout
    assert "README_UNIQUE_CONTENT" not in result.stdout


def test_exclude_pattern(project: Path) -> None:
    result = invoke(["generate", str(project), "--exclude", "*.md"])
    assert result.exit_code == 0
    assert "README_UNIQUE_CONTENT" not in result.stdout
    assert "MAIN_UNIQUE" in result.stdout


def test_explicit_include_overrides_exclude(project: Path) -> None:
    result = invoke(
        [
            "generate",
            str(project),
            "--exclude",
            "*.md",
            "--include",
            "README.md",
        ]
    )
    assert result.exit_code == 0
    assert "README_UNIQUE_CONTENT" in result.stdout


def test_max_size_skips_large_files(project: Path) -> None:
    result = invoke(["generate", str(project), "--max-size", "10"])
    assert result.exit_code == 0
    assert "MAIN_UNIQUE" not in result.stdout
    assert "exceeds limit" in result.stdout


def test_overview_mode_excludes_code(project: Path) -> None:
    result = invoke(["generate", str(project), "--mode", "overview"])
    assert result.exit_code == 0
    assert "Project Overview" in result.stdout
    assert "MAIN_UNIQUE" not in result.stdout


def test_hidden_files_option(project: Path, write_file) -> None:
    write_file(project, ".hidden.py", "HIDDEN_UNIQUE = True\n")
    included = invoke(["generate", str(project)])
    excluded = invoke(["generate", str(project), "--no-hidden"])
    assert "HIDDEN_UNIQUE" in included.stdout
    assert "HIDDEN_UNIQUE" not in excluded.stdout


def test_no_git_option(project: Path) -> None:
    result = invoke(["generate", str(project), "--no-git", "--format", "json"])
    payload = json.loads(result.stdout)
    assert payload["git"] is None


def test_invalid_mode(project: Path) -> None:
    result = invoke(["generate", str(project), "--mode", "everything"])
    assert result.exit_code == 2
    assert "invalid mode" in result.output


def test_invalid_format(project: Path) -> None:
    result = invoke(["generate", str(project), "--format", "yaml"])
    assert result.exit_code == 2
    assert "invalid format" in result.output


def test_invalid_tokenizer(project: Path) -> None:
    result = invoke(["generate", str(project), "--tokenizer", "magic"])
    assert result.exit_code == 2
    assert "invalid tokenizer" in result.output


def test_quiet_suppresses_status(project: Path) -> None:
    output = project / "context.md"
    result = invoke(["generate", str(project), "-o", str(output), "--quiet"])
    assert result.exit_code == 0
    assert result.stderr == ""


def test_config_table(project: Path) -> None:
    result = invoke(["config", str(project)])
    assert result.exit_code == 0
    assert "Resolved Configuration" in result.output
    assert "Max file size" in result.output


def test_config_json(project: Path) -> None:
    result = invoke(["config", str(project), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["mode"] == "context"
    assert payload["root"] == str(project.resolve())


def test_init_creates_ignore_file(project: Path) -> None:
    result = invoke(["init", str(project)])
    assert result.exit_code == 0
    ignore_file = project / ".pussyignore"
    assert ignore_file.is_file()
    assert "Pussy ignore" in ignore_file.read_text(encoding="utf-8")
    assert not (project / "pussy.toml").exists()


def test_init_skips_existing_file(project: Path) -> None:
    (project / ".pussyignore").write_text("# custom\n", encoding="utf-8")
    result = invoke(["init", str(project)])
    assert result.exit_code == 0
    assert "Skipped" in result.output
    assert (project / ".pussyignore").read_text(encoding="utf-8") == "# custom\n"


def test_init_force_and_config(project: Path) -> None:
    (project / ".pussyignore").write_text("# custom\n", encoding="utf-8")
    result = invoke(["init", str(project), "--with-config", "--force"])
    assert result.exit_code == 0
    assert (project / "pussy.toml").is_file()
    assert "Pussy ignore" in (project / ".pussyignore").read_text(encoding="utf-8")


def test_config_init_creates_user_config(
    project: Path, monkeypatch: pytest.MonkeyPatch, tmp_path_factory
) -> None:
    config_home = tmp_path_factory.mktemp("cli-config")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
    monkeypatch.setenv("APPDATA", str(config_home))
    result = invoke(["config", str(project), "--init"])
    assert result.exit_code == 0
    assert (config_home / "pussy" / "config.toml").is_file()

    again = invoke(["config", str(project), "--init"])
    assert again.exit_code == 3


def test_project_config_is_used(project: Path, write_file) -> None:
    write_file(project, "pussy.toml", '[output]\nmode = "overview"\n')
    result = invoke(["generate", str(project)])
    assert result.exit_code == 0
    assert "MAIN_UNIQUE" not in result.stdout


def test_empty_project_is_supported(tmp_path: Path) -> None:
    result = invoke(["generate", str(tmp_path)])
    assert result.exit_code == 0
    assert "# Project Context" in result.stdout
    assert "Not detected" in result.stdout


def test_unicode_paths(project: Path, write_file) -> None:
    write_file(project, "src/модуль.py", "UNICODE_UNIQUE = True\n")
    result = invoke(["generate", str(project)])
    assert result.exit_code == 0
    assert "UNICODE_UNIQUE" in result.stdout
    assert "модуль.py" in result.stdout


def test_terminal_output_has_no_ansi_when_disabled(project: Path) -> None:
    result = invoke(["scan", str(project)])
    assert "\x1b[" not in result.stdout
