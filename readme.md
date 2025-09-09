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
* **UTF-8 console** (uses `chcp 65001`)

### Available engines (-e/--engine)

- fast / pymupdf: PyMuPDF plain text → Markdown
- marker: Marker single-file converter with slice backoff
- poppler / poppler-html2md / html2md: Poppler pdftohtml → markdownify
- pdfminer: pdfminer.six high-level text extraction
- pdfplumber: page-wise text via pdfplumber
- layout / pymupdf4llm: PyMuPDF4LLM layout-aware Markdown
- docling: IBM Docling Markdown conversion
- ocrmypdf / ocr: OCRmyPDF adds text layer, then fast path
- lattice: fast path + Camelot table extraction (lattice flavor)
- pypdf: Pure-Python text extraction
- pypdfium2: PDFium-based text extraction
- pytesseract: OCR via pdf2image + Pillow + Tesseract
- doctr: Deep OCR (python-doctr)
- unstructured: Generic PDF partition to text
- pdftotree: Layout to HTML → markdownify
- tabula: Tables via tabula-py (Markdown tables)
- grobid: Uses a GROBID server; writes TEI and a simple Markdown summary
- borb: Text via borb SimpleTextExtraction (falls back to pypdf)
- pdfrw: Fallback to pypdf for text
- pdfquery: Uses pdfminer for text
- easyocr: OCR with easyocr (CPU by default)
- kraken: OCR via the kraken CLI
- ghostscript / gs: Ghostscript txtwrite text extraction
- pdfx: Extracts references/links with pdfx; falls back to pdfminer text

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

### Usage examples

- Convert a single file with smart routing (default):
  - `smart-pdf-md input.pdf 40`

- Force fast PyMuPDF path (textual PDFs):
  - `smart-pdf-md input.pdf 40 -m fast`

- Force a specific engine:
  - Poppler html2md: `smart-pdf-md input.pdf 40 -e poppler`
  - Layout (PyMuPDF4LLM): `smart-pdf-md input.pdf 40 -e layout`
  - OCRmyPDF: `smart-pdf-md input.pdf 40 -e ocrmypdf`
  - Tesseract OCR: `smart-pdf-md input.pdf 40 -e pytesseract`
  - Ghostscript text: `smart-pdf-md input.pdf 40 -e ghostscript`

- Per‑category overrides in auto mode (keep smart routing):
  - Textual → layout, Non‑textual → marker: `smart-pdf-md input.pdf 40 --engine-textual layout --engine-nontextual marker`
  - Or via env: `SMART_PDF_MD_ENGINE_TEXTUAL=layout SMART_PDF_MD_ENGINE_NON_TEXTUAL=marker python -m smart_pdf_md input.pdf 40`

- Extract tables:
  - Stream mode: `smart-pdf-md input.pdf 40 --tables --tables-mode stream`
  - Lattice mode: `smart-pdf-md input.pdf 40 --tables --tables-mode lattice`

- Use GROBID (server required):
  - `GROBID_URL=https://your-grobid:8070 smart-pdf-md input.pdf 40 -e grobid`

- Batch convert a folder (recursive):
  - `smart-pdf-md ./docs 40`

### Flags and environment

- Prefer CLI flags listed under “Python CLI” for day‑to‑day use.
- Config files (TOML/YAML/JSON) can set options and environment in one place (-C/--config).
- Environment variables can be provided inline via -E KEY=VALUE or under [env] in config.
- Unknown env keys warn by default; suppress with --no-warn-unknown-env or warn_unknown_env=false in config.

Common environment keys (CLI flags are usually better):
- SMART_PDF_MD_MODE (auto|fast|marker), SMART_PDF_MD_OUTPUT_DIR, SMART_PDF_MD_IMAGES
- SMART_PDF_MD_TEXT_MIN_CHARS, SMART_PDF_MD_TEXT_MIN_RATIO
- SMART_PDF_MD_ENGINE (force engine), SMART_PDF_MD_ENGINE_TEXTUAL, SMART_PDF_MD_ENGINE_NON_TEXTUAL
- SMART_PDF_MD_TABLES=1; SMART_PDF_MD_TABLES_FLAVOR=(stream|lattice|auto)
- Marker/Torch: TORCH_DEVICE, OCR_ENGINE, PYTORCH_CUDA_ALLOC_CONF, CUDA_VISIBLE_DEVICES

Per-category engine overrides (auto mode)
- Keep smart routing (textual vs. non-textual) but choose engines:
  - `--engine-textual <engine>` for textual PDFs
  - `--engine-nontextual <engine>` for non-textual PDFs
  - Defaults: textual → PyMuPDF; non-textual → Marker

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

### CLI Options

