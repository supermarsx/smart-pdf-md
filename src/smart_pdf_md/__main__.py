"""Module entry point for `python -m smart_pdf_md` and frozen binaries.

Use absolute imports so freezing (PyInstaller) works without package context.
"""

from smart_pdf_md.cli import main

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
