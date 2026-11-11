# Configuration reference

Pussy works without configuration. Everything below is optional and exists to
make repeated runs reproducible across a team or CI environment.

## Where configuration is read from

Pussy merges configuration from these sources, lowest to highest precedence:

1. **Built-in defaults** (`pussy/config/defaults.py`).
2. **User config**
   - Linux/macOS: `$XDG_CONFIG_HOME/pussy/config.toml`, falling back to
     `~/.config/pussy/config.toml`.
   - Windows: `%APPDATA%\pussy\config.toml`.
3. **Project config** — `pussy.toml` in the scanned project root.
4. **Explicit config** — the file passed with `--config PATH`.
5. **Command-line flags** — for example `--mode`, `--format`, `--max-size`,
   `--exclude`, `--include-ext`.

Later files override earlier ones key by key. Lists such as `ignore.patterns`
are appended across sources; extension filters are unioned. The loaded files are
shown by `python -m pussy config`.

Create the initial files with:

```bash
python -m pussy init .                 # .pussyignore only
python -m pussy init . --with-config   # .pussyignore + pussy.toml
python -m pussy config . --init        # user-level config
```

## Full example

```toml
# pussy.toml

[scan]
include_hidden = true
follow_symlinks = false
max_file_size = "1MB"
max_total_size = "64MB"

[ignore]
use_defaults = true
patterns = [
  "generated/",
  "*.snap",
  "fixtures/large/",
]

[include]
extensions = ["py", "pyi", "ts", "tsx", "sql", "toml", "yaml", "md"]
patterns = ["vendor/acme/public_api.py"]
exclude_extensions = ["lock", "map"]

[output]
format = "markdown"    # markdown | json
mode = "context"       # overview | context | full

[git]
enabled = true
include_diff = false
max_diff_chars = "200KB"

[tokens]
tokenizer = "auto"     # auto | approximate | tiktoken
model = ""             # e.g. "gpt-4o"; empty means generic approximation
```

## `[scan]`

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `include_hidden` | boolean | `true` | Traverse hidden files and directories (subject to ignore rules). |
| `follow_symlinks` | boolean | `false` | Follow symlinks only when they resolve inside the project root, with loop detection. |
| `max_file_size` | size | `1MB` | Skip individual files larger than this. |
| `max_total_size` | size | `64MB` | Stop reading content after this cumulative total. |

Size values accept an integer byte count or a unit suffix: `B`, `KB`/`KiB`,
`MB`/`MiB`, `GB`/`GiB`. They are binary units (`1MB = 1,048,576` bytes).

## `[ignore]`

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `use_defaults` | boolean | `true` | Apply the built-in ignore list for dependencies, build output, caches, lockfiles and previous exports. |
| `patterns` | list of strings | `[]` | Extra gitignore-style rules, appended after `.pussyignore`. |

### Ignore sources and precedence

Rules are evaluated in this order; the **last matching rule wins**:

1. built-in defaults (unless `use_defaults = false`);
2. `.pussyignore` in the project root;
3. `[ignore].patterns` from TOML config files;
4. `--exclude` patterns from the command line.

This matches Git's "last match wins" behavior, so a later `!pattern` re-includes
a path. Explicit `--include`/`[include].patterns` entries act as overrides for
ignored files, but never for sensitive files.

### `.pussyignore` syntax

`.pussyignore` uses gitignore-style rules:

| Pattern | Meaning |
| --- | --- |
| `node_modules/` | Ignore a directory at any depth. |
| `*.log` | Ignore matching basenames at any depth. |
| `/build/` | Anchored to the project root. |
| `src/generated/**` | `**` crosses directory boundaries. |
| `docs/**/*.tmp` | Glob within nested directories. |
| `!important/` | Re-include a previously ignored path (must come later). |
| `\#file` | Match a literal leading `#`. |
| `!` | Escape a literal leading `!` (write `\!`). |

Comments start with `#`; blank lines are ignored. Only the project-root
`.pussyignore` is read. Rules apply to project-relative POSIX paths regardless
of the machine's path separator.

Ignored directories are pruned before descent, so a `node_modules/` rule avoids
walking the tree entirely. Include patterns can still descend into an ignored
directory when they are path-prefixed (for example
`vendor/acme/public_api.py`).

## `[include]`

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `extensions` | list of strings | `[]` | Whitelist of extensions. Empty means all supported text files. Values may include or omit the leading dot. |
| `exclude_extensions` | list of strings | `[]` | Extensions to remove from the selection. |
| `patterns` | list of strings | `[]` | Explicit include globs that override ignore rules. |

Filters are applied after classification. If a file is excluded by
`include.extensions`, its `exclusion_reason` records why. Multiple extensions
can be comma-separated in a single list item (`["py,ts"]`) as well as separate
items.

