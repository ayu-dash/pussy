"""Extensible technology detection.

Detection combines file markers with manifest content validation.  New
technologies can be added through :meth:`ProjectDetector.register` without
modifying the engine.
"""

from __future__ import annotations

import fnmatch
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

from pussy.core.classifier import classify_entry
from pussy.filters.extensions import language_for
from pussy.models.file_entry import FileCategory, FileEntry
from pussy.models.project import Technology
from pussy.utils.encoding import decode_bytes

_MANIFEST_READ_LIMIT = 2 * 1024 * 1024
_LANGUAGE_CATEGORIES = frozenset(
    {
        FileCategory.SOURCE_CODE,
        FileCategory.TESTS,
        FileCategory.DATABASE,
        FileCategory.INFRASTRUCTURE,
    }
)


def _safe_read(path: Path) -> str:
    try:
        with path.open("rb") as handle:
            data = handle.read(_MANIFEST_READ_LIMIT)
    except OSError:
        return ""
    text, _encoding = decode_bytes(data)
    return text


@dataclass(slots=True)
class DetectionContext:
    """Read-only view of the project used by detection rules."""

    root: Path
    entries: list[FileEntry]
    paths: set[str] = field(default_factory=set)
    root_names: set[str] = field(default_factory=set)
    _cache: dict[str, str] = field(default_factory=dict, repr=False)

    @classmethod
    def build(cls, root: Path, entries: list[FileEntry]) -> DetectionContext:
        context = cls(root=root, entries=entries)
        context.paths = {entry.relative_path for entry in entries}
        try:
            context.root_names = {child.name for child in root.iterdir()}
        except OSError:
            context.root_names = {
                entry.relative_path for entry in entries if "/" not in entry.relative_path
            }
        return context

    def exists(self, name: str) -> bool:
        """Whether a root-level file/directory exists."""
        return name in self.root_names or name in self.paths

    def matches(self, pattern: str) -> bool:
        """Whether any root-level name matches a glob."""
        return any(fnmatch.fnmatchcase(name, pattern) for name in self.root_names)

    def any_path_suffix(self, suffix: str) -> bool:
        """Whether any project path ends with a suffix."""
        return any(path.endswith(suffix) for path in self.paths)

    def read(self, name: str) -> str:
        """Read a root-level manifest, caching and size-capping it."""
        if name not in self._cache:
            path = self.root / name
            self._cache[name] = _safe_read(path) if path.is_file() else ""
        return self._cache[name]

    def read_first(self, names: Iterable[str]) -> str:
        """Return the first non-empty manifest among *names*."""
        for name in names:
            content = self.read(name)
            if content:
                return content
        return ""

    def python_manifests(self) -> str:
        """Concatenated Python dependency manifests."""
        return "\n".join(
            filter(
                None,
                (
                    self.read("pyproject.toml"),
                    self.read("requirements.txt"),
                    self.read("Pipfile"),
                ),
            )
        ).lower()

    def node_manifests(self) -> str:
        """Concatenated JavaScript manifests."""
        return self.read("package.json").lower()


DetectorFn = Callable[[DetectionContext], str | None]


@dataclass(frozen=True, slots=True)
class TechnologyRule:
    """One framework/package-manager detection rule."""

    name: str
    kind: str
    detector: DetectorFn


def _contains(haystack: str, *needles: str) -> bool:
    return any(needle in haystack for needle in needles)


def _laravel(ctx: DetectionContext) -> str | None:
    composer = ctx.read("composer.json").lower()
    if ctx.exists("artisan") and _contains(composer, "laravel/framework"):
        return "artisan + composer.json (laravel/framework)"
    return None


def _symfony(ctx: DetectionContext) -> str | None:
    composer = ctx.read("composer.json").lower()
    if _contains(composer, "symfony/framework-bundle", "symfony/symfony"):
        return "composer.json (symfony framework)"
    return None


def _django(ctx: DetectionContext) -> str | None:
    manifests = ctx.python_manifests()
    if _contains(manifests, "django"):
        return "Python manifest (django)"
    if ctx.exists("manage.py") and _contains(ctx.read("manage.py").lower(), "django"):
        return "manage.py (django)"
    return None


def _flask(ctx: DetectionContext) -> str | None:
    if _contains(ctx.python_manifests(), "flask"):
        return "Python manifest (flask)"
    return None


def _fastapi(ctx: DetectionContext) -> str | None:
    if _contains(ctx.python_manifests(), "fastapi"):
        return "Python manifest (fastapi)"
    return None


