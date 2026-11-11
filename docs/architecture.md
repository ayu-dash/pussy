# Architecture

Pussy is a small, staged pipeline. Each stage has one responsibility, accepts
plain Python data, and can be tested without the CLI or a terminal.

## Principles

1. **Metadata before content.** Scanning never opens files. Content is read only
   after ignore, include, extension and security decisions are final.
2. **Security is independent of policy.** Sensitive detection is not an ignore
   rule and cannot be overridden by configuration.
3. **No invented facts.** Detection and dependency parsing report only what the
   files prove; parse failures become warnings.
4. **Read-only integration.** Git is queried with read-only commands; package
   managers are never executed; no network calls are made.
5. **Deterministic output.** Paths, trees, dependencies and sections are sorted
   so repeated runs produce stable documents.
6. **Fail clearly.** Expected failures raise typed errors with stable exit
   codes; per-file problems become recorded statuses instead of aborting a run.

## Project layout

The repository root is the import root. There is no build or installation step:
`python -m pussy` runs the code directly from a clone.

```text
pussy/
├── __init__.py            version (single source of truth)
├── __main__.py            python -m pussy
├── cli.py                 Typer commands, option wiring, console output
├── errors.py              typed errors and exit codes
├── analyzers/
│   ├── dependency.py      manifest parsers (pip, npm, cargo, go, maven, ...)
│   ├── git_analyzer.py    read-only Git status/commit/diff
│   └── project_info.py    fact aggregation into ProjectInfo
├── config/
│   ├── defaults.py        ignore rules, sensitive names, templates
│   ├── loader.py          TOML discovery, validation and merging
│   └── models.py          PussyConfig and validation
├── core/
│   ├── classifier.py      category and language classification
│   ├── context_builder.py mode policy, reading, tree and stats
│   ├── detector.py        extensible technology registry
│   ├── pipeline.py        scan/generate orchestration
│   ├── reader.py          the only content-reading stage
│   ├── scanner.py         metadata-only directory walker
│   └── token_estimator.py optional tiktoken + approximation
├── filters/
│   ├── extensions.py      extension tables and language mappings
│   ├── ignore.py          gitignore-style rule engine
│   ├── sensitive.py       independent secret-name policy
│   └── size_limit.py      size policy helpers
├── formatters/
│   ├── json.py            versioned JSON document
│   ├── markdown.py        numbered Markdown report
│   └── tree.py            deterministic tree renderer
├── integrations/
│   ├── clipboard.py       cross-platform clipboard with fallbacks
│   └── exporter.py        path resolution and atomic writes
├── models/                frozen dataclasses and enums
└── utils/                 encoding, filesystem and size helpers
```

## Pipeline

```text
CLI arguments
    │
    ▼
load_config() ──► PussyConfig (defaults + user + project + explicit + flags)
    │
    ▼
build_ignore_manager()
    │  defaults → .pussyignore → config patterns → CLI patterns
    ▼
Scanner.scan()            metadata only; prunes ignored directories
    │
    ▼
classify_entries()        category + language from names/paths
    │
    ├──► ProjectDetector.detect()       root manifests, capped reads
    ├──► DependencyAnalyzer.analyze()    manifest parsers
    └──► GitAnalyzer.analyze()           read-only subprocess calls
    │
    ▼
ContextBuilder.build()
    │  extension filters → FileReader (mode-dependent)
    │  → mode policy → ProjectInfo → tree → token stats
    ▼
MarkdownFormatter / JsonFormatter
    │
    ▼
ExportManager.write() or ClipboardManager.copy() or stdout
```

`pipeline.scan_project()` performs the metadata and analysis stages.
`pipeline.generate_context()` adds the content and formatting inputs. The CLI is
a thin layer over these two functions, so every command shares identical
behavior.

## Stage details

### Configuration (`config/`)

