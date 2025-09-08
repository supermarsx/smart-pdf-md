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

Windows batch script to **mass-convert PDF (.pdf) to Markdown (.md)** with smart routing:

* **Textual PDFs →** fast text extraction via **PyMuPDF** (fitz)
* **Scanned/non-textual PDFs →** robust conversion via **Marker** (`marker-pdf` / `marker_single`), with automatic **page slicing** to avoid OOM/timeouts


## Why “smart”?

`smart-pdf-md.bat` inspects each PDF. If enough pages contain real text, it uses PyMuPDF (much faster). Otherwise it falls back to Marker’s high‑quality PDF→Markdown path. Very large PDFs are processed in **slices** (configurable, default 40 pages) to increase reliability.


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

1. Place `smart-pdf-md.bat` anywhere on your system (or clone/download the repo).
2. Open **Command Prompt** in the folder containing your PDFs, or pass a path.
3. Run:

On Windows (CMD):

```bat
smart-pdf-md.bat [INPUT] [SLICE] [FLAGS]
```

On Linux/macOS (bash):

```bash
bash smart-pdf-md.sh [INPUT] [SLICE] [FLAGS]
```

**Arguments**

* `INPUT`
  Path to a **PDF file** or a **folder**. If omitted, defaults to the **current directory**.
* `SLICE`
  Max pages per Marker slice. Default **40**. The script halves this (down to a min of 5) on failures and retries.

**Examples**

```bat
:: Convert all PDFs recursively under the current folder (default slice=40)
smart-pdf-md.bat

:: Convert one folder, larger slices (50 pages)
smart-pdf-md.bat "D:\Docs\Handbooks" 50

:: Convert a single file
smart-pdf-md.bat "C:\Reports\2024\survey.pdf"
```

**Output location**

* For each `input.pdf`, the tool writes `input.md` **next to** the PDF (same folder).

### Flags and environment

You can control the conversion path via an environment variable:

- `SMART_PDF_MD_MODE=auto` (default): heuristic routing between PyMuPDF and Marker
- `SMART_PDF_MD_MODE=fast`: force the fast PyMuPDF path and skip Marker deps
- `SMART_PDF_MD_MODE=marker`: force Marker path

For CI/tests without heavy dependencies, you can also enable a mock Marker writer:

- `SMART_PDF_MD_MARKER_MOCK=1`: skip calling `marker_single` and instead write a minimal Markdown file next to the PDF, simulating success. Useful to test routing and slice-backoff logic without downloading models.

CLI flags mirror these environment variables and can be appended after `INPUT` and `SLICE`:

- `--mode {auto|fast|marker}`
- `--out <dir>`
- `--images` / `--no-images`
- `--min-chars <N>` / `--min-ratio <F>`
- `--mock` / `--mock-fail`

### More environment knobs

- `SMART_PDF_MD_OUTPUT_DIR`: write all `.md` outputs into this directory (created if missing).
- `SMART_PDF_MD_IMAGES=1`: enable image extraction in the Marker path (by default it’s disabled).
- `SMART_PDF_MD_TEXT_MIN_CHARS`: per-page text threshold for the “textual” heuristic (default `100`).
- `SMART_PDF_MD_TEXT_MIN_RATIO`: min ratio of pages that must pass `MIN_CHARS` (default `0.2`).
- `SMART_PDF_MD_MARKER_MOCK_FAIL=1`: with mock enabled, simulate Marker failure to test non-zero exits and backoff paths.
- `SMART_PDF_MD_MOCK_FAIL_IF_SLICE_GT=<N>`: with mock enabled, fail any slice whose size is greater than `N`; useful to exercise slice backoff logic.

---

## What you’ll see (logs)

Representative log tags:

