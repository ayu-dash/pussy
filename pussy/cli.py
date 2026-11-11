"""Typer command-line interface for Pussy CLI."""

from __future__ import annotations

import functools
import json as jsonlib
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from pussy import __version__
from pussy.config.defaults import (
    DEFAULT_IGNORE_PATTERNS,
    IGNORE_FILENAME,
    PROJECT_CONFIG_FILENAME,
    PROJECT_CONFIG_TEMPLATE,
    PUSSYIGNORE_TEMPLATE,
    USER_CONFIG_TEMPLATE,
)
from pussy.config.loader import load_config, user_config_path
from pussy.config.models import PussyConfig
from pussy.core.pipeline import ScanOutcome, generate_context, scan_project
from pussy.errors import (
    EXIT_CONFLICT,
    ConfigError,
    ExportConflictError,
    PussyError,
)
from pussy.formatters.json import JsonFormatter
from pussy.formatters.markdown import MarkdownFormatter
from pussy.formatters.tree import render_tree
from pussy.integrations.clipboard import ClipboardManager
from pussy.integrations.exporter import ExportManager
from pussy.utils.filesystem import is_within, write_atomic
from pussy.utils.size import human_size, parse_size

console = Console()
error_console = Console(stderr=True)

F = TypeVar("F", bound=Callable[..., Any])


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"Pussy CLI {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="pussy",
    help=(
        "Universal AI context generator. Turn a software project into a "
        "structured Markdown or JSON context for LLMs."
    ),
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich",
    context_settings={"help_option_names": ["-h", "--help"]},
)


def _handle_errors(function: F) -> F:
    """Convert expected application errors into clean messages and exit codes."""

    @functools.wraps(function)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return function(*args, **kwargs)
        except PussyError as exc:
            error_console.print(f"[bold red]Error:[/bold red] {exc}")
            raise typer.Exit(exc.exit_code) from exc
        except KeyboardInterrupt:
            error_console.print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit(130) from None

    return wrapper  # type: ignore[return-value]


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        callback=_version_callback,
        is_eager=True,
        help="Show the version and exit.",
    ),
) -> None:
    """Pussy CLI command group."""


# ----------------------------------------------------------------------
# Shared helpers
# ----------------------------------------------------------------------
def _resolve_root(path: str | Path) -> Path:
    candidate = Path(path).expanduser()
    if not candidate.exists():
        raise ConfigError(f"path does not exist: {candidate}")
    if not candidate.is_dir():
        raise ConfigError(f"path is not a directory: {candidate}")
    return candidate.resolve()


def _split_values(values: list[str] | None) -> list[str]:
    result: list[str] = []
    for value in values or []:
        result.extend(part.strip() for part in value.split(",") if part.strip())
    return result


def _apply_common_options(
    config: PussyConfig,
    *,
    include_hidden: bool | None,
    follow_symlinks: bool,
    max_size: str | None,
    exclude: list[str] | None,
    include: list[str] | None = None,
    exclude_ext: list[str] | None = None,
    include_ext: list[str] | None = None,
) -> None:
    if include_hidden is not None:
        config.include_hidden = include_hidden
    if follow_symlinks:
        config.follow_symlinks = True
    if max_size:
        try:
            config.max_file_size = parse_size(max_size)
        except ValueError as exc:
            raise ConfigError(str(exc)) from exc
    config.cli_ignore_patterns.extend(_split_values(exclude))
    config.include_patterns.extend(_split_values(include))
    for extension in _split_values(include_ext):
        config.include_extensions.add(extension if extension.startswith(".") else f".{extension}")
    for extension in _split_values(exclude_ext):
        config.exclude_extensions.add(extension if extension.startswith(".") else f".{extension}")


def _config_from_options(
    path: str,
    *,
    config_path: Path | None,
    include_hidden: bool | None = None,
    follow_symlinks: bool = False,
    max_size: str | None = None,
    exclude: list[str] | None = None,
    include: list[str] | None = None,
    exclude_ext: list[str] | None = None,
    include_ext: list[str] | None = None,
    no_git: bool = False,
) -> PussyConfig:
    root = _resolve_root(path)
    config = load_config(root, config_path)
    _apply_common_options(
        config,
        include_hidden=include_hidden,
        follow_symlinks=follow_symlinks,
        max_size=max_size,
        exclude=exclude,
        include=include,
        exclude_ext=exclude_ext,
        include_ext=include_ext,
    )
    if no_git:
        config.include_git = False
    return config


def _progress(disabled: bool) -> Progress:
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
        disable=disabled,
    )


