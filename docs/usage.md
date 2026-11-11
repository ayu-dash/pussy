# Usage guide

This guide covers every command, option and output mode. For setup and a quick
overview, start with the [README](../README.md).

## Command model

```text
python -m pussy [--version] COMMAND [PATH] [OPTIONS]
```

- `PATH` defaults to the current directory and must be a readable directory.
- Options may be passed before or after the path.
- Errors are printed to stderr with a stable exit code (see
  [exit codes](#exit-codes)).
- Status messages, progress and warnings go to stderr; the generated document is
  written to stdout unless `--output` or `--save` is used. This keeps pipelines
  such as `python -m pussy generate . > context.md` clean.

## Commands

### `scan`

Scan file metadata without reading any file contents. Useful for checking what
Pussy would include before generating a prompt.

```bash
python -m pussy scan .
python -m pussy scan ./service --limit 25 --exclude "*.snap"
python -m pussy scan . --no-hidden --max-size 512KB
```

| Option | Description |
| --- | --- |
| `--config PATH` | Explicit TOML configuration file. |
| `--exclude`, `-x GLOB` | Additional ignore glob(s), comma-separated. Repeatable. |
| `--hidden / --no-hidden` | Include or exclude hidden files and directories. |
| `--follow-symlinks` | Follow symlinks that stay inside the project root. |
| `--max-size SIZE` | Maximum individual file size (for example `1MB`). |
| `--limit N` | Number of files to list; `0` hides the file list (default `10`). |
| `--no-progress` | Disable the progress indicator. |

Output includes a summary panel, a category/size table, and the first `N` files
with their inclusion status.

### `tree`

Print only the directory tree. Sensitive and ignored paths may still appear in
the tree so the user can see they were considered; their contents are never
read.

```bash
python -m pussy tree .
python -m pussy tree . --ascii
python -m pussy tree . --no-hidden
```

| Option | Description |
| --- | --- |
| `--config PATH` | Explicit TOML configuration file. |
| `--exclude`, `-x GLOB` | Additional ignore glob(s), comma-separated. |
| `--hidden / --no-hidden` | Include or exclude hidden files and directories. |
| `--ascii` | Use ASCII connectors (`|--`, `` `-- ``) instead of Unicode. |
| `--no-progress` | Disable the progress indicator. |

### `info`

Show project intelligence without generating a context document.

```bash
python -m pussy info .
python -m pussy info . --no-git
```

| Option | Description |
| --- | --- |
| `--config PATH` | Explicit TOML configuration file. |
| `--exclude`, `-x GLOB` | Additional ignore glob(s), comma-separated. |
| `--no-git` | Skip Git analysis. |
| `--no-progress` | Disable the progress indicator. |

The output includes a project summary, a technology table (name, kind and
evidence), a dependency count by scope, and Git branch/commit/status when the
path is a repository.

### `generate`

Generate the complete context document.

```bash
# Markdown to stdout
python -m pussy generate .

# JSON to stdout
python -m pussy generate . --format json

# Clipboard, with stdout fallback if no clipboard tool is available
python -m pussy generate . --copy

# Explicit file; refuses to overwrite without --force
python -m pussy generate . -o context.md
python -m pussy generate . -o context.md --force

# Auto-named file in the project root
python -m pussy generate . --save
```

| Option | Description |
| --- | --- |
| `--config PATH` | Explicit TOML configuration file. |
| `--mode`, `-m MODE` | `overview`, `context` (default) or `full`. |
| `--format`, `-f FORMAT` | `markdown` (default) or `json`. |
| `--output`, `-o PATH` | Write to a file. A directory or trailing slash auto-names the file. No suffix adds `.md`/`.json`. |
| `--save` | Auto-name a file in the project root: `pussy-context-YYYYMMDD-HHMMSS.md`. |
| `--force` | Allow replacing an existing output file. |
| `--copy`, `-c` | Copy the rendered document to the clipboard. |
| `--include-ext LIST` | Only include these extensions (`py,ts`). Repeatable. |
| `--exclude-ext LIST` | Exclude these extensions (`lock,map`). Repeatable. |
| `--exclude`, `-x GLOB` | Additional ignore glob(s), comma-separated. Repeatable. |
| `--include`, `-i GLOB` | Explicit include glob(s) that override ignore rules. |
| `--max-size SIZE` | Maximum individual file size. |
| `--max-total-size SIZE` | Maximum total content size. |
| `--tree-only` | Emit tree, report and statistics only. |
| `--code-only` | Emit file sections, report and statistics only. |
| `--git / --no-git` | Include or skip Git information (default: included). |
| `--git-diff` | Include the working-tree diff (implies `--git`). |
| `--model NAME` | Model name used to select a `tiktoken` encoding. |
| `--tokenizer MODE` | `auto` (default), `approximate` or `tiktoken`. |
| `--hidden / --no-hidden` | Include or exclude hidden files and directories. |
| `--follow-symlinks` | Follow symlinks that stay inside the project root. |
| `--no-progress` | Disable the progress indicator. |
| `--quiet`, `-q` | Suppress status messages (warnings are still reported). |

`--tree-only` and `--code-only` are mutually exclusive.

### `init`

Create a `.pussyignore` file using a documented starter template.

```bash
python -m pussy init .
python -m pussy init . --with-config
python -m pussy init . --force
```

| Option | Description |
| --- | --- |
| `--with-config` | Also create `pussy.toml`. |
| `--force` | Overwrite existing files. Without it, existing files are skipped. |

### `config`

Show the fully resolved configuration, or create the user-level config file.

```bash
python -m pussy config .
python -m pussy config . --json
python -m pussy config . --init
python -m pussy config . --init --force
```

| Option | Description |
| --- | --- |
| `--config PATH` | Explicit TOML configuration file. |
| `--init` | Create the user config file. |
| `--force` | Overwrite an existing user config. |
| `--json` | Print the resolved configuration as JSON instead of a table. |

`--init` exits with code `3` if the user config already exists and `--force` is
not supplied.

## Modes and section order

### `context` (default)

Reads text files in the source, configuration, documentation, database, tests
and infrastructure categories. Generated and unknown files are excluded.

1. Project Overview
2. Project Metadata
3. Directory Structure
4. Dependencies
5. Configuration Files
6. Source Code
7. Documentation
8. Database
9. Tests
10. Infrastructure Files
11. Other Files
12. Git Information
13. File Processing Report
14. Context Statistics

Empty content sections are still rendered (with "No files in this category.") so
the document structure is predictable.

### `overview`

Reads no file contents. Emits overview, metadata, tree, dependencies, Git,
report and statistics. Use this when you only need architecture.

### `full`

Same as `context`, but also reads generated and unknown text files. Useful for
small projects where every text artifact matters.

### `--tree-only`

Skips content, overview, metadata, dependencies and Git. Emits:

1. Directory Structure
2. File Processing Report
3. Context Statistics

### `--code-only`

Skips overview, metadata, tree, dependencies and Git. Emits file sections,
report and statistics. Empty categories are omitted in this mode.

## Output behavior

- Without `--output` or `--save`, the rendered document is written to stdout.
- With `--copy`, nothing is written to stdout on success. If every clipboard
  utility fails, Pussy reports the failure on stderr and falls back to stdout.
- `--save` and `--output` auto-name conflicting files (for `--save`) or require
  `--force` (for explicit output paths). Files are written atomically through a
  temporary file and replacement.
- The current output file is excluded from its own scan. Previous
  `pussy-context-*.md` and `pussy-context-*.json` exports are ignored by default.
- Status lines such as `Wrote ...` and `Copied to clipboard ...` go to stderr.
  Use `--quiet` to suppress them.

### Clipboard commands

Pussy tries platform-appropriate utilities in order:

| Platform | Order |
| --- | --- |
| Windows | `clip`, then PowerShell `Set-Clipboard` |
| macOS | `pbcopy` |
| Linux / Wayland | `wl-copy`, `xclip`, `xsel` |
| Linux / X11 | `xclip`, `xsel`, `wl-copy` |

Failure of one utility falls through to the next. All failures produce a
combined diagnostic and a stdout fallback.

## JSON output

`--format json` returns a versioned document (`schema_version: 1`):

```json
{
  "schema_version": 1,
  "generator": { "name": "pussy-cli", "version": "1.0.0" },
  "generated_at": "2026-01-01T00:00:00+00:00",
  "mode": "context",
  "tree_only": false,
  "code_only": false,
  "project": { "...": "overview, technologies, categories, warnings" },
  "tree": "project/\n...",
  "dependencies": { "files_analyzed": [], "warnings": [], "items": [] },
  "git": { "...": "branch, commit, changes, optional diff" },
  "files": [
    {
      "path": "src/main.py",
      "category": "source_code",
      "language": "Python",
      "size": 123,
      "included": true,
      "is_binary": false,
      "is_sensitive": false,
      "read_status": "read",
      "exclusion_reason": null,
      "content": "...",
      "metadata": {}
    }
  ],
  "report": { "included_files": 1, "excluded_files": 0, "warnings": [] },
  "stats": { "estimated_tokens": 1234, "...": "..." }
}
```

Excluded files remain in `files` with `included: false`, `content: null` and an
`exclusion_reason`. This makes exclusions auditable. Git is `null` when
`--no-git` is used.

## Token estimation

- `auto` uses `tiktoken` when it is installed **and** the model name is known;
  otherwise it uses a labelled `characters / 4` approximation.
- `approximate` always uses `characters / 4`.
- `tiktoken` requests exact counting but falls back to the labelled
  approximation if the package or model encoding is unavailable.
- Estimates cover the tree plus file contents; Markdown formatting overhead is
  excluded. `stats.approximate` tells consumers which method was used.
- No tokenizer download or network request is performed.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Success |
| `1` | Runtime error |
| `2` | Usage or configuration error |
| `3` | Export conflict |

## Examples

```bash
# Audit what would be sent before generating
python -m pussy scan . --limit 50

# Architecture-only prompt for a large monorepo
python -m pussy generate . --mode overview --copy

# Small project, include every text artifact
python -m pussy generate . --mode full

# Backend only
python -m pussy generate . --include-ext py,go,sql,yaml,toml

# Skip generated frontend bundles and common build artifacts
python -m pussy generate . --exclude "*.min.js" --exclude-ext map,lock

# Include an ignored fixture on purpose
python -m pussy generate . --exclude "fixtures/**" --include "fixtures/sample.json"

# CI artifact, fail if the context already exists
python -m pussy generate . -o pussy-context.md --quiet

# Machine-readable inventory without reading content
python -m pussy generate . --mode overview --format json
```

## Troubleshooting

- **"path does not exist" / "not a directory"** — pass a directory; files are
  rejected intentionally.
- **"output file already exists"** — rerun with `--force`, or choose another
  path. Pussy never overwrites silently.
- **Clipboard copy failed** — install `wl-clipboard`, `xclip`, or `xsel` on
  Linux, `pbcopy` on macOS, or use `clip` on Windows. The document is printed to
  stdout as a fallback.
- **Git section says "Not a Git repository"** — expected outside a repository;
  this is not an error. Use `--no-git` to omit the section.
- **A file is present in the tree but has no content** — it is sensitive,
  ignored, binary, or over a size limit. The File Processing Report states why.
