# Development

## Build & Test Matrix

- Tests (CI): Ubuntu (ubuntu-latest) on Python 3.11, 3.12, 3.13
- Builds (CI): Windows, Ubuntu, macOS (one-file binaries)
- Releases (GH Releases):
  - Linux: x86_64 (ubuntu-latest), ARM64 (ubuntu-22.04-arm64)
  - macOS: x86_64 (macos-13), ARM64 (macos-14)
  - Windows: x86_64 (windows-latest)

## CI speed-ups and binary checks

- Pip caching covers requirements*.in/txt and pyproject.toml
- Optional `USE_UV=1` enables the `uv` installer for faster setup
- Optional `ENABLE_OCR_SMOKE=1` runs an OCR smoke test when OCRmyPDF is available
- PyInstaller bundles PyMuPDF resources via `--collect-all fitz`
- CI validates fast-path extraction on a generated PDF (table-like lines + embedded image)
- Optional job "Test Optional Engines" installs `requirements-optional.txt` and Poppler/Ghostscript, then runs optional-engine tests