def _show_warnings(warnings: list[str]) -> None:
    if not warnings:
        return
    shown = warnings[:10]
    lines = [f"- {warning}" for warning in shown]
    if len(warnings) > len(shown):
        lines.append(f"- ... and {len(warnings) - len(shown)} more")
    error_console.print(
        Panel("\n".join(lines), title="Warnings", border_style="yellow", expand=False)
    )


def _category_table(outcome: ScanOutcome) -> Table:
    table = Table(title="Files by Category", show_header=True, header_style="bold")
    table.add_column("Category")
    table.add_column("Files", justify="right")
    table.add_column("Size", justify="right")
    counts: dict[str, int] = {}
    sizes: dict[str, int] = {}
    for entry in outcome.scan.files:
        label = entry.category.label
        counts[label] = counts.get(label, 0) + 1
        sizes[label] = sizes.get(label, 0) + entry.size
    for label in sorted(counts):
        table.add_row(label, str(counts[label]), human_size(sizes[label]))
    return table


def _scan_summary_panel(outcome: ScanOutcome) -> Panel:
    scan = outcome.scan
    included = sum(1 for entry in scan.files if entry.included)
    languages = ", ".join(name for name, _ in outcome.detection.languages) or "Not detected"
    frameworks = ", ".join(outcome.detection.frameworks) or "Not detected"
    lines = [
        f"[bold]Root:[/bold] {scan.root}",
        f"[bold]Files:[/bold] {scan.file_count} ({included} selected)",
        f"[bold]Directories:[/bold] {scan.directory_count}",
        f"[bold]Skipped directories:[/bold] {len(scan.skipped_directories)}",
        f"[bold]Languages:[/bold] {languages}",
        f"[bold]Frameworks:[/bold] {frameworks}",
    ]
    return Panel("\n".join(lines), title="Scan Summary", border_style="cyan", expand=False)


def _write_output(path: Path, text: str, *, force: bool) -> Path:
    """Write an export, prompting only in an interactive terminal."""
    if path.exists() and not force:
        if sys.stdin.isatty():
            if not typer.confirm(f"Output file {path} exists. Overwrite?"):
                raise typer.Exit(EXIT_CONFLICT)
            force = True
        else:
            raise ExportConflictError(
                f"output file already exists: {path} (use --force to overwrite)"
            )
    return ExportManager().write(path, text, force=force)


# ----------------------------------------------------------------------
# Commands
# ----------------------------------------------------------------------
@app.command(help="Scan a project and display file statistics without emitting a context.")
@_handle_errors
def scan(
    path: str = typer.Argument(".", help="Project directory to scan."),
    config_path: Path | None = typer.Option(None, "--config", help="Explicit TOML config file."),
    exclude: list[str] = typer.Option(
        [], "--exclude", "-x", help="Ignore glob(s), comma-separated."
    ),
    include_hidden: bool | None = typer.Option(
        None, "--hidden/--no-hidden", help="Include hidden files and directories."
    ),
    follow_symlinks: bool = typer.Option(False, "--follow-symlinks", help="Follow safe symlinks."),
    max_size: str | None = typer.Option(None, "--max-size", help="Maximum file size, e.g. 1MB."),
    limit: int = typer.Option(10, "--limit", min=0, help="Files to list (0 hides the list)."),
    no_progress: bool = typer.Option(
        False, "--no-progress", help="Disable the progress indicator."
    ),
) -> None:
    """Scan and report file metadata."""
    config = _config_from_options(
        path,
        config_path=config_path,
        include_hidden=include_hidden,
        follow_symlinks=follow_symlinks,
        max_size=max_size,
        exclude=exclude,
    )
    with _progress(no_progress or not console.is_terminal) as progress:
        task = progress.add_task("Scanning project...", total=None)

        def update(relative_path: str) -> None:
            progress.update(task, description=f"Scanning {relative_path}")

        outcome = scan_project(config, progress=update)

    console.print(_scan_summary_panel(outcome))
    console.print(_category_table(outcome))
    if limit:
        table = Table(title=f"First {min(limit, len(outcome.scan.files))} Files")
        table.add_column("Path", overflow="fold")
        table.add_column("Category")
        table.add_column("Size", justify="right")
        table.add_column("Status")
        for entry in sorted(outcome.scan.files, key=lambda item: item.relative_path.casefold())[
            :limit
        ]:
            status = "included" if entry.included else (entry.exclusion_reason or "excluded")
            table.add_row(entry.relative_path, entry.category.label, human_size(entry.size), status)
        console.print(table)
    _show_warnings(outcome.warnings)