```
[boot] smart_pdf_md.bat starting...
[cfg ] Input            : "C:\Docs"
[cfg ] Slice pages      : 40
[cfg ] Output format    : markdown
[cfg ] Image extraction : DISABLED
[cfg ] DPI (low/high)   : 96 / 120
[lint] Python OK       : 3.11 / 64-bit
[lint] pip OK          : pip 24.x
[deps] PyMuPDF present.
[deps] marker-pdf present.
[env ] TORCH_DEVICE=cuda
[env ] OCR_ENGINE=surya
[io  ] Writing driver: "%TEMP%\smart_pdf_md_driver.py"
[scan ] folder: C:\Docs  files=37
[file ] (1/37) C:\Docs\foo.pdf
[path ] TEXTUAL -> fast PyMuPDF
[TEXT ] C:\Docs\foo.pdf -> C:\Docs\foo.md  (0.42s)
[file ] (2/37) C:\Docs\scanned.pdf
[path ] NON-TEXTUAL -> marker_single
[MRK_S] total_pages=240 slice=40 dpi=96/120
[RUN  ] marker_single ...
[OK   ] pages 0-39 in 35.22s
...
[done] smart_pdf_md.bat finished.
```

**Exit codes** (driver)

* `0` success
* `1` input path not found
* `2` slice processing failed even at minimum slice size
* `3` Marker single‑pass failed when PDF could not be opened by PyMuPDF
* `9` unhandled error

---

## Configuration

The batch file sets a few knobs you may want to change.

### Marker/torch environment

```
TORCH_DEVICE=cuda          # use 'cpu' if you don’t have a supported GPU
OCR_ENGINE=surya           # default OCR used by Marker
PYTORCH_CUDA_ALLOC_CONF    # tuned allocator settings for CUDA
```

> Edit these near the top of `smart-pdf-md.bat`. Setting `TORCH_DEVICE=cpu` improves compatibility at the cost of speed.

### DPI used by Marker

The generated Python driver defines:

```
LOWRES = 96
HIGHRES = 120
```

These influence Marker’s internal rendering during conversion. Increase for higher fidelity (slower) or decrease for speed. Edit the constants inside the **driver generation** section of the `.bat` if needed.

### Slice size

Pass `SLICE` on the command line (default 40). On failures, the driver halves the slice (`40 → 20 → 10 → 5`) and retries. Minimum slice is 5.

### Image extraction

The Marker path is configured for **Markdown text only** by default. If you want embedded images, call `marker_single` manually with the appropriate flags, or adapt the command in the batch file (search for the lines that build the `marker_single` command in the generated driver).


## How it works (under the hood)

1. **Toolchain check**: verifies `python`/`pip` and prints versions.
2. **Deps**: ensures `pymupdf` and `marker-pdf` are installed (installs if missing).
3. **Env**: exports Marker‑related env vars (device, OCR engine, CUDA allocator).
4. **Driver emit**: writes a temporary **Python driver** to `%TEMP%` and **pre‑compiles** it (`py_compile`).
5. **Routing** per file:

   * **Textual detection**: opens with PyMuPDF and counts pages with ≥100 non‑whitespace chars; if ≥20% of pages qualify → **fast text extraction** path writes a single `.md` by concatenating page text with blank lines.
   * Otherwise → **Marker path**:

     * If the PDF can’t be opened by PyMuPDF, run a **single‑pass** `marker_single`.
     * If it opens, process in **slices** of `SLICE` pages using `marker_single` per slice, shrinking the slice on errors.
6. **Output**: `.md` written next to the PDF.


## Development

- Prereqs: Python 3.11+ with pip. On macOS/Linux, bash for `smart-pdf-md.sh`.
- Install dev deps: `python -m pip install -r requirements-dev.txt`
- Lint: `python -m ruff check .`
- Test (uses PyMuPDF + mocked Marker): `python -m pytest -q`
- Optional: run scripts directly with mock path:
  - Windows: `smart-pdf-md.bat . 5 --mock`
  - macOS/Linux: `bash smart-pdf-md.sh . 5 --mock`

Notes
- Tests and CI mock the Marker path to avoid large downloads and GPU needs.
- PyMuPDF deprecation warnings are filtered in test runs (see `pyproject.toml`).


## Continuous Integration

The GitHub Actions workflow (`.github/workflows/ci.yml`) covers:

