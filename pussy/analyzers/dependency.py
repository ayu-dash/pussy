"""Dependency manifest parsers.

Only files are read; no package manager is executed and nothing is installed.
Parse failures are reported as warnings instead of aborting analysis.
"""

from __future__ import annotations

import json
import re
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

from pussy.models.file_entry import FileEntry
from pussy.models.project import Dependency, DependencyReport
from pussy.utils.encoding import decode_bytes

_REQUIREMENT_RE = re.compile(
    r"^(?P<name>[A-Za-z0-9][A-Za-z0-9_.-]*)"
    r"(?:\[[^\]]*\])?"
    r"\s*(?P<spec>.*)$"
)
_GRADLE_RE = re.compile(
    r"\b(implementation|api|compileOnly|runtimeOnly|testImplementation|"
    r"testRuntimeOnly|kapt|annotationProcessor|classpath)\s*[(\s]\s*"
    r"['\"]([^'\"]+)['\"]"
)
_GEM_RE = re.compile(r"^\s*gem\s+['\"]([^'\"]+)['\"](?:\s*,\s*['\"]([^'\"]+)['\"])?")
_PLATFORM_PACKAGES = frozenset({"php", "python", "composer-plugin-api"})


def _read(path: Path) -> str:
    try:
        data = path.read_bytes()
    except OSError:
        return ""
    text, _encoding = decode_bytes(data)
    return text


def _clean_spec(spec: str) -> str:
    value = spec.strip()
    if value.startswith(";"):
        return ""
    if value.startswith("@"):  # direct URL reference
        return value
    return value


def _parse_requirement(line: str) -> Dependency | None:
    stripped = line.strip()
    if not stripped or stripped.startswith(("#", "-", "git+", "http://", "https://")):
        return None
    if " #" in stripped:
        stripped = stripped.split(" #", 1)[0].strip()
    match = _REQUIREMENT_RE.match(stripped)
    if not match:
        return None
    name = match.group("name").strip()
    spec = _clean_spec(match.group("spec"))
    if ";" in spec:
        spec = spec.split(";", 1)[0].strip()
    return Dependency(name=name, version=spec)


def _requirement_scope(filename: str) -> str:
    lowered = filename.lower()
    if "dev" in lowered or "test" in lowered:
        return "development"
    return "production"


def _parse_requirements(path: Path, relative: str) -> list[Dependency]:
    dependencies: list[Dependency] = []
    scope = _requirement_scope(path.name)
    for line in _read(path).splitlines():
        dependency = _parse_requirement(line)
        if dependency:
            dependencies.append(Dependency(dependency.name, dependency.version, scope, relative))
    return dependencies


def _version_of(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        version = value.get("version", "")
        return str(version).strip() if version else ""
    return ""


def _parse_pyproject(path: Path, relative: str) -> list[Dependency]:
    try:
        data = tomllib.loads(_read(path))
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"invalid TOML: {exc}") from exc
    dependencies: list[Dependency] = []

    project = data.get("project", {})
    if isinstance(project, dict):
        for raw in project.get("dependencies", []) or []:
            if isinstance(raw, str):
                dependency = _parse_requirement(raw)
                if dependency:
                    dependencies.append(
                        Dependency(dependency.name, dependency.version, "production", relative)
                    )
        optional = project.get("optional-dependencies", {}) or {}
        if isinstance(optional, dict):
            for group, values in optional.items():
                for raw in values or []:
                    if isinstance(raw, str):
                        dependency = _parse_requirement(raw)
                        if dependency:
                            dependencies.append(
                                Dependency(
                                    dependency.name,
                                    dependency.version,
                                    f"optional:{group}",
                                    relative,
                                )
                            )

    groups = data.get("dependency-groups", {})
    if isinstance(groups, dict):
        for group, values in groups.items():
            for raw in values or []:
                if isinstance(raw, str):
                    dependency = _parse_requirement(raw)
                    if dependency:
                        dependencies.append(
                            Dependency(
                                dependency.name,
                                dependency.version,
                                "development" if group in {"dev", "test"} else f"optional:{group}",
                                relative,
                            )
                        )

    poetry = data.get("tool", {}).get("poetry", {})
    if isinstance(poetry, dict):
        for name, value in (poetry.get("dependencies") or {}).items():
            if str(name).lower() == "python":
                continue
            dependencies.append(Dependency(str(name), _version_of(value), "production", relative))
        for name, value in (poetry.get("dev-dependencies") or {}).items():
            dependencies.append(Dependency(str(name), _version_of(value), "development", relative))
        poetry_groups = poetry.get("group", {}) or {}
        if isinstance(poetry_groups, dict):
            for group, table in poetry_groups.items():
                if not isinstance(table, dict):
                    continue
                scope = "development" if group in {"dev", "test"} else f"optional:{group}"
                for name, value in (table.get("dependencies") or {}).items():
                    dependencies.append(Dependency(str(name), _version_of(value), scope, relative))
    return dependencies


