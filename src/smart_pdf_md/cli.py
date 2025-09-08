"""Argparse-based command-line interface for smart-pdf-md.

Invoked via the console script `smart-pdf-md` or as a module with
`python -m smart_pdf_md`.
"""

from __future__ import annotations

import time
from pathlib import Path
import argparse

from .core import iter_input_files, process_one, log, set_config


def build_parser() -> argparse.ArgumentParser:
    """Create and return the CLI argument parser."""
    p = argparse.ArgumentParser(prog="smart-pdf-md", add_help=True)
    p.add_argument("input", nargs="?", help="Input PDF file or directory")
    p.add_argument("slice", nargs="?", type=int, help="Slice size for marker path")
    p.add_argument(
        "-C",
        "--config",
        dest="config",
        help="Path to a config file (.toml/.yaml/.yml/.json)",
    )
    p.add_argument("-m", "--mode", choices=["auto", "fast", "marker"], help="Processing mode")
    p.add_argument("-o", "--out", dest="outdir", help="Output directory")
    g = p.add_mutually_exclusive_group()
    g.add_argument("-i", "--images", dest="images", action="store_true", help="Enable images")
    g.add_argument(
        "-I", "--no-images", dest="no_images", action="store_true", help="Disable images"
    )
    p.add_argument(
        "-c",
        "--min-chars",
        type=int,
        dest="min_chars",
        help="Min chars per page for fast path",
    )
    p.add_argument(
        "-r", "--min-ratio", type=float, dest="min_ratio", help="Min ratio of textual pages"
    )
    p.add_argument("-M", "--mock", action="store_true", help="Mock marker path")
    p.add_argument("-F", "--mock-fail", action="store_true", help="Force mock marker failure")
    p.add_argument(
        "-L",
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Standard logging level threshold",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    """CLI entry point; returns a conventional exit code."""
    parser = build_parser()
    ns = parser.parse_args(argv if argv is not None else None)

    cfg: dict[str, object] = {}
    if ns.config:
        from .config import load_config_file

        try:
            cfg = load_config_file(ns.config)
        except Exception as e:  # pragma: no cover - I/O/parsing
            log(f"[ERROR] config load failed: {e!r}", level="ERROR")
            return 2

    # Resolve input and slice from CLI or config
    inp_val = ns.input if ns.input is not None else cfg.get("input")
    slice_val = ns.slice if ns.slice is not None else cfg.get("slice")
    if inp_val is None or slice_val is None:
        log("[USAGE] smart-pdf-md INPUT SLICE [-C CONFIG] [options]")
        return 2
    inp = Path(str(inp_val))
    slice_pages = int(slice_val)  # type: ignore[arg-type]

    # Merge config with CLI overrides
    set_config(
        mode=(ns.mode.lower() if ns.mode else str(cfg.get("mode")).lower() if cfg.get("mode") else None),
        images=(
            True
            if ns.images
            else False
            if ns.no_images
            else bool(cfg.get("images")) if cfg.get("images") is not None else None
        ),
        outdir=(ns.outdir if ns.outdir is not None else str(cfg.get("outdir")) if cfg.get("outdir") else None),
        min_chars=(ns.min_chars if ns.min_chars is not None else int(cfg.get("min_chars")) if cfg.get("min_chars") is not None else None),
        min_ratio=(ns.min_ratio if ns.min_ratio is not None else float(cfg.get("min_ratio")) if cfg.get("min_ratio") is not None else None),
        mock=(True if ns.mock else bool(cfg.get("mock")) if cfg.get("mock") is not None else None),
        mock_fail=(
            True if ns.mock_fail else bool(cfg.get("mock_fail")) if cfg.get("mock_fail") is not None else None
        ),
        log_level=(ns.log_level if ns.log_level else str(cfg.get("log_level")).upper() if cfg.get("log_level") else None),
    )

    files = list(iter_input_files(inp))
    if not files:
        return 1

    t0 = time.perf_counter()
    fails = 0
    exit_code = 0
    for i, f in enumerate(files, 1):
        try:
            rc = process_one(f, i, len(files), slice_pages)
        except Exception as e:  # pragma: no cover - safety
            log(f"[CRASH] {f}: {e!r}")
            rc = 10
        if rc != 0:
            fails += 1
            if exit_code == 0:
                exit_code = rc
    log(f"[DONE ] total={len(files)} failures={fails} elapsed={time.perf_counter() - t0:.2f}s")
    return exit_code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
