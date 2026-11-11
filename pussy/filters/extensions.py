"""Extension and filename knowledge shared by classifiers and detectors."""

from __future__ import annotations

LANGUAGE_BY_EXTENSION: dict[str, str] = {
    ".py": "Python",
    ".pyi": "Python",
    ".pyw": "Python",
    ".php": "PHP",
    ".phtml": "PHP",
    ".js": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".mts": "TypeScript",
    ".cts": "TypeScript",
    ".java": "Java",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".go": "Go",
    ".rs": "Rust",
    ".c": "C",
    ".h": "C",
    ".cc": "C++",
    ".cpp": "C++",
    ".cxx": "C++",
    ".hpp": "C++",
    ".hh": "C++",
    ".cs": "C#",
    ".rb": "Ruby",
    ".rake": "Ruby",
    ".swift": "Swift",
    ".dart": "Dart",
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".scss": "CSS",
    ".sass": "CSS",
    ".less": "CSS",
    ".sql": "SQL",
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".fish": "Shell",
    ".ps1": "PowerShell",
    ".psm1": "PowerShell",
    ".lua": "Lua",
    ".ex": "Elixir",
    ".exs": "Elixir",
    ".erl": "Erlang",
    ".hrl": "Erlang",
    ".scala": "Scala",
    ".clj": "Clojure",
    ".cljs": "Clojure",
    ".hs": "Haskell",
    ".r": "R",
    ".R": "R",
    ".vue": "Vue",
    ".svelte": "Svelte",
    ".astro": "Astro",
    ".graphql": "GraphQL",
    ".gql": "GraphQL",
    ".proto": "Protocol Buffers",
    ".tf": "HCL",
    ".hcl": "HCL",
    ".dockerfile": "Dockerfile",
    ".mk": "Makefile",
    ".cmake": "CMake",
    ".gradle": "Groovy",
    ".groovy": "Groovy",
    ".pl": "Perl",
    ".pm": "Perl",
    ".asm": "Assembly",
    ".s": "Assembly",
    ".sol": "Solidity",
    ".zig": "Zig",
    ".nim": "Nim",
    ".jl": "Julia",
    ".vb": "Visual Basic",
    ".fs": "F#",
    ".fsx": "F#",
    ".md": "Markdown",
    ".mdx": "MDX",
    ".rst": "reStructuredText",
    ".adoc": "AsciiDoc",
    ".tex": "LaTeX",
    ".json": "JSON",
    ".jsonc": "JSON",
    ".json5": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".ini": "INI",
    ".cfg": "INI",
    ".conf": "Configuration",
    ".xml": "XML",
    ".plist": "XML",
    ".csv": "CSV",
    ".tsv": "TSV",
    ".env": "Dotenv",
    ".properties": "Properties",
    ".bat": "Batch",
    ".cmd": "Batch",
    ".gitignore": "Git Config",
    ".gitattributes": "Git Config",
}

LANGUAGE_BY_FILENAME: dict[str, str] = {
    "dockerfile": "Dockerfile",
    "containerfile": "Dockerfile",
    "makefile": "Makefile",
    "gnumakefile": "Makefile",
    "cmakelists.txt": "CMake",
    "gemfile": "Ruby",
    "rakefile": "Ruby",
    "vagrantfile": "Ruby",
    "berksfile": "Ruby",
    "podfile": "Ruby",
    "procfile": "Procfile",
    "jenkinsfile": "Groovy",
    "build.gradle": "Groovy",
    "build.gradle.kts": "Kotlin",
    "settings.gradle": "Groovy",
    "settings.gradle.kts": "Kotlin",
    "go.mod": "Go",
    "go.sum": "Go",
    "cargo.toml": "TOML",
    "cargo.lock": "TOML",
    "package.json": "JSON",
    "composer.json": "JSON",
    "tsconfig.json": "JSON",
    "pyproject.toml": "TOML",
    "requirements.txt": "Text",
    "pipfile": "TOML",
    "pom.xml": "XML",
    "artisan": "PHP",
    "next.config.js": "JavaScript",
    "next.config.mjs": "JavaScript",
    "nuxt.config.ts": "TypeScript",
    "nuxt.config.js": "JavaScript",
    "vue.config.js": "JavaScript",
    "svelte.config.js": "JavaScript",
    "angular.json": "JSON",
    "pubspec.yaml": "YAML",
    "nginx.conf": "Configuration",
    "caddyfile": "Configuration",
}

ASSET_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".bmp",
        ".ico",
        ".icns",
        ".webp",
        ".avif",
        ".tif",
        ".tiff",
        ".psd",
        ".svg",
        ".woff",
        ".woff2",
        ".ttf",
        ".otf",
        ".eot",
        ".mp3",
        ".wav",
        ".ogg",
        ".flac",
        ".aac",
        ".mp4",
        ".webm",
        ".mov",
        ".avi",
        ".mkv",
        ".m4v",
    }
)

BINARY_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".exe",
        ".dll",
        ".so",
        ".dylib",
        ".a",
        ".lib",
        ".bin",
        ".dat",
        ".class",
        ".jar",
        ".war",
        ".ear",
        ".pyc",
        ".pyo",
        ".o",
        ".obj",
        ".pdb",
        ".wasm",
        ".zip",
        ".tar",
        ".gz",
        ".tgz",
        ".bz2",
        ".xz",
        ".7z",
        ".rar",
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        ".sqlite",
        ".sqlite3",
        ".db",
        ".mdb",
        ".parquet",
        ".avro",
        ".onnx",
        ".pt",
        ".pth",
        ".safetensors",
        ".pkl",
        ".pickle",
        ".npy",
        ".npz",
        ".h5",
        ".hdf5",
        # Images, fonts and media are binary even though they are tracked as
        # assets. SVG is deliberately absent because it is a text format.
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".bmp",
        ".ico",
        ".icns",
        ".webp",
        ".avif",
        ".tif",
        ".tiff",
        ".psd",
        ".woff",
        ".woff2",
        ".ttf",
        ".otf",
        ".eot",
        ".mp3",
        ".wav",
        ".ogg",
        ".flac",
        ".aac",
        ".mp4",
        ".webm",
        ".mov",
        ".avi",
        ".mkv",
        ".m4v",
    }
)

