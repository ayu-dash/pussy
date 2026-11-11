"""Project detector tests across languages and frameworks."""

from __future__ import annotations

import json
from pathlib import Path

from pussy.core.detector import ProjectDetector, TechnologyRule
from pussy.core.scanner import Scanner
from pussy.filters.ignore import IgnoreManager
from pussy.models.file_entry import FileEntry


def detect_with(root: Path) -> object:
    scan = Scanner(root, IgnoreManager([])).scan()
    return ProjectDetector().detect(root, scan.files)


def test_laravel_detection(tmp_path: Path, write_file) -> None:
    write_file(tmp_path, "artisan", "#!/usr/bin/env php\n<?php\n")
    write_file(
        tmp_path,
        "composer.json",
        json.dumps({"require": {"laravel/framework": "^11.0", "php": "^8.2"}}),
    )
    write_file(tmp_path, "app/Models/User.php", "<?php class User {}")
    result = detect_with(tmp_path)
    assert "Laravel" in result.frameworks
    assert "Composer" in result.package_managers
    assert "PHP" in [name for name, _count in result.languages]


def test_django_detection(tmp_path: Path, write_file) -> None:
    write_file(
        tmp_path,
        "manage.py",
        "import django\nfrom django.core.management import execute_from_command_line\n",
    )
    write_file(tmp_path, "requirements.txt", "Django==5.0\n")
    result = detect_with(tmp_path)
    assert "Django" in result.frameworks
    assert "pip" in result.package_managers
    assert "manage.py" in result.entry_points


def test_nextjs_and_react_detection(tmp_path: Path, write_file) -> None:
    write_file(
        tmp_path,
        "package.json",
        json.dumps({"dependencies": {"next": "^14.0.0", "react": "^18.0.0"}}),
    )
    write_file(tmp_path, "next.config.js", "module.exports = {}\n")
    write_file(tmp_path, "src/app/page.tsx", "export default function Page() { return null }\n")
    result = detect_with(tmp_path)
    assert "Next.js" in result.frameworks
    assert "React" in result.frameworks
    assert "npm" in result.package_managers


def test_react_project_without_next(tmp_path: Path, write_file) -> None:
    write_file(
        tmp_path,
        "package.json",
        json.dumps({"dependencies": {"react": "^18.0.0", "react-dom": "^18.0.0"}}),
    )
    result = detect_with(tmp_path)
    assert "React" in result.frameworks
    assert "Next.js" not in result.frameworks


def test_react_native_is_not_plain_react(tmp_path: Path, write_file) -> None:
    write_file(
        tmp_path,
        "package.json",
        json.dumps({"dependencies": {"react": "^18.0.0", "react-native": "^0.74.0"}}),
    )
    result = detect_with(tmp_path)
    assert "React Native" in result.frameworks
    assert "React" not in result.frameworks


def test_generic_python_project(tmp_path: Path, write_file) -> None:
    write_file(tmp_path, "main.py", "print('hello')\n")
    result = detect_with(tmp_path)
    assert [name for name, _count in result.languages] == ["Python"]
    assert result.frameworks == []
    assert result.package_managers == []
    assert result.entry_points == ["main.py"]


def test_generic_php_project(tmp_path: Path, write_file) -> None:
    write_file(tmp_path, "index.php", "<?php echo 'hi';")
    result = detect_with(tmp_path)
    assert [name for name, _count in result.languages] == ["PHP"]
    assert "Laravel" not in result.frameworks


def test_project_without_manifest(tmp_path: Path) -> None:
    result = detect_with(tmp_path)
    assert result.languages == []
    assert result.frameworks == []
    assert result.package_managers == []


def test_multi_language_project(tmp_path: Path, write_file) -> None:
    for name in ("a.py", "b.js", "c.php", "d.go", "e.rs"):
        write_file(tmp_path, name, "content\n")
    result = detect_with(tmp_path)
    languages = {name for name, _count in result.languages}
    assert {"Python", "JavaScript", "PHP", "Go", "Rust"} <= languages


