"""Dependency manifest parser tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pussy.analyzers.dependency import DependencyAnalyzer
from pussy.core.scanner import Scanner
from pussy.filters.ignore import IgnoreManager


def analyze(root: Path):
    scan = Scanner(root, IgnoreManager([])).scan()
    return DependencyAnalyzer().analyze(root, scan.files)


def by_name(report) -> dict[str, list]:
    result: dict[str, list] = {}
    for dependency in report.dependencies:
        result.setdefault(dependency.name.lower(), []).append(dependency)
    return result


def test_requirements_txt(tmp_path: Path, write_file) -> None:
    write_file(
        tmp_path,
        "requirements.txt",
        "# comment\nrequests>=2.31\nflask[async]==3.0.0 ; python_version >= '3.9'\n"
        "-r other.txt\nhttps://example.com/pkg.whl\n",
    )
    report = analyze(tmp_path)
    names = by_name(report)
    assert names["requests"][0].version == ">=2.31"
    assert names["flask"][0].version == "==3.0.0"
    assert names["flask"][0].scope == "production"
    assert report.files_analyzed == ["requirements.txt"]


def test_requirements_dev_scope(tmp_path: Path, write_file) -> None:
    write_file(tmp_path, "requirements-dev.txt", "pytest==8.0.0\n")
    report = analyze(tmp_path)
    assert report.dependencies[0].scope == "development"


def test_pyproject_pep621(tmp_path: Path, write_file) -> None:
    write_file(
        tmp_path,
        "pyproject.toml",
        """
[project]
dependencies = ["httpx>=0.27", "pydantic[email]==2.6"]

[project.optional-dependencies]
cli = ["typer>=0.12"]

[dependency-groups]
dev = ["pytest>=8"]
""",
    )
    report = analyze(tmp_path)
    scopes = {(dependency.name, dependency.scope) for dependency in report.dependencies}
    assert ("httpx", "production") in scopes
    assert ("pydantic", "production") in scopes
    assert ("typer", "optional:cli") in scopes
    assert ("pytest", "development") in scopes


def test_pyproject_poetry(tmp_path: Path, write_file) -> None:
    write_file(
        tmp_path,
        "pyproject.toml",
        """
[tool.poetry]
name = "demo"

[tool.poetry.dependencies]
python = "^3.11"
requests = "^2.31"

[tool.poetry.group.dev.dependencies]
pytest = "^8.0"
""",
    )
    report = analyze(tmp_path)
    dependencies = {dependency.name: dependency for dependency in report.dependencies}
    assert "python" not in dependencies
    assert dependencies["requests"].version == "^2.31"
    assert dependencies["requests"].scope == "production"
    assert dependencies["pytest"].scope == "development"


def test_pipfile(tmp_path: Path, write_file) -> None:
    write_file(
        tmp_path,
        "Pipfile",
        '[packages]\nrequests = "*"\n[dev-packages]\npytest = "==8.0.0"\n',
    )
    report = analyze(tmp_path)
    dependencies = {dependency.name: dependency for dependency in report.dependencies}
    assert dependencies["requests"].scope == "production"
    assert dependencies["pytest"].scope == "development"
    assert dependencies["pytest"].version == "==8.0.0"


def test_package_json_scopes(tmp_path: Path, write_file) -> None:
    write_file(
        tmp_path,
        "package.json",
        json.dumps(
            {
                "dependencies": {"react": "^18.0.0"},
                "devDependencies": {"typescript": "^5.0.0"},
                "peerDependencies": {"react-dom": "^18.0.0"},
                "optionalDependencies": {"fsevents": "^2.3.0"},
            }
        ),
    )
    report = analyze(tmp_path)
    scopes = {dependency.name: dependency.scope for dependency in report.dependencies}
    assert scopes["react"] == "production"
    assert scopes["typescript"] == "development"
    assert scopes["react-dom"] == "optional:peer"
    assert scopes["fsevents"] == "optional"


def test_composer_skips_platform_packages(tmp_path: Path, write_file) -> None:
    write_file(
        tmp_path,
        "composer.json",
        json.dumps(
            {
                "require": {"php": "^8.2", "ext-json": "*", "laravel/framework": "^11.0"},
                "require-dev": {"phpunit/phpunit": "^11.0"},
            }
        ),
    )
    report = analyze(tmp_path)
    names = {dependency.name: dependency.scope for dependency in report.dependencies}
    assert "php" not in names
    assert "ext-json" not in names
    assert names["laravel/framework"] == "production"
    assert names["phpunit/phpunit"] == "development"


def test_cargo_dependencies(tmp_path: Path, write_file) -> None:
    write_file(
        tmp_path,
        "Cargo.toml",
        """
[package]
name = "demo"

[dependencies]
serde = { version = "1.0", features = ["derive"] }
tokio = "1.38"

