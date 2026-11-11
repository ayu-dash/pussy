"""Read-only Git repository analysis."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from pussy.config.defaults import DEFAULT_MAX_DIFF_CHARS, DEFAULT_TIMEOUT_SECONDS
from pussy.filters.sensitive import is_sensitive_path
from pussy.models.project import GitChange, GitInfo

_CREDENTIAL_URL = re.compile(r"(https?://)[^/\s@]+@", re.IGNORECASE)


def _sanitize(text: str) -> str:
    """Remove embedded credentials from Git output."""
    return _CREDENTIAL_URL.sub(r"\1***@", text)


def _run_git(
    root: Path, arguments: list[str], timeout: int = DEFAULT_TIMEOUT_SECONDS
) -> tuple[int, str, str]:
    command = ["git", "-c", "core.quotepath=false", *arguments]
    environment = os.environ.copy()
    environment["GIT_TERMINAL_PROMPT"] = "0"
    environment["LC_ALL"] = "C"
    environment.pop("GIT_DIR", None)
    environment.pop("GIT_WORK_TREE", None)
    try:
        completed = subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="surrogateescape",
            timeout=timeout,
            check=False,
            env=environment,
        )
    except FileNotFoundError:
        return 127, "", "git executable not found"
    except subprocess.TimeoutExpired:
        return 124, "", "git command timed out"
    except OSError as exc:
        return 126, "", f"cannot execute git: {exc}"
    return completed.returncode, completed.stdout, _sanitize(completed.stderr.strip())


def _parse_status(output: str) -> list[GitChange]:
    changes: list[GitChange] = []
    tokens = output.split("\0")
    index = 0
    while index < len(tokens):
        token = tokens[index]
        index += 1
        if len(token) < 3:
            continue
        code = token[:2]
        path = token[3:]
        if code[0] == "R" or code[1] == "R":
            # The following token is the original path for renames.
            index += 1
            changes.append(GitChange("renamed", path))
            continue
        if code == "??":
            status = "untracked"
        elif "A" in code:
            status = "added"
        elif "D" in code:
            status = "deleted"
        elif "U" in code or "M" in code or "T" in code:
            status = "modified"
        elif "R" in code:
            status = "renamed"
        else:
            status = "modified"
        changes.append(GitChange(status, path))
    return changes


def _filter_sensitive_diff(diff: str) -> str:
    """Drop diff sections for sensitive paths so secrets never reach output."""
    sections: list[str] = []
    current: list[str] = []
    current_path: str | None = None

    def flush() -> None:
        nonlocal current, current_path
        if current and (current_path is None or not is_sensitive_path(current_path)):
            sections.append("".join(current))
        current = []
        current_path = None

    for line in diff.splitlines(keepends=True):
        if line.startswith("diff --git "):
            flush()
            match = re.match(r"diff --git a/(.*?) b/(.*?)\s*$", line.rstrip("\n"))
            if match:
                current_path = match.group(2)
        current.append(line)
    flush()
    return "".join(sections)


class GitAnalyzer:
    """Collect branch, commit, status and optional diff information."""

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        max_diff_chars: int = DEFAULT_MAX_DIFF_CHARS,
    ) -> None:
        self.timeout = timeout
        self.max_diff_chars = max_diff_chars

    def analyze(self, root: Path, include_diff: bool = False) -> GitInfo:
        """Analyze *root* without modifying the repository."""
        info = GitInfo()
        code, stdout, stderr = _run_git(root, ["rev-parse", "--is-inside-work-tree"], self.timeout)
        if code == 127:
            info.available = False
            info.error = stderr or "git executable not found"
            return info
        if code != 0 or stdout.strip() != "true":
            info.error = stderr if code in {124, 126} and stderr else "not a Git repository"
            return info

        info.is_repo = True
        code, stdout, _stderr = _run_git(root, ["rev-parse", "--show-toplevel"], self.timeout)
        if code == 0:
            info.repository_root = stdout.strip()

        code, stdout, _stderr = _run_git(
            root, ["symbolic-ref", "--short", "-q", "HEAD"], self.timeout
        )
        if code == 0 and stdout.strip():
            info.branch = stdout.strip()

        code, stdout, _stderr = _run_git(
            root,
            ["log", "-1", "--pretty=format:%H%x00%h%x00%an%x00%aI%x00%s"],
            self.timeout,
        )
        if code == 0 and stdout:
            parts = stdout.split("\0")
            if len(parts) >= 5:
                (
                    info.commit_hash,
                    info.commit_short,
                    info.commit_author,
                    info.commit_date,
                    info.commit_subject,
                ) = parts[:5]

        code, stdout, stderr = _run_git(
            root,
            ["status", "--porcelain=v1", "-z", "--untracked-files=normal"],
            self.timeout,
        )
        if code == 0:
            info.changes = _parse_status(stdout)
        else:
            info.error = stderr or "git status failed"

        if include_diff:
            diff = self._read_diff(root)
            if diff:
                info.diff = diff
        return info

    def _read_diff(self, root: Path) -> str:
        code, stdout, _stderr = _run_git(
            root,
            ["diff", "--no-color", "--no-ext-diff", "HEAD"],
            self.timeout,
        )
        if code != 0 or not stdout:
            code, stdout, _stderr = _run_git(
                root,
                ["diff", "--no-color", "--no-ext-diff"],
                self.timeout,
            )
        if code != 0 or not stdout:
            return ""
        filtered = _filter_sensitive_diff(stdout)
        if len(filtered) > self.max_diff_chars:
            filtered = (
                filtered[: self.max_diff_chars]
                + f"\n... [diff truncated at {self.max_diff_chars} characters]\n"
            )
        return filtered