@app.command(help="Print only the project directory tree.")
@_handle_errors
def tree(
    path: str = typer.Argument(".", help="Project directory."),
    config_path: Path | None = typer.Option(None, "--config", help="Explicit TOML config file."),
    exclude: list[str] = typer.Option(
        [], "--exclude", "-x", help="Ignore glob(s), comma-separated."
    ),
    include_hidden: bool | None = typer.Option(None, "--hidden/--no-hidden"),
    ascii_only: bool = typer.Option(False, "--ascii", help="Use ASCII connectors."),
    no_progress: bool = typer.Option(False, "--no-progress"),
) -> None:
    """Render the directory tree without file contents."""
    config = _config_from_options(
        path,
        config_path=config_path,
        include_hidden=include_hidden,
        exclude=exclude,
    )
    with _progress(no_progress or not console.is_terminal) as progress:
        progress.add_task("Scanning project...", total=None)
        outcome = scan_project(config)
    output = render_tree(
        config.root.name,
        outcome.scan.directories,
        [entry.relative_path for entry in outcome.scan.files],
        ascii_only=ascii_only,
    )
    sys.stdout.write(output)
    _show_warnings(outcome.warnings)


@app.command(help="Show detected technologies, dependencies and Git status.")
@_handle_errors
def info(
    path: str = typer.Argument(".", help="Project directory."),
    config_path: Path | None = typer.Option(None, "--config", help="Explicit TOML config file."),
    exclude: list[str] = typer.Option(
        [], "--exclude", "-x", help="Ignore glob(s), comma-separated."
    ),
    no_git: bool = typer.Option(False, "--no-git", help="Skip Git analysis."),
    no_progress: bool = typer.Option(False, "--no-progress"),
) -> None:
    """Display project intelligence."""
    config = _config_from_options(path, config_path=config_path, exclude=exclude, no_git=no_git)
    with _progress(no_progress or not console.is_terminal) as progress:
        progress.add_task("Analyzing project...", total=None)
        outcome = scan_project(config)
    detection = outcome.detection
    overview = [
        f"[bold]Project:[/bold] {config.root.name}",
        f"[bold]Root:[/bold] {config.root}",
        f"[bold]Files:[/bold] {outcome.scan.file_count}",
        f"[bold]Directories:[/bold] {outcome.scan.directory_count}",
        f"[bold]Dependencies:[/bold] {len(outcome.dependencies.dependencies)}",
        f"[bold]Package Managers:[/bold] {', '.join(detection.package_managers) or 'Not detected'}",
        f"[bold]Entry Points:[/bold] {', '.join(detection.entry_points) or 'Not detected'}",
    ]
    console.print(
        Panel("\n".join(overview), title="Project Info", border_style="cyan", expand=False)
    )

    if detection.technologies:
        tech_table = Table(title="Detected Technologies")
        tech_table.add_column("Technology")
        tech_table.add_column("Kind")
        tech_table.add_column("Evidence", overflow="fold")
        for technology in detection.technologies:
            tech_table.add_row(technology.name, technology.kind, technology.evidence)
        console.print(tech_table)

    if outcome.dependencies.dependencies:
        grouped = outcome.dependencies.by_scope()
        dependency_table = Table(title="Dependencies")
        dependency_table.add_column("Scope")
        dependency_table.add_column("Count", justify="right")
        for scope, items in grouped.items():
            dependency_table.add_row(scope, str(len(items)))
        console.print(dependency_table)

    git = outcome.git
    if git is None:
        console.print("[dim]Git analysis disabled.[/dim]")
    elif not git.is_repo:
        console.print(f"[dim]Git: {git.error or 'not a repository'}[/dim]")
    else:
        git_table = Table(title="Git")
        git_table.add_column("Field")
        git_table.add_column("Value", overflow="fold")
        git_table.add_row("Branch", git.branch or "(detached HEAD)")
        git_table.add_row(
            "Last commit", f"{git.commit_short or '?'} {git.commit_subject or ''}".strip()
        )
        git_table.add_row("Author", git.commit_author or "Unknown")
        git_table.add_row("Working tree", "dirty" if git.is_dirty else "clean")
        git_table.add_row("Changed files", str(len(git.changes)))
        console.print(git_table)
    _show_warnings(outcome.warnings)


