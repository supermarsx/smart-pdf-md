# smart-pdf-md

[![CI](https://github.com/supermarsx/smart-pdf-md/actions/workflows/ci.yml/badge.svg)](https://github.com/supermarsx/smart-pdf-md/actions/workflows/ci.yml)
[![Coverage](badges/coverage.svg)](docs/coverage.md)
[![PyPI](https://img.shields.io/pypi/v/smart-pdf-md)](https://pypi.org/project/smart-pdf-md/)
[![Downloads](https://img.shields.io/github/downloads/supermarsx/smart-pdf-md/total)](https://github.com/supermarsx/smart-pdf-md/releases)
[![PyPI Downloads](https://pepy.tech/badge/smart-pdf-md)](https://pepy.tech/project/smart-pdf-md)
[![GitHub Stars](https://img.shields.io/github/stars/supermarsx/smart-pdf-md)](https://github.com/supermarsx/smart-pdf-md/stargazers)
[![GitHub Forks](https://img.shields.io/github/forks/supermarsx/smart-pdf-md)](https://github.com/supermarsx/smart-pdf-md/network/members)
[![GitHub Watchers](https://img.shields.io/github/watchers/supermarsx/smart-pdf-md)](https://github.com/supermarsx/smart-pdf-md/watchers)
[![GitHub Issues](https://img.shields.io/github/issues/supermarsx/smart-pdf-md)](https://github.com/supermarsx/smart-pdf-md/issues)
[![Commit Activity](https://img.shields.io/github/commit-activity/m/supermarsx/smart-pdf-md)](https://github.com/supermarsx/smart-pdf-md/commits)
[![Made with Python](https://img.shields.io/badge/Made%20with-Python-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](license.md)
<!-- Coverage badge (enable Codecov in repo to activate)
[![codecov](https://codecov.io/gh/supermarsx/smart-pdf-md/branch/main/graph/badge.svg)](https://codecov.io/gh/supermarsx/smart-pdf-md)
-->

Python CLI to **mass-convert PDF (.pdf) to Markdown (.md)** with smart routing:

* **Textual PDFs →** fast text extraction via **PyMuPDF** (fitz)
* **Scanned/non-textual PDFs →** robust conversion via **Marker** (`marker-pdf` / `marker_single`), with automatic **page slicing** to avoid OOM/timeouts


## Why “smart”?

The tool inspects each PDF. If enough pages contain real text, it uses PyMuPDF (much faster). Otherwise it falls back to Marker’s high‑quality PDF→Markdown path. Very large PDFs are processed in **slices** (configurable, default 40 pages) to increase reliability.


## Features

* **Batch/recursive conversion** of one file or an entire folder tree
* **Auto‑install** Python dependencies on first run (`pymupdf`, `marker-pdf`)
* **Heuristic routing** between fast text extraction and Marker OCR/layout path
* **Slice processing** for large docs with progressive backoff on errors
* **Inline logging** with consistent tags (`[scan]`, `[file]`, `[path]`, `[OK]`, `[WARN]`, `[ERROR]`…)
* **Zero setup** beyond having Python + pip on PATH (Windows)
* **UTF‑8 console** (uses `chcp 65001`)

> **Note:** Image extraction in the Marker path is **disabled by default**; output focuses on Markdown text.


## Requirements

* **Windows** (runs in `cmd.exe` via `.bat`)
* **Python** with **pip** available on PATH

  * The script checks/prints Python version/bitness and pip version
* Internet access on first run (to install `pymupdf` and `marker-pdf` if missing)
* Optional: **CUDA‑capable GPU** (the script exports `TORCH_DEVICE=cuda` for Marker). If you don’t have a compatible GPU/driver, switch to CPU (see **Configuration**).


## Quick Start

Run one of the following from the repo or an installed environment:

- From source (repo root): `python smart-pdf-md.py INPUT SLICE [options]`
- As a module: `python -m smart_pdf_md INPUT SLICE [options]`
- Installed script: `smart-pdf-md INPUT SLICE [options]`

**Arguments**

* `INPUT`
  Path to a **PDF file** or a **folder**. If omitted, defaults to the **current directory**.
* `SLICE`
  Max pages per Marker slice. Default **40**. The script halves this (down to a min of 5) on failures and retries.

**Examples**

```
# Convert all PDFs recursively under the current folder (default slice=40)
smart-pdf-md . 40

# Convert one folder, larger slices (50 pages)
smart-pdf-md "./docs/Handbooks" 50

# Convert a single file
smart-pdf-md "./reports/2024/survey.pdf" 40
```

**Output location**

* For each `input.pdf`, the tool writes `input.md` **next to** the PDF (same folder).

### Flags and environment

- Prefer CLI flags listed under “Python CLI” for day‑to‑day use.
- Config files (TOML/YAML/JSON) can set options and environment in one place (-C/--config).
- Environment variables can be provided inline via -E KEY=VALUE or under [env] in config.
- Unknown env keys warn by default; suppress with --no-warn-unknown-env or warn_unknown_env=false in config.

Common environment keys (CLI flags are usually better):
- SMART_PDF_MD_MODE (auto|fast|marker), SMART_PDF_MD_OUTPUT_DIR, SMART_PDF_MD_IMAGES.
- SMART_PDF_MD_TEXT_MIN_CHARS, SMART_PDF_MD_TEXT_MIN_RATIO.
- Marker/Torch: TORCH_DEVICE, OCR_ENGINE, PYTORCH_CUDA_ALLOC_CONF, CUDA_VISIBLE_DEVICES.

## Logs

- Default text logs with tags like [scan], [file], [path], [TEXT], [RUN], [OK], [WARN], [ERROR].
- -p/--progress shows incremental updates (pages, slices).
- Structured logs: --log-json and --log-file run.log for JSON lines and archival.
- Verbosity: -q/--quiet (ERROR), -v/--verbose (DEBUG), or -L/--log-level.

## Configuration

- See config.toml.example and the “Config File” section for TOML/YAML/JSON examples.
- Torch/Marker convenience flags map to envs: -T/--torch-device, -O/--ocr-engine, -P/--pytorch-alloc-conf, -G/--cuda-visible-devices.## Python CLI

Run without installing (from repo root):

`
python smart-pdf-md.py INPUT SLICE [options]
`

Short options
- -m, --mode {auto,fast,marker}: processing mode
- -o, --out DIR: output directory
- --output-format {md,txt}: fast-path output extension (marker remains markdown)
- -i, --images / -I, --no-images: toggle image extraction for Marker path
- -c, --min-chars INT: min chars/page to treat as textual
- -r, --min-ratio FLOAT: min ratio of textual pages
- -S, --include GLOB: include pattern(s) when scanning a folder (repeatable)
- -X, --exclude GLOB: exclude pattern(s) when scanning a folder (repeatable)
- -p, --progress: show incremental progress (pages/slices)
- -n, --dry-run: log intended actions; do not write or run Marker
- -L, --log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}: logging threshold
- -q/--quiet and -v/--verbose: set ERROR/DEBUG respectively (overridden by -L)
- --log-json: emit JSON logs; --log-file PATH: also append logs to file
- -C, --config FILE: load TOML/YAML/JSON config; CLI overrides config values
- -E, --env KEY=VALUE: set env var(s) for this run (repeatable)
- --no-warn-unknown-env: suppress warnings for unknown env keys
- -T, --torch-device VAL; -O, --ocr-engine VAL
- -P, --pytorch-alloc-conf VAL; -G, --cuda-visible-devices VAL
- -V, --version: print version (includes git SHA/date in a git checkout)

Example
`
python smart-pdf-md.py . 40 -m marker -M -o out -i -p --output-format md \
  -S "**/Handbooks/*.pdf" -X "**/*draft*.pdf" -L INFO --log-json --log-file run.log
`

## Build & Test Matrix

- Tests (CI): Ubuntu (ubuntu-latest) with Python 3.11
- Builds (CI): Windows, Ubuntu, macOS (one-file binaries)
- Releases (GH Releases):
  - Linux: x86_64 (ubuntu-latest), ARM64 (ubuntu-22.04-arm64)
  - macOS: x86_64 (macos-13), ARM64 (macos-14)
  - Windows: x86_64 (windows-latest)

## Dependencies & pip-tools

This repo uses split requirements and optionally supports pip-tools for pinning.

- Runtime (base):
  - `requirements.in` → source of unpinned base deps
  - `requirements.txt` → compiled from `requirements.in`

- Development:
  - `requirements-dev.in` → source of unpinned dev deps (includes `-r requirements.in`)
  - `requirements-dev.txt` → compiled from `requirements-dev.in`

Compile with pip-tools (optional):

```
pip install pip-tools
pip-compile requirements.in -o requirements.txt
pip-compile requirements-dev.in -o requirements-dev.txt
```

Install for development:

```
python -m pip install -r requirements-dev.txt
python -m pip install -e .
```

## Troubleshooting

- No output created
  - Run with `-p -L DEBUG` to see progress and routing decisions.
  - Use `-n` (dry-run) to preview actions without writing files.
- Marker fails or is slow
  - Force fast path with `-m fast` for textual PDFs.
  - Limit GPU settings via `-T cpu` or `-G 0`.
- Too many files processed
  - Use `-S/--include` and `-X/--exclude` globs to narrow scope.
- Logs hard to parse
  - Use `--log-json` and `--log-file run.log` for structured logging and archival.