[dev-dependencies]
tempfile = "3"
""",
    )
    report = analyze(tmp_path)
    dependencies = {dependency.name: dependency for dependency in report.dependencies}
    assert dependencies["serde"].version == "1.0"
    assert dependencies["tokio"].version == "1.38"
    assert dependencies["tempfile"].scope == "development"


def test_go_mod_block(tmp_path: Path, write_file) -> None:
    write_file(
        tmp_path,
        "go.mod",
        "module example.com/app\n\nrequire (\n"
        "\tgithub.com/gin-gonic/gin v1.10.0\n"
        "\tgolang.org/x/text v0.14.0 // indirect\n"
        ")\n\nrequire github.com/stretchr/testify v1.9.0\n",
    )
    report = analyze(tmp_path)
    dependencies = {dependency.name: dependency for dependency in report.dependencies}
    assert dependencies["github.com/gin-gonic/gin"].version == "v1.10.0"
    assert dependencies["golang.org/x/text"].version == "v0.14.0"
    assert dependencies["github.com/stretchr/testify"].version == "v1.9.0"


def test_pom_xml(tmp_path: Path, write_file) -> None:
    write_file(
        tmp_path,
        "pom.xml",
        """<project xmlns="http://maven.apache.org/POM/4.0.0">
  <properties><spring.version>6.0.0</spring.version></properties>
  <dependencies>
    <dependency><groupId>org.springframework</groupId>
      <artifactId>spring-core</artifactId><version>6.0.0</version></dependency>
    <dependency><groupId>org.junit.jupiter</groupId>
      <artifactId>junit-jupiter</artifactId><version>5.10.0</version>
      <scope>test</scope></dependency>
  </dependencies>
</project>""",
    )
    report = analyze(tmp_path)
    dependencies = {dependency.name: dependency for dependency in report.dependencies}
    assert dependencies["org.springframework:spring-core"].version == "6.0.0"
    assert dependencies["org.junit.jupiter:junit-jupiter"].scope == "development"


def test_gradle(tmp_path: Path, write_file) -> None:
    write_file(
        tmp_path,
        "build.gradle",
        """
dependencies {
    implementation 'com.squareup.retrofit2:retrofit:2.9.0'
    testImplementation "junit:junit:4.13.2"
}
""",
    )
    report = analyze(tmp_path)
    dependencies = {dependency.name: dependency for dependency in report.dependencies}
    assert dependencies["com.squareup.retrofit2:retrofit"].version == "2.9.0"
    assert dependencies["junit:junit"].scope == "development"


def test_pubspec(tmp_path: Path, write_file) -> None:
    write_file(
        tmp_path,
        "pubspec.yaml",
        """
name: app
environment:
  sdk: '>=3.0.0 <4.0.0'
dependencies:
  http: ^1.2.0
  flutter:
    sdk: flutter
dev_dependencies:
  flutter_test:
    sdk: flutter
""",
    )
    report = analyze(tmp_path)
    dependencies = {dependency.name: dependency for dependency in report.dependencies}
    assert dependencies["http"].version == "^1.2.0"
    assert dependencies["http"].scope == "production"
    assert dependencies["flutter_test"].scope == "development"
    assert "sdk" not in dependencies


def test_gemfile_group(tmp_path: Path, write_file) -> None:
    write_file(
        tmp_path,
        "Gemfile",
        """
source 'https://rubygems.org'
gem 'rails', '~> 7.1'
group :development, :test do
  gem 'rspec', '~> 3.13'
end
""",
    )
    report = analyze(tmp_path)
    dependencies = {dependency.name: dependency for dependency in report.dependencies}
    assert dependencies["rails"].scope == "production"
    assert dependencies["rspec"].scope == "development"


def test_invalid_manifest_is_a_warning(tmp_path: Path, write_file) -> None:
    write_file(tmp_path, "package.json", "{ invalid json")
    report = analyze(tmp_path)
    assert report.dependencies == []
    assert any("cannot parse package.json" in warning for warning in report.warnings)


def test_invalid_pyproject_is_a_warning(tmp_path: Path, write_file) -> None:
    write_file(tmp_path, "pyproject.toml", "[project\n")
    report = analyze(tmp_path)
    assert any("cannot parse pyproject.toml" in warning for warning in report.warnings)


def test_deduplicates_identical_dependencies(tmp_path: Path, write_file) -> None:
    write_file(tmp_path, "package.json", json.dumps({"dependencies": {"react": "^18.0.0"}}))
    report = analyze(tmp_path)
    react = [dependency for dependency in report.dependencies if dependency.name == "react"]
    assert len(react) == 1


@pytest.mark.parametrize("filename", ["requirements-test.txt", "requirements_dev.txt"])
def test_requirements_naming_variants(tmp_path: Path, write_file, filename: str) -> None:
    write_file(tmp_path, filename, "pytest\n")
    report = analyze(tmp_path)
    assert report.dependencies[0].scope == "development"
