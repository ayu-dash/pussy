"""Shared pytest fixtures.

Every test runs with isolated user configuration so a developer's real
``~/.config/pussy/config.toml`` can never influence assertions.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pussy.config.models import PussyConfig
from pussy.core.classifier import classify_entries
from pussy.core.pipeline import generate_context
from pussy.core.scanner import Scanner, ScanResult
from pussy.filters.ignore import IgnoreManager


@pytest.fixture(autouse=True)
def isolated_user_config(monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory):
    base = tmp_path_factory.mktemp("config-home")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(base))
    monkeypatch.setenv("APPDATA", str(base))
    yield


@pytest.fixture
def write_file():
    def _write(root: Path, relative: str, content: str | bytes = "") -> Path:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
        return path

    return _write


@pytest.fixture
def collect():
    def _collect(
        root: Path,
        ignore: IgnoreManager | None = None,
        **scanner_options: object,
    ) -> ScanResult:
        scanner = Scanner(root, ignore or IgnoreManager([]), **scanner_options)
        result = scanner.scan()
        classify_entries(result.files)
        return result

    return _collect


@pytest.fixture
def build_bundle():
    def _build(
        root: Path,
        *,
        mode: str = "context",
        tree_only: bool = False,
        code_only: bool = False,
        **config_options: object,
    ):
        config = PussyConfig(root=root, include_git=False, mode=mode, **config_options)
        return generate_context(config, tree_only=tree_only, code_only=code_only)

    return _build