def _express(ctx: DetectionContext) -> str | None:
    if _contains(ctx.node_manifests(), '"express"'):
        return "package.json (express)"
    return None


def _nestjs(ctx: DetectionContext) -> str | None:
    if _contains(ctx.node_manifests(), '"@nestjs/core"'):
        return "package.json (@nestjs/core)"
    return None


def _nextjs(ctx: DetectionContext) -> str | None:
    if ctx.matches("next.config.*"):
        return "next.config.*"
    if _contains(ctx.node_manifests(), '"next"'):
        return "package.json (next)"
    return None


def _nuxt(ctx: DetectionContext) -> str | None:
    if ctx.matches("nuxt.config.*"):
        return "nuxt.config.*"
    if _contains(ctx.node_manifests(), '"nuxt"'):
        return "package.json (nuxt)"
    return None


def _react(ctx: DetectionContext) -> str | None:
    if _contains(ctx.node_manifests(), '"react"') and not _contains(
        ctx.node_manifests(), '"react-native"'
    ):
        return "package.json (react)"
    return None


def _react_native(ctx: DetectionContext) -> str | None:
    if _contains(ctx.node_manifests(), '"react-native"'):
        return "package.json (react-native)"
    return None


def _vue(ctx: DetectionContext) -> str | None:
    if ctx.matches("vue.config.*") or _contains(ctx.node_manifests(), '"vue"'):
        return "vue.config.* / package.json (vue)"
    return None


def _angular(ctx: DetectionContext) -> str | None:
    if ctx.exists("angular.json") or _contains(ctx.node_manifests(), '"@angular/core"'):
        return "angular.json / package.json (@angular/core)"
    return None


def _svelte(ctx: DetectionContext) -> str | None:
    if ctx.matches("svelte.config.*") or _contains(ctx.node_manifests(), '"svelte"'):
        return "svelte.config.* / package.json (svelte)"
    return None


def _spring_boot(ctx: DetectionContext) -> str | None:
    build = (ctx.read("pom.xml") + ctx.read("build.gradle") + ctx.read("build.gradle.kts")).lower()
    if _contains(build, "spring-boot"):
        return "Maven/Gradle manifest (spring-boot)"
    return None


def _aspnet(ctx: DetectionContext) -> str | None:
    if any(path.endswith((".csproj", ".fsproj", ".vbproj")) for path in ctx.paths):
        return ".NET project file"
    return None


def _flutter(ctx: DetectionContext) -> str | None:
    pubspec = ctx.read("pubspec.yaml")
    if pubspec and _contains(pubspec.lower(), "flutter"):
        return "pubspec.yaml (flutter)"
    return None


def _package_manager(name: str, condition: Callable[[DetectionContext], bool]) -> TechnologyRule:
    return TechnologyRule(name, "package_manager", lambda ctx: name if condition(ctx) else None)


DEFAULT_RULES: tuple[TechnologyRule, ...] = (
    TechnologyRule("Laravel", "framework", _laravel),
    TechnologyRule("Symfony", "framework", _symfony),
    TechnologyRule("Django", "framework", _django),
    TechnologyRule("Flask", "framework", _flask),
    TechnologyRule("FastAPI", "framework", _fastapi),
    TechnologyRule("Express", "framework", _express),
    TechnologyRule("NestJS", "framework", _nestjs),
    TechnologyRule("Next.js", "framework", _nextjs),
    TechnologyRule("Nuxt", "framework", _nuxt),
    TechnologyRule("React", "framework", _react),
    TechnologyRule("React Native", "framework", _react_native),
    TechnologyRule("Vue", "framework", _vue),
    TechnologyRule("Angular", "framework", _angular),
    TechnologyRule("Svelte", "framework", _svelte),
    TechnologyRule("Spring Boot", "framework", _spring_boot),
    TechnologyRule("ASP.NET", "framework", _aspnet),
    TechnologyRule("Flutter", "framework", _flutter),
    _package_manager(
        "Poetry",
        lambda ctx: (
            "[tool.poetry]" in ctx.read("pyproject.toml").lower() or ctx.exists("poetry.lock")
        ),
    ),
    _package_manager("uv", lambda ctx: ctx.exists("uv.lock")),
    _package_manager(
        "pip",
        lambda ctx: (
            ctx.exists("requirements.txt")
            or (
                ctx.exists("pyproject.toml")
                and "[tool.poetry]" not in ctx.read("pyproject.toml").lower()
                and not ctx.exists("uv.lock")
            )
        ),
    ),
    _package_manager("Pipenv", lambda ctx: ctx.exists("Pipfile")),
    _package_manager("Composer", lambda ctx: ctx.exists("composer.json")),
    _package_manager("pnpm", lambda ctx: ctx.exists("pnpm-lock.yaml")),
    _package_manager("yarn", lambda ctx: ctx.exists("yarn.lock")),
    _package_manager(
        "npm",
        lambda ctx: (
            ctx.exists("package-lock.json")
            or (
                ctx.exists("package.json")
                and not ctx.exists("pnpm-lock.yaml")
                and not ctx.exists("yarn.lock")
            )
        ),
    ),
    _package_manager("Cargo", lambda ctx: ctx.exists("Cargo.toml")),
    _package_manager("Maven", lambda ctx: ctx.exists("pom.xml")),
    _package_manager(
        "Gradle", lambda ctx: ctx.exists("build.gradle") or ctx.exists("build.gradle.kts")
    ),
    _package_manager("Bundler", lambda ctx: ctx.exists("Gemfile")),
    _package_manager("Go modules", lambda ctx: ctx.exists("go.mod")),
    _package_manager("pub", lambda ctx: ctx.exists("pubspec.yaml")),
    _package_manager(
        "NuGet", lambda ctx: any(path.endswith((".csproj", ".fsproj")) for path in ctx.paths)
    ),
)

