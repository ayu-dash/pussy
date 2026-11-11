"""Runtime configuration model."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pussy.config.defaults import (
    DEFAULT_MAX_DIFF_CHARS,
    DEFAULT_MAX_FILE_SIZE,
    DEFAULT_MAX_TOTAL_SIZE,
)
from pussy.errors import ConfigError

VALID_MODES = ("overview", "context", "full")
VALID_FORMATS = ("markdown", "json")
VALID_TOKENIZERS = ("auto", "approximate", "tiktoken")


@dataclass(slots=True)
class PussyConfig:
    """Resolved configuration used by every pipeline stage."""

    root: Path
    ignore_patterns: list[str] = field(default_factory=list)
    cli_ignore_patterns: list[str] = field(default_factory=list)
    include_patterns: list[str] = field(default_factory=list)
    include_extensions: set[str] = field(default_factory=set)
    exclude_extensions: set[str] = field(default_factory=set)
    use_default_ignores: bool = True
    include_hidden: bool = True
    follow_symlinks: bool = False
    max_file_size: int = DEFAULT_MAX_FILE_SIZE
    max_total_size: int = DEFAULT_MAX_TOTAL_SIZE
    mode: str = "context"
    output_format: str = "markdown"
    include_git: bool = True
    include_git_diff: bool = False
    max_diff_chars: int = DEFAULT_MAX_DIFF_CHARS
    tokenizer: str = "auto"
    model: str | None = None
    show_progress: bool = True
    quiet: bool = False
    exclude_paths: list[Path] = field(default_factory=list)
    config_files: list[Path] = field(default_factory=list)
    ignore_file: Path | None = None
    warnings: list[str] = field(default_factory=list)

    def validate(self) -> None:
        """Validate enumerations and numeric limits.

        Raises:
            ConfigError: when a value cannot be used by the pipeline.
        """
        if self.mode not in VALID_MODES:
            raise ConfigError(f"invalid mode {self.mode!r}; choose from: {', '.join(VALID_MODES)}")
        if self.output_format not in VALID_FORMATS:
            raise ConfigError(
                f"invalid format {self.output_format!r}; choose from: {', '.join(VALID_FORMATS)}"
            )
        if self.tokenizer not in VALID_TOKENIZERS:
            raise ConfigError(
                f"invalid tokenizer {self.tokenizer!r}; choose from: {', '.join(VALID_TOKENIZERS)}"
            )
        if self.max_file_size < 0:
            raise ConfigError("max_file_size must be non-negative")
        if self.max_total_size < 0:
            raise ConfigError("max_total_size must be non-negative")
        if not self.root.exists():
            raise ConfigError(f"project path does not exist: {self.root}")
        if not self.root.is_dir():
            raise ConfigError(f"project path is not a directory: {self.root}")
