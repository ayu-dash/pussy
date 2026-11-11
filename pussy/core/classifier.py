"""Functional file classification.

Classification combines filename, extension, parent-directory semantics and a
small number of structural markers.  Content is not read here, so the scanner
stays cheap; the reader can refine a missing language later from a shebang.
"""

from __future__ import annotations

from pathlib import PurePosixPath

from pussy.filters.extensions import (
    ASSET_EXTENSIONS,
    BINARY_EXTENSIONS,
    CONFIGURATION_EXTENSIONS,
    CONFIGURATION_FILENAMES,
    DATABASE_EXTENSIONS,
    DEPENDENCY_DIRECTORY_NAMES,
    DOCUMENTATION_EXTENSIONS,
    GENERATED_EXTENSIONS,
    INFRASTRUCTURE_FILENAMES,
    LANGUAGE_BY_EXTENSION,
    TEST_DIRECTORY_NAMES,
    extension_of,
    language_for,
)
from pussy.models.file_entry import FileCategory, FileEntry

_DOCUMENTATION_NAMES = frozenset(
    {
        "readme",
        "changelog",
        "changes",
        "contributing",
        "license",
        "licence",
        "authors",
        "notice",
        "code_of_conduct",
        "security",
        "support",
        "faq",
        "architecture",
        "usage",
    }
)

_INFRASTRUCTURE_EXTENSIONS = frozenset({".tf", ".tfvars", ".hcl"})
_INFRASTRUCTURE_DIRECTORIES = frozenset(
    {"terraform", "k8s", "kubernetes", "helm", "deploy", "deployment", "ops", "infra"}
)
_DATABASE_DIRECTORIES = frozenset(
    {"migration", "migrations", "db", "database", "databases", "schema", "schemas", "seeders"}
)
_DOCUMENTATION_DIRECTORIES = frozenset({"docs", "doc", "documentation", "wiki"})
_GENERATED_MARKERS = (
    ".min.js",
    ".min.css",
    ".bundle.js",
    ".generated.",
    ".designer.cs",
    ".g.dart",
    ".freezed.dart",
    "_pb2.py",
    "_pb2_grpc.py",
    ".pb.go",
    ".snap",
)


def _is_test_filename(name: str) -> bool:
    lowered = name.lower()
    stem = PurePosixPath(lowered).stem
    test_prefix = lowered.startswith(("test_", "test-"))
    test_suffix = stem.endswith(("_test", "-test", "_tests", ".test", ".spec", "tests"))
    return test_prefix or test_suffix or lowered == "conftest.py"


def _has_segment(parts: list[str], names: frozenset[str]) -> bool:
    return any(part.lower() in names for part in parts)


def classify_path(relative_path: str) -> FileCategory:
    """Classify a project-relative path without reading the file."""
    path = PurePosixPath(relative_path)
    name = path.name
    lowered = name.lower()
    suffix = extension_of(name)
    parts = list(path.parts[:-1])

    if lowered in {
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "cargo.lock",
        "poetry.lock",
        "uv.lock",
        "composer.lock",
        "gemfile.lock",
        "pipfile.lock",
    }:
        return FileCategory.DEPENDENCIES

    if (
        suffix in GENERATED_EXTENSIONS
        or any(marker in lowered for marker in _GENERATED_MARKERS)
        or lowered.endswith(".lock")
    ):
        return FileCategory.GENERATED

    if _has_segment(parts, DEPENDENCY_DIRECTORY_NAMES):
        return FileCategory.DEPENDENCIES

    if _has_segment(parts, TEST_DIRECTORY_NAMES) or _is_test_filename(name):
        return FileCategory.TESTS

    if (
        lowered in INFRASTRUCTURE_FILENAMES
        or lowered.startswith(("dockerfile.", "docker-compose", "compose."))
        or suffix in _INFRASTRUCTURE_EXTENSIONS
        or _has_segment(parts, _INFRASTRUCTURE_DIRECTORIES)
        or (".github" in parts and "workflows" in parts)
        or lowered in {".gitlab-ci.yml", ".travis.yml", "azure-pipelines.yml"}
    ):
        return FileCategory.INFRASTRUCTURE

    if (
        suffix in DATABASE_EXTENSIONS
        or _has_segment(parts, _DATABASE_DIRECTORIES)
        or lowered == "schema.prisma"
    ):
        return FileCategory.DATABASE

    if (
        lowered in CONFIGURATION_FILENAMES
        or lowered.startswith(".env")
        or (lowered.startswith("requirements") and lowered.endswith(".txt"))
        or suffix in CONFIGURATION_EXTENSIONS
        or lowered.endswith((".config.js", ".config.ts", ".config.mjs", ".config.cjs"))
        or lowered in {".gitignore", ".gitattributes", ".dockerignore", ".editorconfig"}
    ):
        return FileCategory.CONFIGURATION

    if (
        PurePosixPath(lowered).stem in _DOCUMENTATION_NAMES
        or suffix in DOCUMENTATION_EXTENSIONS
        or _has_segment(parts, _DOCUMENTATION_DIRECTORIES)
    ):
        return FileCategory.DOCUMENTATION

    if suffix in ASSET_EXTENSIONS:
        return FileCategory.ASSETS

    if suffix in BINARY_EXTENSIONS:
        return FileCategory.BINARY

    if suffix in LANGUAGE_BY_EXTENSION:
        return FileCategory.SOURCE_CODE

    return FileCategory.UNKNOWN


def classify_entry(entry: FileEntry) -> FileEntry:
    """Assign category and language to an entry in place."""
    if entry.is_sensitive:
        entry.category = FileCategory.SENSITIVE
        entry.language = language_for(entry.name)
        return entry
    entry.category = classify_path(entry.relative_path)
    entry.language = language_for(entry.name)
    return entry


def classify_entries(entries: list[FileEntry]) -> None:
    """Classify a list of entries in place."""
    for entry in entries:
        classify_entry(entry)
