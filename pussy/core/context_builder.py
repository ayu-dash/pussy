"""Context bundle construction."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from pussy.analyzers.project_info import build_project_info
from pussy.core.classifier import classify_entries
from pussy.core.detector import DetectionResult
from pussy.core.reader import FileReader
from pussy.core.scanner import ScanResult
from pussy.core.token_estimator import TokenEstimator
from pussy.filters.extensions import language_from_shebang
from pussy.formatters.tree import render_tree
from pussy.models.context import ContextBundle, ContextStats
from pussy.models.file_entry import FileCategory, FileEntry, ReadStatus
from pussy.models.project import DependencyReport, GitInfo

CONTENT_CATEGORIES: frozenset[FileCategory] = frozenset(
    {
        FileCategory.CONFIGURATION,
        FileCategory.SOURCE_CODE,
        FileCategory.DOCUMENTATION,
        FileCategory.DATABASE,
        FileCategory.TESTS,
        FileCategory.INFRASTRUCTURE,
    }
)

FULL_CONTENT_CATEGORIES: frozenset[FileCategory] = CONTENT_CATEGORIES | {
    FileCategory.GENERATED,
    FileCategory.UNKNOWN,
}

ReadProgress = Callable[[str], None]


@dataclass(slots=True)
class BuildOptions:
    """Generation choices that affect which content enters the bundle."""

    mode: str = "context"
    tree_only: bool = False
    code_only: bool = False
    include_extensions: set[str] = field(default_factory=set)
    exclude_extensions: set[str] = field(default_factory=set)
    model: str | None = None
    tokenizer: str = "auto"

    def allowed_categories(self) -> frozenset[FileCategory]:
        """Categories whose content belongs in the selected mode."""
        if self.mode == "full":
            return FULL_CONTENT_CATEGORIES
        return CONTENT_CATEGORIES


class ContextBuilder:
    """Turn scan results and analyses into a render-ready context bundle."""

    def __init__(
        self,
        options: BuildOptions | None = None,
        *,
        max_file_size: int = 1_048_576,
        max_total_size: int = 64 * 1024 * 1024,
    ) -> None:
        self.options = options or BuildOptions()
        self.max_file_size = max_file_size
        self.max_total_size = max_total_size

    def build(
        self,
        scan: ScanResult,
        detection: DetectionResult,
        dependencies: DependencyReport,
        git: GitInfo | None,
        *,
        read_progress: ReadProgress | None = None,
    ) -> ContextBundle:
        """Build the bundle, reading content only when the mode needs it."""
        classify_entries(scan.files)
        self._apply_extension_filters(scan.files)

        wants_content = not self.options.tree_only and self.options.mode != "overview"
        if wants_content:
            reader = FileReader(
                max_file_size=self.max_file_size,
                max_total_size=self.max_total_size,
            )
            reader.read_all(scan.files, progress=read_progress)
            self._apply_mode_policy(scan.files)
            for entry in scan.files:
                if entry.language is None and entry.content:
                    entry.language = language_from_shebang(entry.content)

        project = build_project_info(scan, detection, dependencies)
        tree = render_tree(
            scan.root.name or str(scan.root),
            scan.directories,
            [entry.relative_path for entry in scan.files],
        )
        stats = self._build_stats(scan.files, tree)
        return ContextBundle(
            project=project,
            entries=scan.files,
            tree=tree,
            dependencies=dependencies,
            git=git,
            stats=stats,
            mode=self.options.mode,
            tree_only=self.options.tree_only,
            code_only=self.options.code_only,
            warnings=list(project.warnings),
        )

    def _apply_extension_filters(self, entries: list[FileEntry]) -> None:
        include = self.options.include_extensions
        exclude = self.options.exclude_extensions
        for entry in entries:
            if not entry.included:
                continue
            if include and entry.suffix not in include:
                entry.exclude(f"extension {entry.suffix or '(none)'} not in include list")
                continue
            if entry.suffix in exclude:
                entry.exclude(f"extension {entry.suffix} excluded")

    def _apply_mode_policy(self, entries: list[FileEntry]) -> None:
        allowed = self.options.allowed_categories()
        for entry in entries:
            if not entry.included or entry.read_status is not ReadStatus.READ:
                continue
            if entry.category not in allowed:
                entry.exclude(
                    f"category '{entry.category.label}' is not included in {self.options.mode} mode"
                )

    def _build_stats(self, entries: list[FileEntry], tree: str) -> ContextStats:
        content_entries = [entry for entry in entries if entry.has_content]
        selected_count = sum(1 for entry in entries if entry.included)
        text_parts: list[str] = [tree]
        text_parts.extend(entry.content or "" for entry in content_entries)
        combined = "\n".join(text_parts)
        estimate = TokenEstimator(
            model=self.options.model, tokenizer=self.options.tokenizer
        ).estimate(combined)
        total_bytes = sum(entry.size for entry in content_entries) + len(tree.encode("utf-8"))
        return ContextStats(
            files_included=selected_count,
            files_excluded=len(entries) - selected_count,
            total_files=len(entries),
            characters=estimate.characters,
            words=estimate.words,
            lines=estimate.lines,
            bytes=total_bytes,
            estimated_tokens=estimate.tokens,
            tokenizer=estimate.tokenizer,
            estimation_method=(
                estimate.method + " (tree + file contents; formatting overhead excluded)"
            ),
            approximate=estimate.approximate,
        )


__all__ = [
    "CONTENT_CATEGORIES",
    "FULL_CONTENT_CATEGORIES",
    "BuildOptions",
    "ContextBuilder",
]