## `[output]`

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `format` | `markdown` or `json` | `markdown` | Output format. |
| `mode` | `overview`, `context` or `full` | `context` | Content selection mode. |

Invalid values fail fast with exit code `2` and a message listing valid choices.

## `[git]`

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `enabled` | boolean | `true` | Run Git analysis. |
| `include_diff` | boolean | `false` | Include the working-tree diff in the output. |
| `max_diff_chars` | size | `200KB` | Truncate the diff at this many characters. |

Git analysis is strictly read-only. Commands run with prompts disabled and a
timeout, `GIT_DIR`/`GIT_WORK_TREE` are removed from the environment, credential
URLs are redacted, and diff sections for sensitive paths are removed.

## `[tokens]`

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `tokenizer` | `auto`, `approximate` or `tiktoken` | `auto` | Token counting strategy. |
| `model` | string | `""` | Model name for `tiktoken` encoding selection. |

- `auto` uses `tiktoken` when the optional dependency is installed and the model
  is recognized; otherwise it uses `characters / 4`.
- `approximate` always uses `characters / 4`.
- `tiktoken` requests exact counting but falls back to the labelled
  approximation if unavailable.
- No network access is ever required or attempted.

Install exact counting with:

```bash
pip install tiktoken
```

## Sensitive files

Sensitive detection is independent of configuration and ignore rules. It cannot
be disabled or re-included from the command line, because a false negative would
leak credentials.

Blocked by name or suffix include:

- `.env` and variants such as `.env.local`, `.env.production`;
- `.envrc`, `.npmrc`, `.pypirc`, `.netrc`, `.htpasswd`;
- `credentials.json`, `secrets.json`, `secret.json`;
- private keys: `id_rsa`, `id_dsa`, `id_ecdsa`, `id_ed25519`, `*.pem`,
  `*.key`, `*.p12`, `*.pfx`, `*.jks`, `*.keystore`, `*.kdbx`, `*.ppk`,
  `*.asc.gpg`;
- anything below `.ssh/`, `.gnupg/`, `.aws/`, `.azure/` or `.config/gcloud/`.

Allowlisted placeholders whose contents are safe to include:

- `.env.example`, `.env.sample`, `.env.template`, `.env.dist`
- `credentials.example.json`, `secrets.example.json`

Sensitive paths still appear in the tree and processing report with an
exclusion reason. The reader refuses to open them, so their content never enters
memory or output.

## Default ignore list

The built-in list covers:

- VCS/editor metadata: `.git/`, `.hg/`, `.svn/`, `.idea/`, `.vscode/`, `.vs/`
- dependencies and virtualenvs: `node_modules/`, `vendor/`, `venv/`, `.venv/`,
  `site-packages/`, `Pods/`, `.env/`
- caches: `__pycache__/`, `.mypy_cache/`, `.pytest_cache/`, `.ruff_cache/`,
  `.tox/`, `.nox/`, `.hypothesis/`
- build output: `dist/`, `build/`, `out/`, `target/`, `coverage/`, `.next/`,
  `.nuxt/`, `.output/`, `.svelte-kit/`, `.angular/`, `.parcel-cache/`,
  `.turbo/`, `.cache/`
- logs and OS files: `*.log`, `.DS_Store`, `Thumbs.db`
- lockfiles: `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `Cargo.lock`,
  `poetry.lock`, `uv.lock`, `composer.lock`, `Gemfile.lock`, `Pipfile.lock`
- previous exports: `pussy-context-*.md`, `pussy-context-*.json`

Set `ignore.use_defaults = false` only if you really want the raw tree.

## Binary handling

These are never decoded as text:

- executables and libraries (`.exe`, `.dll`, `.so`, `.dylib`, `.class`,
  `.jar`, `.wasm`, `.o`, `.pyc`, ...);
- archives and documents (`.zip`, `.tar`, `.gz`, `.7z`, `.pdf`, `.docx`,
  `.xlsx`, `.pptx`, ...);
- databases and serialized data (`.sqlite`, `.db`, `.parquet`, `.onnx`, `.pt`,
  `.safetensors`, `.npy`, ...);
- images, fonts, audio and video (`.png`, `.jpg`, `.gif`, `.webp`, `.ttf`,
  `.woff2`, `.mp3`, `.mp4`, ...). `.svg` is excluded from this list because it
  is XML text.

Files with unknown extensions are also inspected for null bytes and skipped when
binary content is detected. Binary files may be listed in the tree and report,
but `content` is always `null` in JSON.

## Reproducibility tips

- Commit `pussy.toml` and `.pussyignore` so every contributor generates the same
  selection.
- Prefer explicit `[include].extensions` in CI to prevent accidental large
  additions.
- Keep `max_total_size` bounded in automated jobs.
- Use `--no-progress` and `--quiet` in scripts.
- Use `--format json` when another tool needs stable, machine-readable facts.
