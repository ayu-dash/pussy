"""Structured JSON formatter for machine consumption."""

from __future__ import annotations

import json
from dataclasses import asdict

from pussy import __version__
from pussy.models.context import ContextBundle
from pussy.models.file_entry import FileEntry


def _entry_payload(entry: FileEntry) -> dict[str, object]:
    return {
        "path": entry.relative_path,
        "category": entry.category.value,
        "category_label": entry.category.label,
        "language": entry.language,
        "size": entry.size,
        "included": entry.included,
        "is_binary": entry.is_binary,
        "is_sensitive": entry.is_sensitive,
        "is_symlink": entry.is_symlink,
        "read_status": entry.read_status.value,
        "exclusion_reason": entry.exclusion_reason,
        "error": entry.error,
        "encoding": entry.encoding,
        "lines": entry.line_count,
        "content": entry.content if entry.has_content else None,
        "metadata": entry.metadata,
    }


class JsonFormatter:
    """Render a bundle as a stable, versioned JSON document."""

    schema_version = 1

    def render(self, bundle: ContextBundle) -> str:
        """Return pretty-printed JSON suitable for other tools."""
        git_payload: dict[str, object] | None = None
        if bundle.git is not None:
            git_payload = asdict(bundle.git)
        payload = {
            "schema_version": self.schema_version,
            "generator": {"name": "pussy-cli", "version": __version__},
            "generated_at": bundle.generated_at.isoformat(),
            "mode": bundle.mode,
            "tree_only": bundle.tree_only,
            "code_only": bundle.code_only,
            "project": asdict(bundle.project),
            "tree": bundle.tree,
            "dependencies": {
                "files_analyzed": bundle.dependencies.files_analyzed,
                "warnings": bundle.dependencies.warnings,
                "items": [asdict(dependency) for dependency in bundle.dependencies.dependencies],
            },
            "git": git_payload,
            "files": [
                _entry_payload(entry)
                for entry in sorted(bundle.entries, key=lambda item: item.relative_path.casefold())
            ],
            "report": {
                "included_files": bundle.stats.files_included,
                "excluded_files": bundle.stats.files_excluded,
                "skipped_directories": bundle.project.skipped_directories,
                "warnings": bundle.warnings,
            },
            "stats": asdict(bundle.stats),
        }
        return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
