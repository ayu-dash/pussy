"""Configuration loading tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from pussy.config.loader import load_config, read_ignore_file, user_config_path
from pussy.config.models import PussyConfig
from pussy.errors import ConfigError
from pussy.utils.size import parse_size


def test_defaults_and_ignore_file(tmp_path: Path, write_file) -> None:
    write_file(tmp_path, ".pussyignore", "dist/\n*.log\n")
    config = load_config(tmp_path)
    assert config.root == tmp_path.resolve()
    assert config.mode == "context"
    assert config.output_format == "markdown"
    assert config.ignore_file == tmp_path / ".pussyignore"


def test_project_toml_overrides_defaults(tmp_path: Path, write_file) -> None:
    write_file(
        tmp_path,
        "pussy.toml",
        """
[scan]
include_hidden = false
max_file_size = "2MB"
max_total_size = 1024

[include]
extensions = ["py", ".ts"]
patterns = ["vendor/keep.py"]
exclude_extensions = ["log"]

[output]
format = "json"
mode = "full"

[git]
enabled = false
include_diff = true

[tokens]
tokenizer = "tiktoken"
model = "gpt-4o"
""",
    )
    config = load_config(tmp_path)
    assert not config.include_hidden
    assert config.max_file_size == 2 * 1024 * 1024
    assert config.max_total_size == 1024
    assert config.include_extensions == {".py", ".ts"}
    assert config.exclude_extensions == {".log"}
    assert config.include_patterns == ["vendor/keep.py"]
    assert config.mode == "full"
    assert config.output_format == "json"
    assert not config.include_git
    assert config.include_git_diff
    assert config.tokenizer == "tiktoken"
    assert config.model == "gpt-4o"
    assert config.config_files == [tmp_path / "pussy.toml"]


def test_explicit_config_has_highest_precedence(tmp_path: Path, write_file, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "user-config"))
    user_file = tmp_path / "user-config" / "pussy" / "config.toml"
    user_file.parent.mkdir(parents=True)
    user_file.write_text('[output]\nmode = "overview"\n', encoding="utf-8")
    write_file(tmp_path, "pussy.toml", '[output]\nmode = "context"\n')
    explicit = write_file(tmp_path, "custom.toml", '[output]\nmode = "full"\n')

    config = load_config(tmp_path, explicit)
    assert config.mode == "full"
    assert len(config.config_files) == 3


def test_user_config_is_loaded(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    user_file = tmp_path / "xdg" / "pussy" / "config.toml"
    user_file.parent.mkdir(parents=True)
    user_file.write_text('[output]\nformat = "json"\n', encoding="utf-8")
    config = load_config(tmp_path)
    assert config.output_format == "json"
    assert user_file in config.config_files


def test_invalid_toml_raises_config_error(tmp_path: Path, write_file) -> None:
    write_file(tmp_path, "pussy.toml", "[output\n")
    with pytest.raises(ConfigError, match="invalid TOML"):
        load_config(tmp_path)


def test_invalid_section_type_raises(tmp_path: Path, write_file) -> None:
    write_file(tmp_path, "pussy.toml", 'output = "json"\n')
    with pytest.raises(ConfigError, match="must be a table"):
        load_config(tmp_path)


def test_invalid_choice_raises(tmp_path: Path, write_file) -> None:
    write_file(tmp_path, "pussy.toml", '[output]\nformat = "yaml"\n')
    with pytest.raises(ConfigError, match="format"):
        load_config(tmp_path)


def test_invalid_size_raises(tmp_path: Path, write_file) -> None:
    write_file(tmp_path, "pussy.toml", '[scan]\nmax_file_size = "huge"\n')
    with pytest.raises(ConfigError, match="max_file_size"):
        load_config(tmp_path)


def test_missing_explicit_config_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path, tmp_path / "missing.toml")


def test_user_config_path_platform(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert user_config_path() == tmp_path / "pussy" / "config.toml"


def test_read_ignore_file_handles_bom(tmp_path: Path) -> None:
    path = tmp_path / ".pussyignore"
    path.write_bytes(b"\xef\xbb\xbfdist/\n*.log\n")
    assert read_ignore_file(path) == ["dist/", "*.log"]


def test_read_ignore_file_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="cannot read"):
        read_ignore_file(tmp_path / "missing")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1MB", 1024 * 1024),
        ("1 MiB", 1024 * 1024),
        ("512KB", 512 * 1024),
        ("2gb", 2 * 1024**3),
        (100, 100),
    ],
)
def test_parse_size(value, expected) -> None:
    assert parse_size(value) == expected


@pytest.mark.parametrize("value", ["abc", "-1MB", "10XB"])
def test_parse_size_invalid(value: str) -> None:
    with pytest.raises(ValueError):
        parse_size(value)


def test_config_validation_rejects_missing_root(tmp_path: Path) -> None:
    config = PussyConfig(root=tmp_path / "missing")
    with pytest.raises(ConfigError, match="does not exist"):
        config.validate()


def test_config_validation_rejects_file_root(tmp_path: Path, write_file) -> None:
    path = write_file(tmp_path, "file.txt", "x")
    config = PussyConfig(root=path)
    with pytest.raises(ConfigError, match="not a directory"):
        config.validate()


def test_config_validation_rejects_bad_mode(tmp_path: Path) -> None:
    config = PussyConfig(root=tmp_path, mode="everything")
    with pytest.raises(ConfigError, match="invalid mode"):
        config.validate()


def test_config_validation_rejects_bad_tokenizer(tmp_path: Path) -> None:
    config = PussyConfig(root=tmp_path, tokenizer="magic")
    with pytest.raises(ConfigError, match="invalid tokenizer"):
        config.validate()
