# Pussy

**Turn any software project into a clean, structured context document for LLMs.**

Repository: <https://github.com/ayu-dash/pussy>

Pussy scans a repository, detects its technologies, parses dependency manifests,
reads Git metadata, and renders everything as Markdown or JSON — with strict
security rules that keep secrets and binary files out of the output.

```bash
python -m pussy generate . --copy
```

The result is a single document containing the project overview, directory tree,
detected stack, dependencies, Git state, file contents, exclusions, and token
statistics — ready to paste into a chat, an agent, or a local model.

---

## Highlights

- **Clone-and-run** — no build, package install, or console script; run
  `python -m pussy` from the checkout.
- **Project intelligence** — languages, frameworks, package managers, entry
  points, configuration files, dependencies and Git state.
- **Three context modes** — `overview`, `context` (default) and `full`.
- **Markdown and JSON** — human-friendly reports or a stable, versioned schema
  for tooling.
- **Security by construction** — sensitive files are blocked independently of
  ignore rules, and content is never read for them.
- **Binary-aware** — images, archives, executables, fonts and media are skipped
  before any bytes are decoded.
- **Token estimates** — optional `tiktoken` support with a clearly labelled
  approximation fallback (no network calls).
- **Cross-platform clipboard** — `wl-copy`, `xclip`, `xsel`, `pbcopy` or `clip`,
  with a safe stdout fallback.
- **Deterministic output** — sorted trees and file sections make diffs stable.
- **No silent overwrites** — exports are atomic and require `--force` to replace
  an existing file.

This repository is used directly from a clone. It is **not** published as a
package and does not need to be installed.

## Requirements

- Python **3.11+**
- Git is optional; it is only used read-only when available.

## Setup

Clone the repository and install the runtime dependencies:

```bash
git clone https://github.com/ayu-dash/pussy.git pussy
cd pussy

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Optional exact token counting:

```bash
pip install tiktoken
```

For development and tests:

```bash
pip install -r requirements-dev.txt
```

Run the CLI from the repository root:

```bash
python -m pussy --version
python -m pussy --help
```

There is no console-script installation step. `python -m pussy` always runs the
code in this checkout.

## Quick start

```bash
# Inspect the project without generating a context
python -m pussy scan .
python -m pussy tree .
python -m pussy info .

# Generate Markdown to stdout
python -m pussy generate .

# Copy the generated context to the clipboard
python -m pussy generate . --copy

# Write a Markdown file (auto-named in the project root)
python -m pussy generate . --save

# Write to an explicit path, overwriting only with --force
python -m pussy generate . --output context.md
python -m pussy generate . --output context.md --force

# Machine-readable output
python -m pussy generate . --format json --output context.json

# A short overview with no file contents
python -m pussy generate . --mode overview

# Only the tree and processing report
python -m pussy generate . --tree-only

# Only file contents, without overview/tree/Git sections
python -m pussy generate . --code-only

# Restrict or exclude extensions
python -m pussy generate . --include-ext py,ts
python -m pussy generate . --exclude-ext lock,map

# Skip Git entirely
python -m pussy generate . --no-git
```

## Commands

| Command | Purpose |
| --- | --- |
| `python -m pussy scan [path]` | Scan metadata and print category/file statistics. |
| `python -m pussy tree [path]` | Print only the directory tree. |
| `python -m pussy info [path]` | Show detected technologies, dependencies and Git status. |
| `python -m pussy generate [path]` | Generate the full Markdown or JSON context. |
| `python -m pussy init [path]` | Create `.pussyignore` (and optionally `pussy.toml`). |
| `python -m pussy config [path]` | Show resolved configuration or create a user config. |

Every command accepts a project path; `.` is the default.

### Modes

| Mode | Includes | Reads file content |
| --- | --- | --- |
| `overview` | Overview, metadata, tree, dependencies, Git, report, stats | No |
| `context` (default) | Overview, metadata, tree, dependencies, Git, source/config/docs/tests/infrastructure/database content, report, stats | Yes |
| `full` | Same as `context` plus generated and unknown text files | Yes |

`--tree-only` emits the tree, report and statistics only. `--code-only` emits
file sections, report and statistics only. The two flags cannot be combined.

## Configuration

Configuration is optional. Pussy reads, in increasing precedence:

1. built-in defaults;
2. the user config (`$XDG_CONFIG_HOME/pussy/config.toml`, or
   `%APPDATA%\pussy\config.toml` on Windows);
3. `pussy.toml` in the project root;
4. an explicit `--config` file;
5. command-line flags.

```toml
[scan]
include_hidden = true
follow_symlinks = false
max_file_size = "1MB"
max_total_size = "64MB"