def _parse_pipfile(path: Path, relative: str) -> list[Dependency]:
    try:
        data = tomllib.loads(_read(path))
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"invalid TOML: {exc}") from exc
    dependencies: list[Dependency] = []
    for section, scope in (("packages", "production"), ("dev-packages", "development")):
        table = data.get(section, {}) or {}
        if isinstance(table, dict):
            for name, value in table.items():
                dependencies.append(Dependency(str(name), _version_of(value), scope, relative))
    return dependencies


def _parse_package_json(path: Path, relative: str) -> list[Dependency]:
    try:
        data = json.loads(_read(path))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("top-level JSON value must be an object")
    sections = (
        ("dependencies", "production"),
        ("devDependencies", "development"),
        ("peerDependencies", "optional:peer"),
        ("optionalDependencies", "optional"),
    )
    dependencies: list[Dependency] = []
    for section, scope in sections:
        table = data.get(section, {}) or {}
        if isinstance(table, dict):
            for name, version in table.items():
                dependencies.append(Dependency(str(name), str(version), scope, relative))
    return dependencies


def _parse_composer(path: Path, relative: str) -> list[Dependency]:
    try:
        data = json.loads(_read(path))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("top-level JSON value must be an object")
    dependencies: list[Dependency] = []
    for section, scope in (("require", "production"), ("require-dev", "development")):
        table = data.get(section, {}) or {}
        if not isinstance(table, dict):
            continue
        for name, version in table.items():
            lowered = str(name).lower()
            if lowered in _PLATFORM_PACKAGES or lowered.startswith(("ext-", "lib-")):
                continue
            dependencies.append(Dependency(str(name), str(version), scope, relative))
    return dependencies


def _parse_cargo(path: Path, relative: str) -> list[Dependency]:
    try:
        data = tomllib.loads(_read(path))
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"invalid TOML: {exc}") from exc
    dependencies: list[Dependency] = []
    sections = (
        ("dependencies", "production"),
        ("dev-dependencies", "development"),
        ("build-dependencies", "build"),
    )
    for section, scope in sections:
        table = data.get(section, {}) or {}
        if isinstance(table, dict):
            for name, value in table.items():
                dependencies.append(Dependency(str(name), _version_of(value), scope, relative))
    workspace = data.get("workspace", {}) or {}
    if isinstance(workspace, dict) and isinstance(workspace.get("dependencies"), dict):
        for name, value in workspace["dependencies"].items():
            dependencies.append(Dependency(str(name), _version_of(value), "production", relative))
    return dependencies


def _parse_go_mod(path: Path, relative: str) -> list[Dependency]:
    dependencies: list[Dependency] = []
    in_block = False
    for raw in _read(path).splitlines():
        line = raw.split("//", 1)[0].strip()
        if not line:
            continue
        if line.startswith("require ("):
            in_block = True
            continue
        if in_block and line == ")":
            in_block = False
            continue
        if line.startswith("require "):
            line = line[len("require ") :].strip()
        elif not in_block:
            continue
        fields = line.split()
        if len(fields) >= 2:
            dependencies.append(Dependency(fields[0], fields[1], "production", relative))
    return dependencies


def _xml_text(element: ET.Element, tag: str) -> str:
    for child in element:
        if child.tag.rsplit("}", 1)[-1] == tag:
            return (child.text or "").strip()
    return ""