GENERATED_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".pyc",
        ".pyo",
        ".class",
        ".o",
        ".obj",
        ".map",
        ".lock",
    }
)

DOCUMENTATION_EXTENSIONS: frozenset[str] = frozenset(
    {".md", ".mdx", ".rst", ".adoc", ".asciidoc", ".tex", ".txt"}
)

DATABASE_EXTENSIONS: frozenset[str] = frozenset(
    {".sql", ".sqlite", ".sqlite3", ".db", ".prisma", ".cql", ".psql"}
)

INFRASTRUCTURE_FILENAMES: frozenset[str] = frozenset(
    {
        "dockerfile",
        "containerfile",
        "docker-compose.yml",
        "docker-compose.yaml",
        "compose.yml",
        "compose.yaml",
        ".dockerignore",
        "makefile",
        "gnumakefile",
        "justfile",
        "procfile",
        "jenkinsfile",
        "vagrantfile",
        "caddyfile",
        "nginx.conf",
        "serverless.yml",
        "serverless.yaml",
        "vercel.json",
        "netlify.toml",
        "fly.toml",
        "render.yaml",
        "ansible.cfg",
    }
)

CONFIGURATION_FILENAMES: frozenset[str] = frozenset(
    {
        "package.json",
        "composer.json",
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "pipfile",
        "requirements.txt",
        "tsconfig.json",
        "jsconfig.json",
        "webpack.config.js",
        "vite.config.js",
        "vite.config.ts",
        "rollup.config.js",
        "babel.config.js",
        ".babelrc",
        ".eslintrc",
        ".eslintrc.js",
        ".eslintrc.json",
        "eslint.config.js",
        "prettier.config.js",
        ".prettierrc",
        ".editorconfig",
        ".gitignore",
        ".gitattributes",
        ".pussyignore",
        "pussy.toml",
        "phpunit.xml",
        "phpunit.xml.dist",
        "pytest.ini",
        "tox.ini",
        "mypy.ini",
        "ruff.toml",
        ".coveragerc",
        "cargo.toml",
        "go.mod",
        "pom.xml",
        "build.gradle",
        "build.gradle.kts",
        "settings.gradle",
        "gemfile",
        "angular.json",
        "nuxt.config.ts",
        "next.config.js",
        "next.config.mjs",
        "vite.config.mjs",
        "tailwind.config.js",
        "postcss.config.js",
        "nest-cli.json",
        "artisan",
        "manage.py",
        "pubspec.yaml",
    }
)

CONFIGURATION_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".toml",
        ".ini",
        ".cfg",
        ".conf",
        ".yaml",
        ".yml",
        ".json",
        ".jsonc",
        ".json5",
        ".xml",
        ".properties",
        ".env",
    }
)

TEST_DIRECTORY_NAMES: frozenset[str] = frozenset(
    {
        "test",
        "tests",
        "__tests__",
        "spec",
        "specs",
        "testdata",
        "test_data",
        "e2e",
        "cypress",
        "playwright",
    }
)

DEPENDENCY_DIRECTORY_NAMES: frozenset[str] = frozenset(
    {
        "node_modules",
        "vendor",
        "venv",
        ".venv",
        "site-packages",
        "bower_components",
        "pods",
        ".bundle",
    }
)


def extension_of(name: str) -> str:
    """Return the lowercase suffix, handling dotfiles such as ``.env``."""
    from pathlib import PurePosixPath

    path = PurePosixPath(name)
    if path.name.startswith(".") and path.suffix == "":
        return path.name.lower()
    return path.suffix.lower()


def language_for(name: str) -> str | None:
    """Infer a language/format from a filename."""
    lowered = name.lower()
    if lowered in LANGUAGE_BY_FILENAME:
        return LANGUAGE_BY_FILENAME[lowered]
    if lowered.startswith("dockerfile."):
        return "Dockerfile"
    if lowered.startswith("docker-compose"):
        return "YAML"
    if lowered.startswith("requirements") and lowered.endswith(".txt"):
        return "Text"
    return LANGUAGE_BY_EXTENSION.get(extension_of(name))


_SHEBANG_LANGUAGES: dict[str, str] = {
    "python": "Python",
    "python3": "Python",
    "bash": "Shell",
    "sh": "Shell",
    "zsh": "Shell",
    "fish": "Shell",
    "node": "JavaScript",
    "nodejs": "JavaScript",
    "ruby": "Ruby",
    "php": "PHP",
    "perl": "Perl",
    "lua": "Lua",
}


def language_from_shebang(text: str) -> str | None:
    """Infer a language from a ``#!`` interpreter line, if present."""
    first_line = text.split("\n", 1)[0].strip()
    if not first_line.startswith("#!"):
        return None
    parts = first_line[2:].strip().split()
    if not parts:
        return None
    interpreter = parts[0].rsplit("/", 1)[-1].lower()
    if interpreter == "env" and len(parts) > 1:
        interpreter = parts[1].rsplit("/", 1)[-1].lower()
    return _SHEBANG_LANGUAGES.get(interpreter)