[ignore]
use_defaults = true
patterns = ["generated/", "*.snap"]

[include]
extensions = ["py", "ts"]
patterns = ["vendor/acme/lib.py"]
exclude_extensions = ["lock", "map"]

[output]
format = "markdown"
mode = "context"

[git]
enabled = true
include_diff = false

[tokens]
tokenizer = "auto"
model = ""
```

Create a starting point automatically:

```bash
python -m pussy init . --with-config
python -m pussy config . --init
```

See [docs/configuration.md](docs/configuration.md) for every key, the ignore
syntax, and precedence rules.

## Security model

Pussy is designed for the common case of pasting a codebase into an external
model, where an accidental secret leak is the highest-risk failure.

- Sensitive names and suffixes are detected **before** ignore rules and cannot
  be overridden by includes. Examples: `.env`, `.npmrc`, `.netrc`, private keys,
  credential files, and anything under `.ssh/`, `.gnupg/`, `.aws/`.
- `.env.example`, `.env.sample`, `.env.template` and `.env.dist` are allowlisted.
- The reader is the only stage that opens files, and it refuses sensitive or
  excluded entries.
- Binary content is detected both by extension and by null-byte inspection.
- Git is queried read-only with prompts disabled; credential-bearing URLs in Git
  output are redacted, and diffs for sensitive paths are dropped.
- No network requests and no API keys are used anywhere.
- Symlinks are skipped by default and only followed when they resolve inside the
  project root.
- Exports are written atomically and never overwrite an existing file without
  `--force`.

Sensitive paths still appear in the tree and processing report so the user can
see that they were deliberately excluded — only their contents are blocked.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Success |
| `1` | Runtime error (unreadable export, unexpected failure) |
| `2` | Usage or configuration error (invalid path, mode, format, tokenizer, size) |
| `3` | Export conflict (target exists without `--force`) |

## Repository layout

```text
pussy/
├── pussy/                  application code (run as `python -m pussy`)
│   ├── analyzers/          dependency, Git and project-info analysis
│   ├── config/             defaults, TOML loader and config model
│   ├── core/               scanner, reader, detector, builder, pipeline
│   ├── filters/            ignore, sensitive, extension and size policies
│   ├── formatters/         Markdown, JSON and tree renderers
│   ├── integrations/       clipboard and export handling
│   ├── models/             dataclasses and enums
│   └── utils/              encoding, filesystem and size helpers
├── tests/                  pytest suite (isolated temporary projects)
├── docs/                   usage, configuration and architecture docs
├── requirements.txt        runtime dependencies
├── requirements-dev.txt    test and lint dependencies
├── pyproject.toml          pytest, coverage, Ruff and MyPy settings only
├── README.md
├── LICENSE
├── .pussyignore            ignore rules used when scanning this repo
├── .pussyignore.example    starter template for other projects
└── .gitignore
```

Local virtual environments, caches, coverage output and generated context files
are ignored by Git and are not part of the source tree. `pyproject.toml` contains
no build metadata: it exists only to configure development tools.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

pytest
ruff check pussy tests
ruff format --check pussy tests
mypy
```

The suite covers scanning, ignore matching, sensitive filtering, reading,
classification, detection, dependency parsing, Git analysis, token estimation,
context building, formatting, clipboard behavior and the full CLI.

## Documentation

- [Usage guide](docs/usage.md)
- [Configuration reference](docs/configuration.md)
- [Architecture](docs/architecture.md)

## License

MIT — see [LICENSE](LICENSE).
