from __future__ import annotations
import time
from pathlib import Path
import argparse

from .core import iter_input_files, process_one, log, set_config


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="smart-pdf-md", add_help=True)
    p.add_argument("input", help="Input PDF file or directory")
    p.add_argument("slice", type=int, help="Slice size for marker path")
    p.add_argument("--mode", choices=["auto", "fast", "marker"], help="Processing mode")
    p.add_argument("--out", dest="outdir", help="Output directory")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--images", dest="images", action="store_true", help="Enable images")
    g.add_argument("--no-images", dest="no_images", action="store_true", help="Disable images")
    p.add_argument(
        "--min-chars", type=int, dest="min_chars", help="Min chars per page for fast path"
    )
    p.add_argument("--min-ratio", type=float, dest="min_ratio", help="Min ratio of textual pages")
    p.add_argument("--mock", action="store_true", help="Mock marker path")
    p.add_argument("--mock-fail", action="store_true", help="Force mock marker failure")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(argv if argv is not None else None)

    inp = Path(ns.input)
    slice_pages = int(ns.slice)

    set_config(
        mode=(ns.mode.lower() if ns.mode else None),
        images=(True if ns.images else False if ns.no_images else None),
        outdir=ns.outdir,
        min_chars=ns.min_chars,
        min_ratio=ns.min_ratio,
        mock=True if ns.mock else None,
        mock_fail=True if ns.mock_fail else None,
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