| Option | Alt | Values | Description |
|---|---|---|---|
| `INPUT` | — | path | PDF file or directory to process |
| `SLICE` | — | int | Max pages per Marker slice (e.g., 40) |
| `-m`, `--mode` | — | auto, fast, marker | Processing mode/routing |
| `-e`, `--engine` | — | many | Force a specific engine (see “Available engines”) |
| `-ET`, `--engine-textual` | — | engine | Engine for textual PDFs in auto mode |
| `-EN`, `--engine-nontextual` | — | engine | Engine for non-textual PDFs in auto mode |
| `-o`, `--out` | — | dir | Output directory |
| `-f`, `--output-format` | — | md, txt | Fast path output format (Marker always md) |
| `-B`, `--tables` | — | — | Extract tables to `<stem>.tables.md` via Camelot (stream) |
| `--tables-mode` | — | auto, stream, lattice | Camelot mode (auto tries lattice then stream) |
| `-i`, `--images` | — | — | Enable image extraction in Marker path |
| `-I`, `--no-images` | — | — | Disable image extraction in Marker path |
| `-c`, `--min-chars` | — | int | Min chars/page to treat as textual |
| `-r`, `--min-ratio` | — | float | Min ratio of textual pages |
| `-S`, `--include` | — | glob | Include pattern(s) when scanning folders (repeatable) |
| `-X`, `--exclude` | — | glob | Exclude pattern(s) when scanning folders (repeatable) |
| `-p`, `--progress` | — | — | Show incremental progress (pages/slices) |
| `-n`, `--dry-run` | — | — | Log actions only; do not write outputs or run Marker |
| `-L`, `--log-level` | — | DEBUG, INFO, WARNING, ERROR, CRITICAL | Logging threshold |
| `-q`, `--quiet` | — | — | Set log level to ERROR (overrides mode) |
| `-v`, `--verbose` | — | — | Set log level to DEBUG (overrides mode) |
| `-J`, `--log-json` | — | — | Emit JSON logs (ts, level, message) |
| `-LF`, `--log-file` | — | path | Append logs to a file (1MB simple rotation) |
| `-C`, `--config` | — | file | Load TOML/YAML/JSON config; CLI overrides config |
| `-E`, `--env` | — | `KEY=VALUE` | Set env var(s) for this run (repeatable) |
| `-w`, `--no-warn-unknown-env` | — | — | Suppress warnings for unknown env keys |
| `-T`, `--torch-device` | — | value | Set `TORCH_DEVICE` (e.g., `cpu`, `cuda`) |
| `-O`, `--ocr-engine` | — | value | Set `OCR_ENGINE` |
| `-P`, `--pytorch-alloc-conf` | — | value | Set `PYTORCH_CUDA_ALLOC_CONF` |
| `-G`, `--cuda-visible-devices` | — | value | Set `CUDA_VISIBLE_DEVICES` |
| `-t`, `--timeout` | — | int | Marker subprocess timeout (seconds) |
| `-x`, `--retries` | — | int | Retries for Marker subprocess |
| `-R`, `--resume` | — | — | Skip PDFs whose outputs already exist |
| `-D`, `--check-deps` | `-y`, `--yes` | — | Check/install optional deps; `-y` assumes yes |
| `-V`, `--version` | — | — | Show version and exit |

Example
`
python smart-pdf-md.py . 40 -m marker -M -o out -i -p --output-format md \
  -S "**/Handbooks/*.pdf" -X "**/*draft*.pdf" -L INFO --log-json --log-file run.log
`

## Build & Test Matrix

- Tests (CI): Ubuntu (ubuntu-latest) on Python 3.11, 3.12, 3.13
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

### Optional extras

- Layout-aware Markdown (PyMuPDF4LLM): `pip install '.[layout]'`
- Docling engine: `pip install '.[docling]'`
- Poppler+html2md: `pip install '.[poppler]'` (requires `pdftohtml` on PATH)
- Tables extraction (Camelot): `pip install '.[tables]'`
  - Stream mode works with pure Python
  - Lattice mode requires Ghostscript and OpenCV
- OCR layer: `pip install '.[ocr]'` and install OCRmyPDF (and Tesseract) system-wide
- pdfminer: `pip install '.[pdfminer_engine]'`
- pdfplumber: `pip install '.[pdfplumber_engine]'`
- pypdf: `pip install '.[pypdf]'`
- pypdfium2: `pip install '.[pypdfium2]'`
- Tesseract OCR (pytesseract): `pip install '.[tesseract]'` (needs system Tesseract; pdf2image needs Poppler)
- Doctr OCR: `pip install '.[doctr]'`
- Unstructured: `pip install '.[unstructured]'`
- PDFToTree: `pip install '.[pdftotree]'`
- Tabula: `pip install '.[tabula]'` (requires Java)
- GROBID client: `pip install '.[grobid]'` (requires running server; set `GROBID_URL`)
- borb: `pip install '.[borb]'`
- pdfrw: `pip install '.[pdfrw]'`
- pdfquery: `pip install '.[pdfquery]'`
- easyocr: `pip install '.[easyocr]'`
- kraken OCR: `pip install '.[kraken]'` and install the `kraken` CLI

Convenience: requirements-optional.txt
- Install many optional engines at once:
  - `pip install -r requirements-optional.txt`

### System dependencies

- Poppler: install `pdftohtml` (e.g., `apt-get install poppler-utils`, `brew install poppler`, Windows: Poppler binaries on PATH)
- OCRmyPDF: install OCRmyPDF and Tesseract (`apt-get install ocrmypdf tesseract-ocr`, `brew install ocrmypdf tesseract`)
- Camelot lattice: install Ghostscript (`apt-get install ghostscript`, `brew install ghostscript`, Windows: ensure `gswin64c.exe` on PATH)
- Tabula: requires Java (Tabula)
- Kraken: install the `kraken` CLI and its models; ensure it’s on PATH
- GROBID: run a GROBID server; set `GROBID_URL=https://host:port`

## CI speed-ups and binary checks

- Pip caching covers requirements*.in/txt and pyproject.toml
- Optional `USE_UV=1` enables the `uv` installer for faster setup
- Optional `ENABLE_OCR_SMOKE=1` runs an OCR smoke test when OCRmyPDF is available
- PyInstaller bundles PyMuPDF resources via `--collect-all fitz`
- CI validates fast-path extraction on a generated PDF (table-like lines + embedded image)
- Optional job “Test Optional Engines” installs `requirements-optional.txt` and Poppler/Ghostscript, then runs optional-engine tests

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





