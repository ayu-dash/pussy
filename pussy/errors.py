"""Application-specific exceptions and exit codes."""

from __future__ import annotations

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_CONFLICT = 3


class PussyError(Exception):
    """Base class for expected, user-facing errors."""

    exit_code = EXIT_ERROR


class ConfigError(PussyError):
    """Invalid or unreadable configuration."""

    exit_code = EXIT_USAGE


class ProjectError(PussyError):
    """Invalid project path or unusable project."""

    exit_code = EXIT_USAGE


class ExportError(PussyError):
    """An output file could not be written safely."""


class ExportConflictError(ExportError):
    """Writing would overwrite an existing file without permission."""

    exit_code = EXIT_CONFLICT
