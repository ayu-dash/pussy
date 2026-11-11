"""Pipeline orchestration shared by all CLI commands.

Keeping this logic outside :mod:`pussy.cli` makes every stage usable from tests
and from other tools without going through the terminal.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from pussy.analyzers.dependency import DependencyAnalyzer
from pussy.analyzers.git_analyzer import GitAnalyzer
from pussy.config.loader import read_ignore_file
from pussy.config.models import PussyConfig
from pussy.core.classifier import classify_entries
from pussy.core.context_builder import BuildOptions, ContextBuilder
from pussy.core.detector import DetectionResult, ProjectDetector
from pussy.core.scanner import Scanner, ScanResult
from pussy.filters.ignore import IgnoreManager, IncludeManager
from pussy.models.context import ContextBundle
from pussy.models.project import DependencyReport, GitInfo

Progress = Callable[[str], None]


@dataclass(slots=True)
class ScanOutcome:
    """Results of the analysis stages that do not read file contents."""

    scan: ScanResult
    detection: DetectionResult
    dependencies: DependencyReport
    git: GitInfo | None
    warnings: list[str] = field(default_factory=list)


def build_ignore_manager(config: PussyConfig) -> IgnoreManager:
    """Assemble ignore rules in documented precedence order."""
    ignore_lines: list[str] = []
    if config.ignore_file is not None:
        ignore_lines = read_ignore_file(config.ignore_file)
    defaults = _default_patterns() if config.use_default_ignores else ()
    return IgnoreManager.from_sources(
        defaults=defaults,
        ignore_file_lines=ignore_lines,
        config_patterns=config.ignore_patterns,
        cli_patterns=config.cli_ignore_patterns,
    )


def _default_patterns() -> tuple[str, ...]:
    from pussy.config.defaults import DEFAULT_IGNORE_PATTERNS

    return DEFAULT_IGNORE_PATTERNS


def scan_project(config: PussyConfig, progress: Progress | None = None) -> ScanOutcome:
    """Scan and analyze a project without reading file contents."""
    scanner = Scanner(
        config.root,
        build_ignore_manager(config),
        includes=IncludeManager(config.include_patterns),
        include_hidden=config.include_hidden,
        follow_symlinks=config.follow_symlinks,
        exclude_paths=config.exclude_paths,
    )
    scan = scanner.scan(progress)
    classify_entries(scan.files)

    detector = ProjectDetector()
    detection = detector.detect(config.root, scan.files)
    dependencies = DependencyAnalyzer().analyze(config.root, scan.files)

    git: GitInfo | None = None
    if config.include_git:
        try:
            git = GitAnalyzer(max_diff_chars=config.max_diff_chars).analyze(
                config.root, include_diff=config.include_git_diff
            )
        except Exception as exc:  # Git problems are never fatal
            git = GitInfo(is_repo=False, error=f"Git analysis failed: {exc}")

    warnings = list(config.warnings)
    warnings.extend(scan.warnings)
    warnings.extend(dependencies.warnings)
    if git is not None and git.error and git.is_repo:
        warnings.append(f"Git: {git.error}")
    return ScanOutcome(
        scan=scan,
        detection=detection,
        dependencies=dependencies,
        git=git,
        warnings=warnings,
    )


def generate_context(
    config: PussyConfig,
    *,
    scan_progress: Progress | None = None,
    read_progress: Progress | None = None,
    tree_only: bool = False,
    code_only: bool = False,
) -> ContextBundle:
    """Run the complete pipeline and return a render-ready bundle."""
    outcome = scan_project(config, progress=scan_progress)
    options = BuildOptions(
        mode=config.mode,
        tree_only=tree_only,
        code_only=code_only,
        include_extensions=set(config.include_extensions),
        exclude_extensions=set(config.exclude_extensions),
        model=config.model,
        tokenizer=config.tokenizer,
    )
    bundle = ContextBuilder(
        options,
        max_file_size=config.max_file_size,
        max_total_size=config.max_total_size,
    ).build(
        outcome.scan,
        outcome.detection,
        outcome.dependencies,
        outcome.git,
        read_progress=read_progress,
    )
    bundle.warnings = list(dict.fromkeys([*bundle.warnings, *outcome.warnings]))
    return bundle
