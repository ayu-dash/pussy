"""Safe output export management."""

from __future__ import annotations

import time
from pathlib import Path

from pussy.errors import ExportConflictError, ExportError
from pussy.utils.filesystem import write_atomic


class ExportManager:
    """Resolve output paths and write files without silent overwrites."""

    def resolve_path(
        self,
        output: Path | str | None,
        *,
        output_format: str,
        root: Path | None = None,
        auto_name: bool = False,
    ) -> Path | None:
        """Return the destination path, or None when no file export is requested."""
        extension = ".json" if output_format == "json" else ".md"
        if output is None:
            if not auto_name:
                return None
            base_directory = root or Path.cwd()
            return self._unique_path(
                base_directory / f"pussy-context-{time.strftime('%Y%m%d-%H%M%S')}{extension}"
            )

        path = Path(output).expanduser()
        if path.is_dir() or str(output).endswith(("/", "\\")):
            path = path / f"pussy-context-{time.strftime('%Y%m%d-%H%M%S')}{extension}"
        elif not path.suffix:
            path = path.with_suffix(extension)
        return path

    def write(self, path: Path, text: str, *, force: bool = False) -> Path:
        """Write text atomically, refusing to replace an existing file by default."""
        path = path.expanduser()
        if path.exists() and not force:
            raise ExportConflictError(
                f"output file already exists: {path} (use --force to overwrite)"
            )
        try:
            write_atomic(path, text)
        except OSError as exc:
            raise ExportError(f"cannot write {path}: {exc}") from exc
        return path

    @staticmethod
    def _unique_path(path: Path) -> Path:
        if not path.exists():
            return path
        stem, suffix = path.stem, path.suffix
        for index in range(1, 1000):
            candidate = path.with_name(f"{stem}-{index}{suffix}")
            if not candidate.exists():
                return candidate
        raise ExportError(f"cannot find an unused output name near {path}")