@app.command(help="Generate an AI-ready context document.")
@_handle_errors
def generate(
    path: str = typer.Argument(".", help="Project directory."),
    config_path: Path | None = typer.Option(None, "--config", help="Explicit TOML config file."),
    mode: str | None = typer.Option(None, "--mode", "-m", help="overview | context | full"),
    output_format: str | None = typer.Option(None, "--format", "-f", help="markdown | json"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write output to a file."),
    save: bool = typer.Option(
        False, "--save", help="Auto-name an output file in the project root."
    ),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing output file."),
    copy: bool = typer.Option(False, "--copy", "-c", help="Copy the result to the clipboard."),
    include_ext: list[str] = typer.Option(
        [], "--include-ext", help="Extensions to include, e.g. py,ts."
    ),
    exclude_ext: list[str] = typer.Option(
        [], "--exclude-ext", help="Extensions to exclude, e.g. lock,log."
    ),
    exclude: list[str] = typer.Option(
        [], "--exclude", "-x", help="Ignore glob(s), comma-separated."
    ),
    include: list[str] = typer.Option([], "--include", "-i", help="Explicit include glob(s)."),
    max_size: str | None = typer.Option(None, "--max-size", help="Maximum file size, e.g. 1MB."),
    max_total_size: str | None = typer.Option(
        None, "--max-total-size", help="Maximum total content size, e.g. 64MB."
    ),
    tree_only: bool = typer.Option(False, "--tree-only", help="Emit the tree and report only."),
    code_only: bool = typer.Option(
        False, "--code-only", help="Emit file contents without overview/tree."
    ),
    git: bool = typer.Option(True, "--git/--no-git", help="Include Git information."),
    git_diff: bool = typer.Option(False, "--git-diff", help="Include the working-tree diff."),
    model: str | None = typer.Option(None, "--model", help="Model name for tokenizer selection."),
    tokenizer: str | None = typer.Option(None, "--tokenizer", help="auto | approximate | tiktoken"),
    include_hidden: bool | None = typer.Option(None, "--hidden/--no-hidden"),
    follow_symlinks: bool = typer.Option(False, "--follow-symlinks"),
    no_progress: bool = typer.Option(
        False, "--no-progress", help="Disable the progress indicator."
    ),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress status messages."),
) -> None:
    """Generate Markdown or JSON context."""
    if tree_only and code_only:
        raise ConfigError("--tree-only and --code-only cannot be used together")
    config = _config_from_options(
        path,
        config_path=config_path,
        include_hidden=include_hidden,
        follow_symlinks=follow_symlinks,
        max_size=max_size,
        exclude=exclude,
        include=include,
        exclude_ext=exclude_ext,
        include_ext=include_ext,
        no_git=not git,
    )
    if mode:
        config.mode = mode.lower()
    if output_format:
        config.output_format = output_format.lower()
    if max_total_size:
        try:
            config.max_total_size = parse_size(max_total_size)
        except ValueError as exc:
            raise ConfigError(str(exc)) from exc
    if model:
        config.model = model
    if tokenizer:
        config.tokenizer = tokenizer.lower()
    if git_diff:
        config.include_git = True
        config.include_git_diff = True
    config.validate()

    export_manager = ExportManager()
    output_path = export_manager.resolve_path(
        output,
        output_format=config.output_format,
        root=config.root,
        auto_name=save,
    )
    if output_path is not None and is_within(output_path, config.root):
        config.exclude_paths.append(output_path)

    progress_disabled = no_progress or quiet or not console.is_terminal
    with _progress(progress_disabled) as progress:
        task = progress.add_task("Scanning project...", total=None)

        def update_scan(relative_path: str) -> None:
            progress.update(task, description=f"Scanning {relative_path}")

        def update_read(relative_path: str) -> None:
            progress.update(task, description=f"Reading {relative_path}")

        bundle = generate_context(
            config,
            scan_progress=update_scan,
            read_progress=update_read,
            tree_only=tree_only,
            code_only=code_only,
        )

    formatter = JsonFormatter() if config.output_format == "json" else MarkdownFormatter()
    rendered = formatter.render(bundle)

    written_path: Path | None = None
    if output_path is not None:
        written_path = _write_output(output_path, rendered, force=force)

    clipboard_result = None
    if copy:
        clipboard_result = ClipboardManager().copy(rendered)
        if not clipboard_result.success:
            error_console.print(f"[yellow]Clipboard copy failed:[/yellow] {clipboard_result.error}")

    if written_path is None and not copy:
        sys.stdout.write(rendered)
    elif written_path is None and copy and clipboard_result and not clipboard_result.success:
        error_console.print("[yellow]Falling back to standard output.[/yellow]")
        sys.stdout.write(rendered)

    if not quiet:
        stats = bundle.stats
        approximate = "~" if stats.approximate else ""
        details = (
            f"{stats.files_included} files, {approximate}{stats.estimated_tokens:,} tokens "
            f"({stats.tokenizer})"
        )
        if written_path is not None:
            error_console.print(f"[green]Wrote[/green] {written_path} [dim]({details})[/dim]")
        if copy and clipboard_result and clipboard_result.success:
            error_console.print(
                f"[green]Copied to clipboard[/green] via {clipboard_result.command} "
                f"[dim]({details})[/dim]"
            )
    _show_warnings(bundle.warnings)


@app.command(help="Create a .pussyignore file (and optionally pussy.toml).")
@_handle_errors
def init(
    path: str = typer.Argument(".", help="Project directory."),
    with_config: bool = typer.Option(False, "--with-config", help="Also create pussy.toml."),
    force: bool = typer.Option(False, "--force", help="Overwrite existing files."),
) -> None:
    """Initialise ignore and configuration files."""
    root = _resolve_root(path)
    targets = [(root / IGNORE_FILENAME, PUSSYIGNORE_TEMPLATE)]
    if with_config:
        targets.append((root / PROJECT_CONFIG_FILENAME, PROJECT_CONFIG_TEMPLATE))
    for target, template in targets:
        if target.exists() and not force:
            console.print(f"[yellow]Skipped[/yellow] {target} (already exists)")
            continue
        write_atomic(target, template)
        console.print(f"[green]Created[/green] {target}")


@app.command(name="config", help="Show resolved configuration or create a user config.")
@_handle_errors
def config_command(
    path: str = typer.Argument(".", help="Project directory."),
    config_path: Path | None = typer.Option(None, "--config", help="Explicit TOML config file."),
    initialise: bool = typer.Option(False, "--init", help="Create the user config file."),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing user config."),
    as_json: bool = typer.Option(False, "--json", help="Print resolved config as JSON."),
) -> None:
    """Display resolved settings and loaded files."""
    if initialise:
        target = user_config_path()
        if target.exists() and not force:
            raise ExportConflictError(
                f"user config already exists: {target} (use --force to overwrite)"
            )
        write_atomic(target, USER_CONFIG_TEMPLATE)
        console.print(f"[green]Created[/green] {target}")
        return

    root = _resolve_root(path)
    config = load_config(root, config_path)
    config.validate()
    if as_json:
        payload = {
            "root": str(config.root),
            "config_files": [str(item) for item in config.config_files],
            "ignore_file": str(config.ignore_file) if config.ignore_file else None,
            "mode": config.mode,
            "format": config.output_format,
            "include_hidden": config.include_hidden,
            "follow_symlinks": config.follow_symlinks,
            "max_file_size": config.max_file_size,
            "max_total_size": config.max_total_size,
            "include_extensions": sorted(config.include_extensions),
            "exclude_extensions": sorted(config.exclude_extensions),
            "git": {
                "enabled": config.include_git,
                "include_diff": config.include_git_diff,
            },
            "tokens": {"tokenizer": config.tokenizer, "model": config.model},
        }
        console.print_json(jsonlib.dumps(payload))
        return

    table = Table(title="Resolved Configuration")
    table.add_column("Setting")
    table.add_column("Value", overflow="fold")
    table.add_row("Project root", str(config.root))
    table.add_row("Config files", ", ".join(str(item) for item in config.config_files) or "(none)")
    table.add_row("Ignore file", str(config.ignore_file) if config.ignore_file else "(none)")
    table.add_row("Default ignore rules", str(len(DEFAULT_IGNORE_PATTERNS)))
    table.add_row("Config ignore rules", str(len(config.ignore_patterns)))
    table.add_row("Mode", config.mode)
    table.add_row("Format", config.output_format)
    table.add_row("Include hidden", str(config.include_hidden))
    table.add_row("Follow symlinks", str(config.follow_symlinks))
    table.add_row("Max file size", human_size(config.max_file_size))
    table.add_row("Max total size", human_size(config.max_total_size))
    table.add_row("Include extensions", ", ".join(sorted(config.include_extensions)) or "(all)")
    table.add_row("Exclude extensions", ", ".join(sorted(config.exclude_extensions)) or "(none)")
    table.add_row("Git", "enabled" if config.include_git else "disabled")
    table.add_row("Git diff", "enabled" if config.include_git_diff else "disabled")
    table.add_row("Tokenizer", config.tokenizer)
    table.add_row("Model", config.model or "(none)")
    console.print(table)
    console.print(
        f"[dim]User config path: {user_config_path()} (create with `pussy config --init`)[/dim]"
    )


if __name__ == "__main__":  # pragma: no cover
    app()