`load_config()` merges user config, project `pussy.toml` and an explicit
`--config` file, then the CLI applies flags. `PussyConfig.validate()` rejects
unknown modes, formats and tokenizers before any expensive work starts. Sizes
are parsed by `utils/size.py` into bytes using binary units.

`build_ignore_manager()` assembles rules in documented precedence order. The
engine compiles gitignore globs and evaluates rules last-match-wins. Anchored
patterns, directory-only rules, `**`, character classes, escapes and negations
are supported.

### Scanning (`core/scanner.py`)

The scanner walks with `os.scandir()` for speed and stores only metadata:
path, relative path, size and mtime. It:

- prunes ignored directories before descending;
- applies explicit include overrides;
- detects sensitive paths and marks them excluded;
- skips symlinks unless `--follow-symlinks` is set, then only follows links that
  resolve inside the root and detects loops by device/inode;
- excludes the current output path from its own scan;
- records unreadable directories and special files as warnings.

The result is a `ScanResult` with `files`, `directories`,
`skipped_directories` and `warnings`.

### Classification (`core/classifier.py`)

Classification is name/path-based and does not read content:

- functional categories: source, configuration, documentation, database, tests,
  infrastructure, assets, generated, dependencies, binary, sensitive, unknown;
- language lookup from extension, special filename or shebang (the reader fills
  in a missing language later);
- lockfiles, minified bundles, generated markers and dependency directories are
  recognised explicitly.

### Detection and dependency analysis (`analyzers/`, `core/detector.py`)

The detector is a registry of `TechnologyRule` objects. Each rule receives a
read-only `DetectionContext` with root names and capped manifest contents. Rules
return evidence strings, never bare booleans, so the report can explain *why* a
technology was detected. Built-in rules cover Python frameworks, Node
frameworks, PHP frameworks, Rust, Go, Ruby, Java/Kotlin, .NET, mobile and
infrastructure tooling. New rules can be registered without modifying the engine.

`DependencyAnalyzer` parses known manifests (`pyproject.toml`, requirements
files, `package.json`, `Cargo.toml`, `go.mod`, `pom.xml`, Gradle files,
`composer.json`, `Gemfile`, `pubspec.yaml`). It groups dependencies
by scope and records parse warnings instead of failing.

### Content reading (`core/reader.py`)

The reader is the only stage that opens files for the document. It refuses:

- entries that are not included;
- sensitive entries;
- known binary extensions;
- files above `max_file_size`;
- files that would exceed `max_total_size`.

It reads `limit + 1` bytes to detect oversize files without loading them fully,
checks for binary content (null bytes/control-character ratio), decodes with
encoding detection, normalises newlines, counts lines and records the encoding.
Every failure becomes `ReadStatus.ERROR` or `SKIPPED` on that entry.

`overview` and `--tree-only` never call the reader, so they read no content at
all.

### Context construction (`core/context_builder.py`)

The builder applies extension include/exclude filters, reads content when the
mode requires it, then enforces the mode's category policy:

| Mode | Allowed categories |
| --- | --- |
| `overview` | none (no content) |
| `context` | configuration, source, documentation, database, tests, infrastructure |
| `full` | the above plus generated and unknown |

It creates `ProjectInfo`, renders the tree, and computes token statistics over
the tree plus included content. Statistics clearly label the estimation method.

### Formatting (`formatters/`)

- **Markdown** is a numbered document with overview, metadata, tree,
  dependencies, file sections, Git, processing report and statistics. Code
  fences automatically become longer than any backtick run in the file, so
  embedded Markdown cannot break the document.
- **JSON** is a stable `schema_version: 1` document containing the project,
  tree, dependencies, Git, all discovered files (with inclusion status and
  reasons), report and stats.
- **Tree** renders directories before files, sorted case-insensitively, with
  Unicode or ASCII connectors.

### Export and clipboard (`integrations/`)

`ExportManager` resolves output paths, adds the correct extension, auto-names
`--save` files, and writes atomically through a temporary file. Existing files
are never replaced without `--force`.

