"""Ignore manager and sensitive-file policy tests."""

from __future__ import annotations

import pytest

from pussy.config.defaults import DEFAULT_IGNORE_PATTERNS
from pussy.filters.ignore import (
    IgnoreManager,
    IncludeManager,
    parse_rule,
)
from pussy.filters.sensitive import is_sensitive_path


@pytest.fixture
def defaults() -> IgnoreManager:
    return IgnoreManager.from_sources(defaults=DEFAULT_IGNORE_PATTERNS)


def test_default_directories_are_ignored(defaults: IgnoreManager) -> None:
    assert defaults.is_ignored("node_modules", is_directory=True)
    assert defaults.is_ignored("src/node_modules", is_directory=True)
    assert defaults.is_ignored(".venv", is_directory=True)
    assert defaults.is_ignored("__pycache__", is_directory=True)


def test_default_patterns_do_not_hide_project_content(defaults: IgnoreManager) -> None:
    assert not defaults.is_ignored("src/main.py")
    assert not defaults.is_ignored("storage/app/uploads", is_directory=True)
    assert not defaults.is_ignored("public", is_directory=True)
    assert not defaults.is_ignored("assets", is_directory=True)


def test_glob_matches_nested_files(defaults: IgnoreManager) -> None:
    assert defaults.is_ignored("debug.log")
    assert defaults.is_ignored("logs/debug.log")


def test_directory_pattern_does_not_match_regular_file() -> None:
    manager = IgnoreManager.from_sources(defaults=["build/"])
    assert manager.is_ignored("build", is_directory=True)
    assert not manager.is_ignored("build", is_directory=False)
    assert manager.is_ignored("packages/app/build", is_directory=True)


def test_anchored_pattern_only_matches_root() -> None:
    manager = IgnoreManager.from_sources(defaults=["/config.yml"])
    assert manager.is_ignored("config.yml")
    assert not manager.is_ignored("backend/config.yml")


def test_anchored_path_pattern() -> None:
    manager = IgnoreManager.from_sources(defaults=["docs/internal/**"])
    assert manager.is_ignored("docs/internal/secret.md")
    assert not manager.is_ignored("docs/public/guide.md")


def test_double_star_matches_root_and_nested() -> None:
    manager = IgnoreManager.from_sources(defaults=["**/*.py"])
    assert manager.is_ignored("main.py")
    assert manager.is_ignored("src/deep/main.py")
    assert not manager.is_ignored("main.js")


def test_negation_last_match_wins() -> None:
    manager = IgnoreManager.from_sources(defaults=["*.log", "!important.log", "important.log"])
    assert manager.is_ignored("important.log")
    assert manager.is_ignored("debug.log")

    manager = IgnoreManager.from_sources(defaults=["*.log", "!important.log"])
    assert not manager.is_ignored("important.log")
    assert not manager.is_ignored("nested/important.log")


def test_cli_source_overrides_config_source() -> None:
    manager = IgnoreManager.from_sources(
        defaults=["*.tmp"],
        config_patterns=["*.log"],
        cli_patterns=["!debug.log"],
    )
    assert manager.is_ignored("debug.log") is False
    assert manager.is_ignored("other.log") is True


def test_comments_blank_lines_and_escaped_hash() -> None:
    manager = IgnoreManager.from_sources(defaults=["", "# a comment", "   ", r"\#keep.txt"])
    assert len(manager.rules) == 1
    assert manager.is_ignored("#keep.txt")


def test_character_class() -> None:
    manager = IgnoreManager.from_sources(defaults=["file[0-9].txt"])
    assert manager.is_ignored("file3.txt")
    assert not manager.is_ignored("filex.txt")


def test_question_mark_single_character() -> None:
    manager = IgnoreManager.from_sources(defaults=["temp?.txt"])
    assert manager.is_ignored("temp1.txt")
    assert not manager.is_ignored("temp12.txt")


def test_unicode_pattern() -> None:
    manager = IgnoreManager.from_sources(defaults=["файл*.txt"])
    assert manager.is_ignored("файл-данные.txt")


def test_responsibility_sources_and_patterns() -> None:
    manager = IgnoreManager.from_sources(defaults=[], ignore_file_lines=["dist/"])
    decision = manager.decide("dist", is_directory=True)
    assert decision.ignored
    assert decision.source == ".pussyignore"
    assert decision.pattern == "dist"


@pytest.mark.parametrize(
    "path",
    [
        ".env",
        ".env.local",
        ".env.production",
        "config/.env",
        "cert.pem",
        "private.key",
        "bundle.p12",
        "credentials.json",
        "secrets.json",
        ".ssh/id_rsa",
        "keys/id_ed25519",
    ],
)
def test_sensitive_files_are_detected(path: str) -> None:
    assert is_sensitive_path(path)


@pytest.mark.parametrize(
    "path",
    [
        ".env.example",
        ".env.sample",
        ".env.template",
        "credentials.example.json",
        "src/main.py",
        "src/secret_scanner.py",
        "README.md",
    ],
)
def test_safe_files_are_not_sensitive(path: str) -> None:
    assert not is_sensitive_path(path)


def test_sensitive_check_does_not_depend_on_ignore_rules() -> None:
    manager = IgnoreManager.from_sources(defaults=["!.env", "!*.pem"])
    assert not manager.is_ignored(".env")
    assert is_sensitive_path(".env")
    assert is_sensitive_path("cert.pem")


def test_include_manager_matches_and_allows_traversal() -> None:
    includes = IncludeManager(["vendor/acme/lib.py", "*.md"])
    assert includes.matches_file("vendor/acme/lib.py")
    assert includes.matches_file("docs/guide.md")
    assert includes.may_match_under("vendor")
    assert includes.may_match_under("vendor/acme")
    assert not includes.may_match_under("node_modules")


def test_include_manager_double_star_allows_any_directory() -> None:
    includes = IncludeManager(["**/keep.py"])
    assert includes.may_match_under("vendor")


def test_parse_rule_rejects_blank_and_slash_only() -> None:
    assert parse_rule("", "test") is None
    assert parse_rule("/", "test") is None
    assert parse_rule("# comment", "test") is None
