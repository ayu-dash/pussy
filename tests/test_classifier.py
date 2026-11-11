"""File classification tests."""

from __future__ import annotations

import pytest

from pussy.core.classifier import classify_path
from pussy.models.file_entry import FileCategory


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("main.py", FileCategory.SOURCE_CODE),
        ("src/app.tsx", FileCategory.SOURCE_CODE),
        ("styles/app.css", FileCategory.SOURCE_CODE),
        ("composer.json", FileCategory.CONFIGURATION),
        ("README.md", FileCategory.DOCUMENTATION),
        ("docs/guide.md", FileCategory.DOCUMENTATION),
        ("LICENSE", FileCategory.DOCUMENTATION),
        ("schema.sql", FileCategory.DATABASE),
        ("migrations/2024_add_user.sql", FileCategory.DATABASE),
        ("test_user.py", FileCategory.TESTS),
        ("tests/conftest.py", FileCategory.TESTS),
        ("src/user.test.ts", FileCategory.TESTS),
        ("Dockerfile", FileCategory.INFRASTRUCTURE),
        ("docker-compose.yml", FileCategory.INFRASTRUCTURE),
        (".github/workflows/ci.yml", FileCategory.INFRASTRUCTURE),
        ("terraform/main.tf", FileCategory.INFRASTRUCTURE),
        ("logo.png", FileCategory.ASSETS),
        ("fonts/inter.woff2", FileCategory.ASSETS),
        ("app.pyc", FileCategory.GENERATED),
        ("app.min.js", FileCategory.GENERATED),
        ("package-lock.json", FileCategory.DEPENDENCIES),
        ("node_modules/pkg/index.js", FileCategory.DEPENDENCIES),
        ("vendor/lib/source.php", FileCategory.DEPENDENCIES),
        ("Cargo.lock", FileCategory.DEPENDENCIES),
        ("archive.xyz", FileCategory.UNKNOWN),
        ("binary.exe", FileCategory.BINARY),
        (".env.example", FileCategory.CONFIGURATION),
        ("Makefile", FileCategory.INFRASTRUCTURE),
        ("config/app.yaml", FileCategory.CONFIGURATION),
        ("src/App.vue", FileCategory.SOURCE_CODE),
        ("src/App.svelte", FileCategory.SOURCE_CODE),
        ("prisma/schema.prisma", FileCategory.DATABASE),
    ],
)
def test_classification_table(path: str, expected: FileCategory) -> None:
    assert classify_path(path) == expected


def test_test_directory_wins_over_extension() -> None:
    assert classify_path("tests/fixtures/data.json") == FileCategory.TESTS


def test_documentation_directory_marks_text_files() -> None:
    assert classify_path("docs/notes.txt") == FileCategory.DOCUMENTATION


def test_generated_beats_binary_for_bytecode() -> None:
    assert classify_path("module.pyc") == FileCategory.GENERATED


def test_configuration_wins_over_generic_documentation() -> None:
    assert classify_path("requirements.txt") == FileCategory.CONFIGURATION
