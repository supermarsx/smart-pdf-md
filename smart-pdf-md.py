#!/usr/bin/env python3
"""
Root entry script to run smart-pdf-md directly after cloning.

Usage:
  python smart-pdf-md.py INPUT SLICE [--flags]

This ensures the local `src/` package is importable without installation.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _ensure_src_on_path() -> None:
    root = Path(__file__).resolve().parent
    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


def main() -> int:  # pragma: no cover - wrapper only
    _ensure_src_on_path()
    from smart_pdf_md.cli import main as cli_main

    return cli_main()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
