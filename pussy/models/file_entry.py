"""File-level data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class FileCategory(StrEnum):
    """Functional classification of a file."""

    SOURCE_CODE = "source_code"
    CONFIGURATION = "configuration"
    DOCUMENTATION = "documentation"
    DATABASE = "database"
    TESTS = "tests"
    INFRASTRUCTURE = "infrastructure"
    ASSETS = "assets"
    GENERATED = "generated"
    DEPENDENCIES = "dependencies"
    BINARY = "binary"
    SENSITIVE = "sensitive"
    UNKNOWN = "unknown"

    @property
    def label(self) -> str:
        """Human-readable category name."""
        return _CATEGORY_LABELS[self]


_CATEGORY_LABELS: dict[FileCategory, str] = {
    FileCategory.SOURCE_CODE: "Source Code",
    FileCategory.CONFIGURATION: "Configuration",
    FileCategory.DOCUMENTATION: "Documentation",
    FileCategory.DATABASE: "Database",
    FileCategory.TESTS: "Tests",
    FileCategory.INFRASTRUCTURE: "Infrastructure",
    FileCategory.ASSETS: "Assets",
    FileCategory.GENERATED: "Generated",
    FileCategory.DEPENDENCIES: "Dependencies",
    FileCategory.BINARY: "Binary",
    FileCategory.SENSITIVE: "Sensitive",
    FileCategory.UNKNOWN: "Unknown",
}

CATEGORY_ORDER: tuple[FileCategory, ...] = (
    FileCategory.SOURCE_CODE,
    FileCategory.CONFIGURATION,
    FileCategory.DOCUMENTATION,
    FileCategory.DATABASE,
    FileCategory.TESTS,
    FileCategory.INFRASTRUCTURE,
    FileCategory.ASSETS,
    FileCategory.GENERATED,
    FileCategory.DEPENDENCIES,
    FileCategory.UNKNOWN,
    FileCategory.BINARY,
    FileCategory.SENSITIVE,
)


class ReadStatus(StrEnum):
    """Outcome of attempting to load a file's content."""

    NOT_READ = "not_read"
    READ = "read"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass(slots=True)
class FileEntry:
    """Metadata and (optionally) content for one project file.

    The scanner creates entries with :attr:`content` set to ``None``.  Only
    :class:`pussy.core.reader.FileReader` is allowed to populate content, and it
    refuses to do so for excluded or sensitive entries.
    """

    path: Path
    relative_path: str
    category: FileCategory = FileCategory.UNKNOWN
    language: str | None = None
    size: int = 0
    modified_at: float | None = None
    is_binary: bool = False
    is_sensitive: bool = False
    is_symlink: bool = False
    included: bool = True
    exclusion_reason: str | None = None
    read_status: ReadStatus = ReadStatus.NOT_READ
    content: str | None = None
    error: str | None = None
    encoding: str | None = None
    line_count: int = 0
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def name(self) -> str:
        """Base filename."""
        return self.path.name

    @property
    def suffix(self) -> str:
        """Lowercase final suffix, including the dot."""
        return self.path.suffix.lower()

    @property
    def has_content(self) -> bool:
        """Whether readable text content is present."""
        return self.read_status is ReadStatus.READ and self.content is not None

    def exclude(self, reason: str) -> None:
        """Mark the entry as excluded and drop any loaded content."""
        self.included = False
        self.exclusion_reason = reason
        self.content = None
        self.read_status = ReadStatus.SKIPPED
