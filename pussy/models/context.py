"""Context bundle and statistics models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from pussy.models.file_entry import FileEntry
from pussy.models.project import DependencyReport, GitInfo, ProjectInfo


@dataclass(slots=True)
class ContextStats:
    """Measurements for the generated context document."""

    files_included: int = 0
    files_excluded: int = 0
    total_files: int = 0
    characters: int = 0
    words: int = 0
    lines: int = 0
    bytes: int = 0
    estimated_tokens: int = 0
    tokenizer: str = "approximate"
    estimation_method: str = "approximate (characters / 4)"
    approximate: bool = True


@dataclass(slots=True)
class ContextBundle:
    """Everything needed by a formatter to render the final document."""

    project: ProjectInfo
    entries: list[FileEntry]
    tree: str
    dependencies: DependencyReport
    git: GitInfo | None
    stats: ContextStats
    mode: str = "context"
    tree_only: bool = False
    code_only: bool = False
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    warnings: list[str] = field(default_factory=list)

    def included_entries(self) -> list[FileEntry]:
        """Entries whose content belongs in the document."""
        return [entry for entry in self.entries if entry.included]

    def excluded_entries(self) -> list[FileEntry]:
        """Entries intentionally left out of the document."""
        return [entry for entry in self.entries if not entry.included]

    def content_entries(self) -> list[FileEntry]:
        """Included entries with readable content, sorted by path."""
        return sorted(
            (entry for entry in self.entries if entry.has_content),
            key=lambda entry: entry.relative_path.casefold(),
        )
