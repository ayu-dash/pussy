"""Independent sensitive-file detection.

This check deliberately does not depend on ignore rules.  It is applied to every
file the scanner sees, and the reader refuses to open sensitive entries even if a
caller force-includes them.
"""

from __future__ import annotations

from pathlib import PurePosixPath

from pussy.config.defaults import (
    SENSITIVE_ALLOWLIST,
    SENSITIVE_NAMES,
    SENSITIVE_SUFFIXES,
)

_SENSITIVE_BASENAMES = frozenset(SENSITIVE_NAMES)
_SENSITIVE_SUFFIXES_SET = frozenset(SENSITIVE_SUFFIXES)
_ALLOWLIST = frozenset(SENSITIVE_ALLOWLIST)

# Directory-scoped secret stores.  Any file below these paths is sensitive.
_SENSITIVE_DIRECTORIES = frozenset(
    {
        ".ssh",
        ".gnupg",
        ".aws",
        ".azure",
        ".config/gcloud",
    }
)

_EXTRA_SENSITIVE_PREFIXES = (
    ".env.",
    "credentials.",
    "secrets.",
    "private_key",
    "id_rsa",
    "id_ed25519",
)


def is_sensitive_path(relative_path: str) -> bool:
    """Return True when a project-relative path looks like a secret.

    The check is name-based and intentionally conservative: false positives
    only hide content, while false negatives would leak credentials.
    """
    path = PurePosixPath(relative_path)
    name = path.name
    lowered = name.lower()
    lowered_path = path.as_posix().lower()

    if lowered in _ALLOWLIST:
        return False

    if lowered in _SENSITIVE_BASENAMES:
        return True

    if any(lowered.endswith(suffix) for suffix in _SENSITIVE_SUFFIXES_SET):
        return True

    if any(lowered.startswith(prefix) for prefix in _EXTRA_SENSITIVE_PREFIXES):
        return True

    parts = lowered_path.split("/")
    for directory in _SENSITIVE_DIRECTORIES:
        directory_parts = directory.split("/")
        for index in range(len(parts) - len(directory_parts)):
            if parts[index : index + len(directory_parts)] == directory_parts:
                return True

    return False


def is_sensitive_file(path: str) -> bool:
    """Alias that makes call sites read naturally."""
    return is_sensitive_path(path)