`ClipboardManager` tries platform-specific utilities in order and reports the
combined failure rather than pretending success. The CLI falls back to stdout
when copy fails.

## Security model

The threat model is accidental disclosure when a codebase is pasted into an
external model. The guarantees are:

| Invariant | Enforcement |
| --- | --- |
| Sensitive content is never read | `Scanner` marks it; `FileReader` refuses it. |
| Sensitive detection is not policy | `filters/sensitive.py` is independent of ignore/include. |
| Includes cannot reveal secrets | Include override is checked only after the sensitive flag. |
| Binary data is never emitted as text | Extension checks plus content inspection. |
| The output file does not include itself | `exclude_paths` is checked before adding an entry. |
| Git cannot prompt or modify | `GIT_TERMINAL_PROMPT=0`, env sanitisation, read-only commands, timeout. |
| Git credentials do not leak | URL credential redaction; sensitive diff sections dropped. |
| Symlinks cannot escape | Target must resolve inside the project root. |
| No silent overwrites | Atomic writes require `--force` to replace. |
| No network or API keys | No HTTP client or provider SDK is imported. |

Sensitive *paths* are still visible in the tree and report; this is deliberate,
so users can audit exclusions. Only contents are blocked.

## Error handling

`errors.py` defines the exit-code contract:

| Exception | Exit code |
| --- | --- |
| `ConfigError`, `ProjectError` | `2` |
| `ExportConflictError` | `3` |
| Other `PussyError` (e.g. `ExportError`) | `1` |
| Unexpected exception | `1` |

The CLI's `_handle_errors` decorator converts these into one-line stderr
messages. Git problems are never fatal: they become `GitInfo.error` and the
document still renders. Per-file read problems are recorded on the entry and
reported in the File Processing Report.

## Determinism and performance

- Directory entries and file sections are sorted with `casefold`.
- In-memory caches (`DetectionContext`) avoid repeated manifest reads.
- Ignored directories are pruned, which keeps scans of large
  `node_modules`/`vendor` trees cheap.
- File reads are capped individually and cumulatively.
- `tiktoken` is imported lazily; the tool works without the optional dependency.
- No global mutable state exists outside the CLI console objects.

## Testing

The suite lives in `tests/` and uses only temporary directories:

| Area | Test modules |
| --- | --- |
| Scanner and symlinks | `test_scanner.py` |
| Ignore semantics | `test_ignore.py` |
| Sensitive policy | `test_reader.py`, `test_context_builder.py` |
| Classification and detection | `test_classifier.py`, `test_detector.py` |
| Dependency parsers | `test_dependency.py` |
| Git parsing | `test_git_analyzer.py` |
| Token estimation | `test_token_estimator.py` |
| Builder and modes | `test_context_builder.py` |
| Markdown/JSON/tree | `test_formatter.py` |
| Clipboard | `test_clipboard.py` |
| Configuration | `test_config.py` |
| CLI end-to-end | `test_cli.py` |

Run the quality gates with:

```bash
pytest
ruff check src tests
ruff format --check src tests
mypy src
```

Tests never scan the repository itself; every test that needs a project creates
an isolated temporary directory via pytest's `tmp_path` fixture.

## Extending

- **New technology:** register a `TechnologyRule` with a detector function that
  returns an evidence string.
- **New dependency manifest:** add a parser in `analyzers/dependency.py` and
  dispatch it by filename.
- **New language/extension:** extend `LANGUAGE_BY_EXTENSION` and, if needed,
  `DOCUMENTATION_EXTENSIONS`/`BINARY_EXTENSIONS` in `filters/extensions.py`.
- **New output format:** implement a formatter with `render(bundle)` and wire it
  into `cli.generate`.
- **New ignore syntax:** extend `filters/ignore.py`; add tests for last-match
  semantics and directory pruning.
