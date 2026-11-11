"""TOML configuration discovery and loading."""

from __future__ import annotations

import os
import sys
import tomllib
from pathlib import Path
from typing import Any

from pussy.config.defaults import (
    DEFAULT_MAX_DIFF_CHARS,
    DEFAULT_MAX_FILE_SIZE,
    DEFAULT_MAX_TOTAL_SIZE,
    IGNORE_FILENAME,
    PROJECT_CONFIG_FILENAME,
)
from pussy.config.models import VALID_FORMATS, VALID_MODES, VALID_TOKENIZERS, PussyConfig
from pussy.errors import ConfigError
from pussy.utils.size import parse_size


def user_config_path() -> Path:
    """Return the platform-appropriate user configuration path."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "pussy" / "config.toml"


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"invalid TOML in {path}: {exc}") from exc
    except OSError as exc:
        raise ConfigError(f"cannot read configuration {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"configuration {path} must contain a TOML table")
    return data


def _table(data: dict[str, Any], section: str) -> dict[str, Any]:
    value = data.get(section, {})
    if not isinstance(value, dict):
        raise ConfigError(f"configuration section [{section}] must be a table")
    return value


def _string_list(value: Any, key: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ConfigError(f"{key} must be a list of strings")
    return [item.strip() for item in value if item.strip()]


def _bool(value: Any, key: str, default: bool) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        raise ConfigError(f"{key} must be a boolean")
    return value


def _size(value: Any, key: str, default: int) -> int:
    if value is None:
        return default
    try:
        return parse_size(value)
    except ValueError as exc:
        raise ConfigError(f"{key}: {exc}") from exc


def _choice(value: Any, key: str, default: str, choices: tuple[str, ...]) -> str:
    if value is None:
        return default
    if not isinstance(value, str) or value.lower() not in choices:
        raise ConfigError(f"{key} must be one of: {', '.join(choices)}")
    return value.lower()


def _normalize_extensions(values: list[str]) -> set[str]:
    normalized: set[str] = set()
    for value in values:
        for part in value.split(","):
            part = part.strip().lower()
            if not part:
                continue
            normalized.add(part if part.startswith(".") else f".{part}")
    return normalized


def _apply_file(config: PussyConfig, data: dict[str, Any], path: Path) -> None:
    scan = _table(data, "scan")
    config.include_hidden = _bool(
        scan.get("include_hidden"), "scan.include_hidden", config.include_hidden
    )
    config.follow_symlinks = _bool(
        scan.get("follow_symlinks"), "scan.follow_symlinks", config.follow_symlinks
    )
    config.max_file_size = _size(
        scan.get("max_file_size"), "scan.max_file_size", config.max_file_size
    )
    config.max_total_size = _size(
        scan.get("max_total_size"), "scan.max_total_size", config.max_total_size
    )

    ignore = _table(data, "ignore")
    config.use_default_ignores = _bool(
        ignore.get("use_defaults"), "ignore.use_defaults", config.use_default_ignores
    )
    config.ignore_patterns.extend(_string_list(ignore.get("patterns"), "ignore.patterns"))

    include = _table(data, "include")
    config.include_extensions |= _normalize_extensions(
        _string_list(include.get("extensions"), "include.extensions")
    )
    config.exclude_extensions |= _normalize_extensions(
        _string_list(include.get("exclude_extensions"), "include.exclude_extensions")
    )
    config.include_patterns.extend(_string_list(include.get("patterns"), "include.patterns"))

    output = _table(data, "output")
    config.output_format = _choice(
        output.get("format"), "output.format", config.output_format, VALID_FORMATS
    )
    config.mode = _choice(output.get("mode"), "output.mode", config.mode, VALID_MODES)

    git = _table(data, "git")
    config.include_git = _bool(git.get("enabled"), "git.enabled", config.include_git)
    config.include_git_diff = _bool(
        git.get("include_diff"), "git.include_diff", config.include_git_diff
    )
    config.max_diff_chars = _size(
        git.get("max_diff_chars"), "git.max_diff_chars", config.max_diff_chars
    )

    tokens = _table(data, "tokens")
    config.tokenizer = _choice(
        tokens.get("tokenizer"), "tokens.tokenizer", config.tokenizer, VALID_TOKENIZERS
    )
    model = tokens.get("model")
    if model is not None and not isinstance(model, str):
        raise ConfigError("tokens.model must be a string")
    if model:
        config.model = model

    config.config_files.append(path)


def load_config(
    root: Path,
    explicit_config: Path | None = None,
    *,
    load_user_config: bool = True,
) -> PussyConfig:
    """Build a configuration by merging user, project and explicit TOML files.

    Precedence (lowest to highest): built-in defaults, user config, project
    ``pussy.toml``, explicit ``--config`` file.  CLI flags are applied by the
    caller after this function returns.
    """
    root = root.expanduser().resolve()
    config = PussyConfig(root=root)

    if load_user_config:
        candidate = user_config_path()
        if candidate.is_file():
            _apply_file(config, _read_toml(candidate), candidate)

    project_config = root / PROJECT_CONFIG_FILENAME
    if project_config.is_file() and (
        explicit_config is None
        or project_config.resolve() != explicit_config.expanduser().resolve()
    ):
        _apply_file(config, _read_toml(project_config), project_config)

    if explicit_config is not None:
        path = explicit_config.expanduser().resolve()
        if not path.is_file():
            raise ConfigError(f"configuration file not found: {path}")
        _apply_file(config, _read_toml(path), path)

    ignore_file = root / IGNORE_FILENAME
    if ignore_file.is_file():
        config.ignore_file = ignore_file
    return config


def read_ignore_file(path: Path) -> list[str]:
    """Read ignore patterns from a ``.pussyignore`` file."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise ConfigError(f"cannot read ignore file {path}: {exc}") from exc
    return text.splitlines()


__all__ = [
    "DEFAULT_MAX_DIFF_CHARS",
    "DEFAULT_MAX_FILE_SIZE",
    "DEFAULT_MAX_TOTAL_SIZE",
    "load_config",
    "read_ignore_file",
    "user_config_path",
]
