"""Read-only Git analyzer tests."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from pussy.analyzers.git_analyzer import GitAnalyzer

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")


def git(root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def init_repo(root: Path) -> None:
    git(root, "init", "-q")
    git(root, "config", "user.email", "test@example.com")
    git(root, "config", "user.name", "Test User")
    git(root, "config", "commit.gpgsign", "false")


def test_not_a_repository(tmp_path: Path) -> None:
    info = GitAnalyzer().analyze(tmp_path)
    assert not info.is_repo
    assert info.error == "not a Git repository"


def test_branch_commit_and_clean_tree(tmp_path: Path, write_file) -> None:
    init_repo(tmp_path)
    write_file(tmp_path, "main.py", "print('hello')\n")
    git(tmp_path, "add", "main.py")
    git(tmp_path, "commit", "-q", "-m", "Initial commit")
    info = GitAnalyzer().analyze(tmp_path)
    assert info.is_repo
    assert info.branch
    assert info.commit_subject == "Initial commit"
    assert info.commit_author == "Test User"
    assert info.commit_hash
    assert not info.is_dirty


def test_status_categories(tmp_path: Path, write_file) -> None:
    init_repo(tmp_path)
    write_file(tmp_path, "modified.py", "one\n")
    write_file(tmp_path, "deleted.py", "gone\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "base")

    write_file(tmp_path, "modified.py", "two\n")
    write_file(tmp_path, "untracked.py", "new\n")
    (tmp_path / "deleted.py").unlink()
    info = GitAnalyzer().analyze(tmp_path)
    assert "modified.py" in info.modified
    assert "untracked.py" in info.untracked
    assert "deleted.py" in info.deleted


def test_diff_is_optional_and_content_is_captured(tmp_path: Path, write_file) -> None:
    init_repo(tmp_path)
    write_file(tmp_path, "main.py", "value = 1\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "base")
    write_file(tmp_path, "main.py", "value = 2\n")

    without_diff = GitAnalyzer().analyze(tmp_path)
    assert without_diff.diff is None

    with_diff = GitAnalyzer().analyze(tmp_path, include_diff=True)
    assert with_diff.diff is not None
    assert "value = 2" in with_diff.diff


def test_sensitive_diff_sections_are_removed(tmp_path: Path, write_file) -> None:
    init_repo(tmp_path)
    write_file(tmp_path, ".env", "SECRET=old\n")
    write_file(tmp_path, "main.py", "value = 1\n")
    git(tmp_path, "add", ".env", "main.py")
    git(tmp_path, "commit", "-q", "-m", "base")
    write_file(tmp_path, ".env", "SECRET=super-secret-value\n")
    write_file(tmp_path, "main.py", "value = 3\n")

    info = GitAnalyzer().analyze(tmp_path, include_diff=True)
    assert info.diff is not None
    assert "super-secret-value" not in info.diff
    assert "value = 3" in info.diff


def test_diff_is_truncated(tmp_path: Path, write_file) -> None:
    init_repo(tmp_path)
    write_file(tmp_path, "data.txt", "a\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "base")
    write_file(tmp_path, "data.txt", "b" * 500 + "\n")
    info = GitAnalyzer(max_diff_chars=80).analyze(tmp_path, include_diff=True)
    assert info.diff is not None
    assert "truncated" in info.diff


def test_repository_root_is_reported_for_subdirectory(tmp_path: Path, write_file) -> None:
    init_repo(tmp_path)
    write_file(tmp_path, "backend/main.py", "x = 1\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "base")
    info = GitAnalyzer().analyze(tmp_path / "backend")
    assert info.is_repo
    assert info.repository_root == str(tmp_path.resolve())


def test_missing_git_executable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def missing(*args: object, **kwargs: object):
        raise FileNotFoundError

    monkeypatch.setattr("pussy.analyzers.git_analyzer.subprocess.run", missing)
    info = GitAnalyzer().analyze(tmp_path)
    assert not info.available
    assert "not found" in (info.error or "")


def test_git_timeout_is_reported(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def timeout(*args: object, **kwargs: object):
        raise subprocess.TimeoutExpired(cmd="git", timeout=1)

    monkeypatch.setattr("pussy.analyzers.git_analyzer.subprocess.run", timeout)
    info = GitAnalyzer().analyze(tmp_path)
    assert "timed out" in (info.error or "")
