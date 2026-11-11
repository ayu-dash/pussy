"""Project-level data models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Technology:
    """A detected technology and the evidence that proved it."""

    name: str
    kind: str  # language | framework | package_manager | platform
    evidence: str = ""


@dataclass(frozen=True, slots=True)
class Dependency:
    """One declared dependency extracted from a manifest."""

    name: str
    version: str = ""
    scope: str = "production"  # production | development | optional | build
    source: str = ""

    def display(self) -> str:
        """Return ``name version`` or just the name."""
        return f"{self.name} {self.version}".strip()


@dataclass(frozen=True, slots=True)
class GitChange:
    """One working-tree change reported by ``git status``."""

    status: str
    path: str


@dataclass(slots=True)
class GitInfo:
    """Read-only snapshot of a Git repository."""

    is_repo: bool = False
    repository_root: str | None = None
    branch: str | None = None
    commit_hash: str | None = None
    commit_short: str | None = None
    commit_subject: str | None = None
    commit_author: str | None = None
    commit_date: str | None = None
    changes: list[GitChange] = field(default_factory=list)
    diff: str | None = None
    error: str | None = None
    available: bool = True

    @property
    def modified(self) -> list[str]:
        """Paths with a modified status."""
        return [change.path for change in self.changes if change.status == "modified"]

    @property
    def added(self) -> list[str]:
        """Paths with an added status."""
        return [change.path for change in self.changes if change.status == "added"]

    @property
    def deleted(self) -> list[str]:
        """Paths with a deleted status."""
        return [change.path for change in self.changes if change.status == "deleted"]

    @property
    def untracked(self) -> list[str]:
        """Paths with an untracked status."""
        return [change.path for change in self.changes if change.status == "untracked"]

    @property
    def renamed(self) -> list[str]:
        """Paths with a renamed status."""
        return [change.path for change in self.changes if change.status == "renamed"]

    @property
    def is_dirty(self) -> bool:
        """Whether the working tree contains any change."""
        return bool(self.changes)


@dataclass(slots=True)
class ProjectInfo:
    """Facts about the scanned project, derived from real files only."""

    name: str
    root: str
    languages: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)
    package_managers: list[str] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)
    config_files: list[str] = field(default_factory=list)
    technologies: list[Technology] = field(default_factory=list)
    total_files: int = 0
    total_directories: int = 0
    total_size: int = 0
    category_counts: dict[str, int] = field(default_factory=dict)
    included_count: int = 0
    excluded_count: int = 0
    skipped_directories: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    dependency_count: int = 0


@dataclass(slots=True)
class DependencyReport:
    """Dependencies plus provenance and non-fatal parse warnings."""

    dependencies: list[Dependency] = field(default_factory=list)
    files_analyzed: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def by_scope(self) -> dict[str, list[Dependency]]:
        """Group dependencies by scope, preserving a stable order."""
        grouped: dict[str, list[Dependency]] = {}
        for dependency in self.dependencies:
            grouped.setdefault(dependency.scope, []).append(dependency)
        return grouped
