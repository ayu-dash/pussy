"""Gitignore-style ignore rule engine.

Rules are evaluated last-match-wins.  Directory rules use a trailing slash.
Patterns without a slash match a path segment at any depth; patterns with a
slash are anchored to the project root.  ``**`` crosses directory boundaries.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import PurePosixPath


def _translate_glob(pattern: str) -> str:
    """Translate a gitignore glob (without leading slash) to regex source."""
    output: list[str] = []
    index = 0
    length = len(pattern)
    while index < length:
        char = pattern[index]
        if char == "*":
            if index + 1 < length and pattern[index + 1] == "*":
                if index + 2 < length and pattern[index + 2] == "/":
                    output.append("(?:.*/)?")
                    index += 3
                else:
                    output.append(".*")
                    index += 2
            else:
                output.append("[^/]*")
                index += 1
        elif char == "?":
            output.append("[^/]")
            index += 1
        elif char == "[":
            closing = pattern.find("]", index + 1)
            if closing == -1:
                output.append(r"\[")
                index += 1
            else:
                content = pattern[index + 1 : closing]
                if content.startswith("!"):
                    content = "^" + content[1:]
                output.append(f"[{content}]")
                index = closing + 1
        else:
            output.append(re.escape(char))
            index += 1
    return "".join(output)


@dataclass(slots=True)
class IgnoreRule:
    """One compiled ignore/include pattern."""

    pattern: str
    source: str
    negated: bool = False
    directory_only: bool = False
    basename_only: bool = False
    regex: re.Pattern[str] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.regex = re.compile(f"^{_translate_glob(self.pattern)}$")

    def matches(self, relative_path: str, is_directory: bool) -> bool:
        """Return whether the rule matches a project-relative POSIX path."""
        if self.directory_only and not is_directory:
            return False
        if self.basename_only:
            return any(self.regex.match(part) is not None for part in relative_path.split("/"))
        return self.regex.match(relative_path) is not None


@dataclass(frozen=True, slots=True)
class IgnoreDecision:
    """Result of evaluating the rule list for one path."""

    ignored: bool
    pattern: str | None = None
    source: str | None = None


def parse_rule(raw: str, source: str) -> IgnoreRule | None:
    """Parse one ignore-file line into a rule, or return None for comments."""
    line = raw.strip()
    if not line:
        return None
    if line.startswith(r"\#"):
        line = line[1:]
    elif line.startswith("#"):
        return None

    negated = line.startswith("!")
    if negated:
        line = line[1:].lstrip()
    elif line.startswith(r"\!"):
        line = line[1:]

    directory_only = line.endswith("/")
    line = line.rstrip("/")
    if not line:
        return None

    anchored = line.startswith("/")
    line = line.lstrip("/")
    if "/" in line:
        anchored = True
    if not line:
        return None

    return IgnoreRule(
        pattern=line,
        source=source,
        negated=negated,
        directory_only=directory_only,
        basename_only=not anchored,
    )


class IgnoreManager:
    """Ordered collection of ignore rules with last-match-wins semantics."""

    def __init__(self, rules: Iterable[IgnoreRule] | None = None) -> None:
        self.rules: list[IgnoreRule] = list(rules or [])

    @classmethod
    def from_sources(
        cls,
        *,
        defaults: Iterable[str] = (),
        ignore_file_lines: Iterable[str] = (),
        config_patterns: Iterable[str] = (),
        cli_patterns: Iterable[str] = (),
        use_defaults: bool = True,
    ) -> IgnoreManager:
        """Build a manager in precedence order (last source wins)."""
        rules: list[IgnoreRule] = []
        sources = (
            (defaults if use_defaults else (), "default"),
            (ignore_file_lines, ".pussyignore"),
            (config_patterns, "config"),
            (cli_patterns, "cli"),
        )
        for patterns, source in sources:
            for raw in patterns:
                rule = parse_rule(raw, source)
                if rule is not None:
                    rules.append(rule)
        return cls(rules)

    def add(self, raw: str, source: str) -> None:
        """Append one rule."""
        rule = parse_rule(raw, source)
        if rule is not None:
            self.rules.append(rule)

    def decide(self, relative_path: str, is_directory: bool = False) -> IgnoreDecision:
        """Evaluate every rule and return the final decision."""
        relative_path = PurePosixPath(relative_path).as_posix()
        if relative_path.startswith("./"):
            relative_path = relative_path[2:]
        ignored = False
        pattern: str | None = None
        source: str | None = None
        for rule in self.rules:
            if rule.matches(relative_path, is_directory):
                ignored = not rule.negated
                pattern = rule.pattern
                source = rule.source
        return IgnoreDecision(ignored=ignored, pattern=pattern, source=source)

    def is_ignored(self, relative_path: str, is_directory: bool = False) -> bool:
        """Convenience wrapper around :meth:`decide`."""
        return self.decide(relative_path, is_directory).ignored

    @property
    def has_negations(self) -> bool:
        """Whether any negation rule is present."""
        return any(rule.negated for rule in self.rules)


class IncludeManager:
    """Explicit include patterns that override ignore rules.

    Only files that the scanner actually visits can be re-included.  To reach
    files inside an otherwise ignored directory, use a path-prefixed pattern
    (for example ``vendor/acme/lib.py``).
    """

    def __init__(self, patterns: Iterable[str], source: str = "include") -> None:
        self.rules: list[IgnoreRule] = []
        for raw in patterns:
            rule = parse_rule(raw, source)
            if rule is not None and not rule.negated:
                self.rules.append(rule)

    def matches_file(self, relative_path: str) -> bool:
        """Whether an explicit include rule matches this file path."""
        return any(rule.matches(relative_path, is_directory=False) for rule in self.rules)

    def may_match_under(self, relative_directory: str) -> bool:
        """Whether traversal should continue inside an ignored directory."""
        prefix = relative_directory.strip("/") + "/"
        for rule in self.rules:
            if rule.basename_only:
                continue
            normalised = rule.pattern.lstrip("/")
            if normalised.startswith("**/"):
                return True
            if normalised.startswith(prefix) or normalised == relative_directory.strip("/"):
                return True
        return False

    def __bool__(self) -> bool:
        return bool(self.rules)