def _parse_pom(path: Path, relative: str) -> list[Dependency]:
    try:
        root = ET.fromstring(_read(path))
    except ET.ParseError as exc:
        raise ValueError(f"invalid XML: {exc}") from exc
    dependencies: list[Dependency] = []
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] != "dependency":
            continue
        group = _xml_text(element, "groupId")
        artifact = _xml_text(element, "artifactId")
        version = _xml_text(element, "version")
        scope = _xml_text(element, "scope")
        if not artifact:
            continue
        name = f"{group}:{artifact}" if group else artifact
        dependencies.append(
            Dependency(name, version, "development" if scope == "test" else "production", relative)
        )
    return dependencies


def _parse_gradle(path: Path, relative: str) -> list[Dependency]:
    dependencies: list[Dependency] = []
    for match in _GRADLE_RE.finditer(_read(path)):
        configuration, coordinate = match.groups()
        parts = coordinate.split(":")
        if len(parts) < 2:
            continue
        name = f"{parts[0]}:{parts[1]}"
        version = parts[2] if len(parts) > 2 else ""
        scope = "development" if configuration.startswith("test") else "production"
        dependencies.append(Dependency(name, version, scope, relative))
    return dependencies


def _parse_pubspec(path: Path, relative: str) -> list[Dependency]:
    dependencies: list[Dependency] = []
    section: str | None = None
    for raw in _read(path).splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if not raw.startswith((" ", "\t")):
            key = raw.split(":", 1)[0].strip()
            section = key if key in {"dependencies", "dev_dependencies"} else None
            continue
        if section is None:
            continue
        indent = len(raw) - len(raw.lstrip())
        if indent != 2:
            continue
        if ":" not in raw:
            continue
        name, value = raw.strip().split(":", 1)
        if name in {"sdk", "flutter"}:
            continue
        scope = "development" if section == "dev_dependencies" else "production"
        version = value.strip().strip("'\"")
        if version in {">", ""}:
            version = ""
        dependencies.append(Dependency(name.strip(), version, scope, relative))
    return dependencies


def _parse_gemfile(path: Path, relative: str) -> list[Dependency]:
    dependencies: list[Dependency] = []
    group_depth = 0
    development = False
    for raw in _read(path).splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("group ") and line.endswith(" do"):
            group_depth += 1
            development = any(keyword in line for keyword in ("development", "test"))
            continue
        if line == "end" and group_depth:
            group_depth -= 1
            if group_depth == 0:
                development = False
            continue
        match = _GEM_RE.match(raw)
        if match:
            name, version = match.groups()
            dependencies.append(
                Dependency(
                    name,
                    version or "",
                    "development" if development else "production",
                    relative,
                )
            )
    return dependencies


_PARSERS = {
    "pyproject.toml": _parse_pyproject,
    "Pipfile": _parse_pipfile,
    "package.json": _parse_package_json,
    "composer.json": _parse_composer,
    "Cargo.toml": _parse_cargo,
    "go.mod": _parse_go_mod,
    "pom.xml": _parse_pom,
    "pubspec.yaml": _parse_pubspec,
    "Gemfile": _parse_gemfile,
}


class DependencyAnalyzer:
    """Discover and parse dependency manifests found in the project."""

    def analyze(self, root: Path, entries: list[FileEntry]) -> DependencyReport:
        """Parse all recognized manifests, deduplicating identical entries."""
        report = DependencyReport()
        seen: set[tuple[str, str, str]] = set()

        for entry in sorted(entries, key=lambda item: item.relative_path):
            parser = _PARSERS.get(entry.name)
            if (
                parser is None
                and entry.name.lower().startswith("requirements")
                and entry.name.endswith(".txt")
            ):
                parser = _parse_requirements
            if parser is None and entry.name in {"build.gradle", "build.gradle.kts"}:
                parser = _parse_gradle
            if parser is None:
                continue
            try:
                dependencies = parser(entry.path, entry.relative_path)
            except (ValueError, OSError) as exc:
                report.warnings.append(f"cannot parse {entry.relative_path}: {exc}")
                continue
            report.files_analyzed.append(entry.relative_path)
            for dependency in dependencies:
                key = (dependency.name.lower(), dependency.scope, dependency.source)
                if key in seen:
                    continue
                seen.add(key)
                report.dependencies.append(dependency)

        return report