def test_package_manager_markers(tmp_path: Path, write_file) -> None:
    write_file(tmp_path, "pyproject.toml", "[tool.poetry]\nname = 'x'\n")
    write_file(tmp_path, "poetry.lock", "")
    write_file(tmp_path, "uv.lock", "")
    result = detect_with(tmp_path)
    assert "Poetry" in result.package_managers
    assert "uv" in result.package_managers


def test_yarn_lock_suppresses_npm(tmp_path: Path, write_file) -> None:
    write_file(tmp_path, "package.json", json.dumps({"dependencies": {}}))
    write_file(tmp_path, "yarn.lock", "")
    result = detect_with(tmp_path)
    assert "yarn" in result.package_managers
    assert "npm" not in result.package_managers


def test_pnpm_lock_is_detected(tmp_path: Path, write_file) -> None:
    write_file(tmp_path, "package.json", json.dumps({"dependencies": {}}))
    write_file(tmp_path, "pnpm-lock.yaml", "")
    result = detect_with(tmp_path)
    assert "pnpm" in result.package_managers
    assert "npm" not in result.package_managers


def test_compiled_ecosystem_managers(tmp_path: Path, write_file) -> None:
    write_file(tmp_path, "Cargo.toml", "[package]\nname='x'\n")
    write_file(tmp_path, "pom.xml", "<project></project>")
    write_file(tmp_path, "build.gradle", "plugins {}\n")
    write_file(tmp_path, "Gemfile", "source 'https://rubygems.org'\n")
    write_file(tmp_path, "go.mod", "module example.com/x\n")
    write_file(tmp_path, "pubspec.yaml", "name: app\n")
    result = detect_with(tmp_path)
    for manager in ("Cargo", "Maven", "Gradle", "Bundler", "Go modules", "pub"):
        assert manager in result.package_managers


def test_flutter_detection(tmp_path: Path, write_file) -> None:
    write_file(
        tmp_path,
        "pubspec.yaml",
        "name: app\nenvironment:\n  sdk: '>=3.0.0 <4.0.0'\n"
        "dependencies:\n  flutter:\n    sdk: flutter\n",
    )
    write_file(tmp_path, "lib/main.dart", "void main() {}\n")
    result = detect_with(tmp_path)
    assert "Flutter" in result.frameworks
    assert "Dart" in [name for name, _count in result.languages]


def test_spring_boot_detection(tmp_path: Path, write_file) -> None:
    write_file(
        tmp_path,
        "pom.xml",
        "<project><dependencies><dependency><groupId>org.springframework.boot</groupId>"
        "<artifactId>spring-boot-starter-web</artifactId></dependency></dependencies></project>",
    )
    write_file(tmp_path, "src/main/java/App.java", "public class App {}")
    result = detect_with(tmp_path)
    assert "Spring Boot" in result.frameworks
    assert "Maven" in result.package_managers


def test_entry_points_multiple(tmp_path: Path, write_file) -> None:
    write_file(tmp_path, "src/main.ts", "console.log('x')\n")
    write_file(tmp_path, "manage.py", "import django\n")
    result = detect_with(tmp_path)
    assert "src/main.ts" in result.entry_points
    assert "manage.py" in result.entry_points


def test_custom_technology_rule(tmp_path: Path, write_file) -> None:
    write_file(tmp_path, "custom.marker", "present\n")
    scan = Scanner(tmp_path, IgnoreManager([])).scan()
    detector = ProjectDetector()
    detector.register(
        TechnologyRule(
            "Custom Platform",
            "framework",
            lambda context: "custom.marker" if context.exists("custom.marker") else None,
        )
    )
    result = detector.detect(tmp_path, scan.files)
    assert "Custom Platform" in result.frameworks


def test_detection_is_stable_for_unknown_entries(tmp_path: Path) -> None:
    detector = ProjectDetector()
    result = detector.detect(tmp_path, [FileEntry(tmp_path / "x.xyz", "x.xyz")])
    assert result.languages == []
