# Legacy `pus` prototype

> **Archived documentation.** The original `pus` script and its generated
> `output.md` sample have been removed during repository cleanup. This page is
> kept as historical documentation for the old `pus . -m -c` workflow. The
> supported tool is now **Pussy CLI**, documented in the
> [main README](../README.md).

Pussy is a zero-dependency CLI tool built with Python to aggregate source code repositories into token-optimized Markdown contexts for Large Language Models (LLMs) such as ChatGPT, Claude, Gemini, and local models.

It addresses two primary challenges when sharing codebases with AI:

1. **Architectural Context**: Generates a clean directory tree structure so the LLM understands file locations and relationships.
2. **Token Efficiency**: Filters out non-essential project files (build outputs, lockfiles, binary assets) and removes redundant whitespace to reduce prompt token consumption.

## Table of Contents

* [Features](#features)
* [Prerequisites](#prerequisites)
* [Installation](#installation)
  * [Linux / macOS](#linux--macos)
  * [Windows](#windows)
    * [Option A: Automated PowerShell Setup (Recommended)](#option-a-automated-powershell-setup-recommended)
    * [Option B: Manual Setup (CMD / PowerShell)](#option-b-manual-setup-cmd--powershell)
* [Usage](#usage)
  * [Command Syntax](#command-syntax)
  * [CLI Flags](#cli-flags)
  * [Common Examples](#common-examples)
* [Default Ignore Patterns](#default-ignore-patterns)
* [Token Optimization Details](#token-optimization-details)
* [Customization](#customization)
* [License](#license)

## Features

* **Directory Tree Generation**: Visualizes folder hierarchy in ASCII tree format to provide spatial and structural context.
* **Automatic Filtering**: Ignores common build directories (`node_modules`, `venv`, `target`, `.git`), package lockfiles, and binary/media files.
* **Token Minification Mode (`-m`)**: Removes empty lines throughout the code to save context space without altering indentation or code logic.
* **Cross-Platform Clipboard Integration (`-c`)**: Native clipboard copying for Windows (PowerShell/clip), macOS (pbcopy), and Linux (wl-copy/xclip).
* **Zero External Dependencies**: Built using pure Python standard library modules.

## Prerequisites

* **Python**: Version 3.6 or higher (ensure "Add Python to PATH" was selected during Python installation).

## Installation

### Linux / macOS

1. Download the script:

```bash
curl -sSL https://raw.githubusercontent.com/your-username/pus/main/pus -o pus
```

2. Grant execution permission:

```bash
chmod +x pus
```

3. Move it to your local binary directory (ensure `~/.local/bin` is in your `$PATH`):

```bash
mv pus ~/.local/bin/
```

---

### Windows

#### Option A: Automated PowerShell Setup (Recommended)

Open **PowerShell** as your normal user and execute the following command. It creates a local `bin` directory, downloads the Python script, generates the Windows batch executable wrapper, and adds the path to your User Environment `PATH`:

```powershell
# Create bin directory in User Profile
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\bin"

# Download Python script into the directory
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/your-username/pus/main/pus" -OutFile "$env:USERPROFILE\bin\pus.py"

# Create batch script wrapper for CMD/PowerShell CLI execution
@'
@echo off
python "%~dp0pus.py" %*
'@ | Out-File -Encoding ascii "$env:USERPROFILE\bin\pus.bat"

# Add folder to User PATH variable if not already added
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($UserPath -notlike "*$env:USERPROFILE\bin*") {
    [Environment]::SetEnvironmentVariable("Path", "$UserPath;$env:USERPROFILE\bin", "User")
    Write-Host "Success: Added $env:USERPROFILE\bin to User PATH." -ForegroundColor Green
    Write-Host "Please restart your terminal session to start using 'pus'." -ForegroundColor Yellow
} else {
    Write-Host "Success: 'pus' is updated and ready to use." -ForegroundColor Green
}
```

After running this script, restart your terminal (PowerShell, CMD, or Windows Terminal).

#### Option B: Manual Setup (CMD / PowerShell)

1. **Create a CLI Directory**:
   Create a dedicated folder for your custom tools, for example: `C:\Tools\pus` (or `%USERPROFILE%\bin`).

2. **Save the Python Script**:
   Copy the `pus` Python code and save it inside that folder as `pus.py`.

3. **Create the Batch Wrapper**:
   In the same folder, create a new text file named `pus.bat` with the following contents:

   ```bat
   @echo off
   python "%~dp0pus.py" %*
   ```

4. **Add Folder to Environment Variables (PATH)**:
   * Press `Win + R`, type `sysdm.cpl`, and press **Enter**.
   * Go to the **Advanced** tab and click **Environment Variables**.
   * Under **User variables**, select `Path` and click **Edit**.
   * Click **New** and type the full folder path (e.g., `C:\Tools\pus`).
   * Click **OK** on all dialog boxes to save changes.

5. **Verify Installation**:
   Open a new Command Prompt or PowerShell window and test:

   ```cmd
   pus --help
   ```

---

## Usage

### Command Syntax

```bash
pus [target_paths...] [options]
```

If no target path is specified, `pus` defaults to the current working directory (`.`).

### CLI Flags

| Flag | Long Option | Description | 
| ----- | ----- | ----- | 
| `-m` | `--minify` | Strips all empty lines inside code blocks to minimize token usage. | 
| `-c` | `--copy` | Copies the compiled Markdown directly to the system clipboard. | 
| `-h` | `--help` | Displays help message and CLI usage documentation. | 

### Common Examples

1. **Summarize full project directory, minify code, and copy to clipboard:**

```bash
pus . -m -c
```

2. **Summarize specific files or subdirectories:**

```bash
pus src/components/ package.json -m -c
```

3. **Output Markdown structure directly to terminal or file:**

```bash
pus . -m > ai_context.md
```

---

## Output Format Example

Running `pus src/ package.json -m` generates the following output:

````markdown
### Directory Structure:
```text
my-project/
├── package.json
└── src
    ├── index.js
    └── utils.js
```

### Code Contents:

`package.json`
```
{
  "name": "my-project",
  "version": "1.0.0",
  "dependencies": {
    "express": "^4.18.2"
  }
}
```

`src/index.js`
```
import { calculateSum } from './utils.js';
const express = require('express');
const app = express();
app.get('/', (req, res) => {
  const result = calculateSum(10, 5);
  res.send(`Result: ${result}`);
});
app.listen(3000);
```

`src/utils.js`
```
export function calculateSum(a, b) {
    return a + b;
}
```
````

---

## Default Ignore Patterns

The tool excludes non-essential files and binary assets by default:

* **Directories**: `.git`, `node_modules`, `venv`, `.venv`, `__pycache__`, `build`, `dist`, `.next`, `.nuxt`, `.output`, `.svelte-kit`, `target`, `.idea`, `.vscode`, `coverage`, `vendor`
* **Lockfiles**: `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `Cargo.lock`, `poetry.lock`, `composer.lock`, `.DS_Store`
* **Binary & Media Extensions**: `.png`, `.jpg`, `.jpeg`, `.gif`, `.ico`, `.svg`, `.webp`, `.pdf`, `.exe`, `.bin`, `.dll`, `.so`, `.class`, `.pyc`, `.zip`, `.tar`, `.gz`, `.rar`, `.mp3`, `.mp4`, `.ttf`, `.woff`, `.woff2`, `.eot`

---

## Token Optimization Details

LLM tokenizers treat consecutive newline characters (`\n`) as individual tokens. In larger codebases, empty lines across files accumulate unnecessary token overhead.

Applying `-m` (`--minify`):

* Removes blank lines.
* Preserves indentation rules for whitespace-sensitive languages (such as Python and YAML).
* Maximizes the amount of code context fits within prompt limits.

---

## Customization

To extend or modify the list of ignored patterns, edit the matching sets at the top of the script:

```python
IGNORE_DIRS = {
    '.git', 'node_modules', 'venv', ...
}

IGNORE_FILES = {
    'package-lock.json', ...
}

IGNORE_EXTS = {
    '.png', '.jpg', ...
}
```

---

## License

MIT License