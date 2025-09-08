"""
Entry file to run the smart-pdf-md CLI directly from a source checkout.

Usage:
  python main.py INPUT SLICE [--flags]

This shim ensures the local `src/` package is importable without installation.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _ensure_src_on_path() -> None:
    root = Path(__file__).resolve().parent
    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


def main() -> int:  # pragma: no cover - thin wrapper
    _ensure_src_on_path()
    from smart_pdf_md.cli import main as cli_main

    return cli_main()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