- Lint job (Ubuntu): ruff across repo and ShellCheck on the bash script.
- Test matrix across Windows, Ubuntu, macOS and Python 3.10–3.13.
- Pip caching to speed up repeated runs and concurrency control.
- Script smoke tests: runs `.bat` or `.sh` end-to-end in mock mode and asserts output exists.
- Coverage: publishes `coverage.xml`, an HTML report, and a summary artifact per matrix axis.

Environment in CI
- `SMART_PDF_MD_MARKER_MOCK=1` avoids heavy model downloads while still exercising routing/backoff logic.

Coverage locally
- Run: `python -m pytest -q --cov=tests --cov-report=term-missing --cov-report=xml:coverage.pytest.xml`
- For script path coverage (driver), set `SMART_PDF_MD_COVERAGE=1` when running the scripts; e.g., `SMART_PDF_MD_COVERAGE=1 bash smart-pdf-md.sh file.pdf 5 --mock`.

Troubleshooting CI
- If PyMuPDF wheels are temporarily unavailable for a brand-new Python patch release, pin Python to a prior minor/patch version until wheels publish.
- If ShellCheck isn’t available on a forked macOS runner, the lint job on Ubuntu is sufficient.

## Best practices & tips

* **No GPU?** Set `TORCH_DEVICE=cpu` in the `.bat` to avoid CUDA initialization errors.
* **Huge PDFs**: increase `SLICE` only if you have ample RAM/VRAM; otherwise keep or lower it.
* **Speed vs quality**: PyMuPDF is far faster but only extracts text; layout and tables are preserved better by Marker.
* **Stuck conversions**: lower `SLICE`, lower `DPI`, or switch to CPU if CUDA is unstable.


## Troubleshooting

* **“Python not found on PATH”**: Install Python from python.org or Microsoft Store and select *Add python.exe to PATH*.
* **pip install failures**: Ensure internet access and run the `.bat` from an elevated prompt if your environment requires it.
* **CUDA errors**: Set `TORCH_DEVICE=cpu` in the `.bat`, or ensure a compatible NVIDIA driver/CUDA runtime is present.
* **Garbled output (encoding)**: The script sets `chcp 65001` for UTF‑8; ensure your console font supports the glyphs.
* **Empty Markdown for scanned PDFs**: That indicates the fast path was chosen but the doc was actually scanned. Raise the heuristic (see below) or force Marker by temporarily disabling the fast path in the driver.

### Adjusting the “textual” heuristic (advanced)

Inside the generated driver, the function `is_textual(pdf, min_chars_per_page=100, min_ratio=0.2)` controls routing. You can raise `min_chars_per_page` or `min_ratio` to send more borderline documents through Marker.

## Development

- Tests: use `pytest`. CI runs on Windows, Ubuntu, and macOS.
- Fast-path e2e tests set `SMART_PDF_MD_MODE=fast` to avoid heavy Marker downloads.

Quick local run:

```bash
python -m pip install -r requirements-dev.txt
set SMART_PDF_MD_MODE=fast
pytest -q
```

To exercise Marker routing in tests without installing Marker/models:

```bash
set SMART_PDF_MD_MARKER_MOCK=1
pytest -q
```

To verify non-zero exit behavior in CI without Marker/models:

```bash
set SMART_PDF_MD_MARKER_MOCK=1
set SMART_PDF_MD_MARKER_MOCK_FAIL=1
pytest -q
```


## Contributing

PRs for:

* Optional image extraction toggle and output directory control
* Configurable heuristics via CLI flags
* Robust CPU/GPU auto‑detection for Marker
* Unit tests and CI


## License

Check out `license.md`.


## Appendix: Command reference (summary)

```
Usage: smart-pdf-md.bat [INPUT] [SLICE]

INPUT  : PDF file or directory (recursive). Default = current directory.
SLICE  : Max pages per slice for Marker. Default = 40. Min = 5 (auto‑backoff).

Output : Writes <filename>.md next to each PDF.
Return : 0=OK, 1=not found, 2=slice failed, 3=marker single‑pass failed, 9=unhandled.
```
