"""Module entry-point to allow `python -m smart_pdf_md`."""

from .cli import main

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
