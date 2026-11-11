"""Project overview construction from detected facts."""

from __future__ import annotations

from pussy.core.detector import DetectionResult
from pussy.core.scanner import ScanResult
from pussy.models.project import (
    DependencyReport,
    ProjectInfo,
)


def build_project_info(
    scan: ScanResult,
    detection: DetectionResult,
    dependencies: DependencyReport,
) -> ProjectInfo:
    """Create a :class:`ProjectInfo` without inventing missing facts."""
    category_counts: dict[str, int] = {}
    total_size = 0
    included = 0
    for entry in scan.files:
        category_counts[entry.category.label] = category_counts.get(entry.category.label, 0) + 1
        total_size += entry.size
        if entry.included:
            included += 1

    warnings = list(scan.warnings)
    warnings.extend(dependencies.warnings)
    # A missing repository is a normal project state, not a warning; it is
    # reported explicitly in the Git section instead.

    return ProjectInfo(
        name=scan.root.name or str(scan.root),
        root=str(scan.root),
        languages=[name for name, _count in detection.languages],
        frameworks=detection.frameworks,
        package_managers=detection.package_managers,
        entry_points=detection.entry_points,
        config_files=detection.config_files,
        technologies=detection.technologies,
        total_files=scan.file_count,
        total_directories=scan.directory_count,
        total_size=total_size,
        category_counts=dict(sorted(category_counts.items())),
        included_count=included,
        excluded_count=scan.file_count - included,
        skipped_directories=scan.skipped_directories,
        warnings=warnings,
        dependency_count=len(dependencies.dependencies),
    )