_ENTRY_POINT_CANDIDATES: tuple[str, ...] = (
    "manage.py",
    "artisan",
    "bin/console",
    "public/index.php",
    "index.php",
    "main.py",
    "app.py",
    "run.py",
    "server.py",
    "src/main.py",
    "index.js",
    "src/index.js",
    "src/index.ts",
    "src/main.ts",
    "src/main.tsx",
    "src/App.tsx",
    "src/app.ts",
    "server.js",
    "app.js",
    "main.go",
    "src/main.rs",
    "lib/main.dart",
    "Program.cs",
    "bin/www",
)


@dataclass(slots=True)
class DetectionResult:
    """All technologies found in a project."""

    languages: list[tuple[str, int]] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)
    package_managers: list[str] = field(default_factory=list)
    technologies: list[Technology] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)
    config_files: list[str] = field(default_factory=list)


class ProjectDetector:
    """Registry-driven project detector."""

    def __init__(self, rules: Iterable[TechnologyRule] | None = None) -> None:
        self.rules: list[TechnologyRule] = list(DEFAULT_RULES if rules is None else rules)

    def register(self, rule: TechnologyRule) -> None:
        """Add a rule without changing the detection engine."""
        self.rules.append(rule)

    def detect(self, root: Path, entries: list[FileEntry]) -> DetectionResult:
        """Detect languages, frameworks, package managers and entry points."""
        for entry in entries:
            if entry.category is FileCategory.UNKNOWN and not entry.is_sensitive:
                classify_entry(entry)
        context = DetectionContext.build(root, entries)
        result = DetectionResult()
        result.languages = self._detect_languages(entries)
        seen: set[tuple[str, str]] = set()

        for rule in self.rules:
            try:
                evidence = rule.detector(context)
            except Exception:  # a broken custom rule must not stop detection
                evidence = None
            if not evidence:
                continue
            key = (rule.kind, rule.name)
            if key in seen:
                continue
            seen.add(key)
            result.technologies.append(Technology(rule.name, rule.kind, evidence))
            if rule.kind == "framework":
                result.frameworks.append(rule.name)
            elif rule.kind == "package_manager":
                result.package_managers.append(rule.name)

        result.frameworks.sort()
        result.package_managers.sort()
        result.entry_points = self._detect_entry_points(context)
        result.config_files = sorted(
            entry.relative_path for entry in entries if entry.category is FileCategory.CONFIGURATION
        )
        for language, count in result.languages:
            result.technologies.append(Technology(language, "language", f"{count} file(s)"))
        return result

    @staticmethod
    def _detect_languages(entries: list[FileEntry]) -> list[tuple[str, int]]:
        counts: Counter[str] = Counter()
        for entry in entries:
            if entry.category not in _LANGUAGE_CATEGORIES:
                continue
            language = entry.language or language_for(entry.name)
            if language:
                counts[language] += 1
        return sorted(counts.items(), key=lambda item: (-item[1], item[0]))

    @staticmethod
    def _detect_entry_points(context: DetectionContext) -> list[str]:
        found = [candidate for candidate in _ENTRY_POINT_CANDIDATES if context.exists(candidate)]
        for path in sorted(context.paths):
            if fnmatch.fnmatchcase(path, "cmd/*/main.go"):
                found.append(path)
        return list(dict.fromkeys(found))
