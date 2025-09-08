# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project adheres to Semantic Versioning.

## [Unreleased]

### Added
- Python-only unified CLI with argparse (`python -m smart_pdf_md` and console script `smart-pdf-md`).
- Short flags for all CLI options (-m, -o, -i/-I, -c, -r, -M, -F).
- Root entry script `smart-pdf-md.py` for easy local runs (no install).
- CI build-test job that executes the built binary with a cross-platform smoke test.
- Release workflow for multi-OS/arch binaries (Linux x86_64/ARM64, macOS x86_64/ARM64, Windows x86_64).
- Publish workflow using secrets (`PYPI_API_TOKEN`, `TEST_PYPI_API_TOKEN`).
- Conventional Commits PR title check, PR template, and semantic config.
- Documentation: CLI usage with short flags, build/test/release matrix.
- Docstrings across core and CLI modules.
- Badges: GitHub releases downloads (total) + PyPI downloads (total), coverage badge generation.

### Changed
- Restructured codebase to `src/` package layout (`smart_pdf_md`).
- Tests updated to invoke `python -m smart_pdf_md` and set `PYTHONPATH=src` when needed.
- CI: separate lint, format, test, build, and build-test jobs; tests run on Ubuntu with Python 3.11; builds/tested across Windows/Ubuntu/macOS.
- CI: use `genbadge` CLI for coverage badge; artifact naming unified per OS.
- Packaging: added PEP 621 metadata and console entry point in `pyproject.toml`.

### Removed
- Legacy wrappers `smart-pdf-md.bat` and `smart-pdf-md.sh`.
- Old `smart_pdf_md_driver.py` (logic moved into `src/smart_pdf_md/core.py`).
- Stray artifact files (`fast`, `temp.part`, `{out}`, `PyMuPDF')`, `marker_single')`).
- Extra entry shim `main.py` (use `smart-pdf-md.py` or console script instead).

## [0.1.0] - 2025-09-08
- Initial version and repository setup.

[Unreleased]: https://github.com/supermarsx/smart-pdf-md/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/supermarsx/smart-pdf-md/releases/tag/v0.1.0
