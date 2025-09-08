"""Argparse-based command-line interface for smart-pdf-md.

Invoked via the console script `smart-pdf-md` or as a module with
`python -m smart_pdf_md`.
"""

from __future__ import annotations

import time
from pathlib import Path
import argparse

from .core import iter_input_files, process_one, log, set_config
from . import __version__


def _compute_version() -> str:
    """Return a version string, optionally with git metadata if available."""
    base = f"smart-pdf-md {__version__}"
    try:
        import subprocess
        import os

        git_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".git"))
        if not os.path.isdir(git_dir):
            return base
        sha = (
            subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL)
            .decode()
            .strip()
        )
        date = (
            subprocess.check_output(
                ["git", "show", "-s", "--format=%cd", "--date=iso-strict", "HEAD"],
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )
        return f"{base} (git {sha} {date})"
    except Exception:
        return base


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
    # Torch/Marker environment convenience flags
    p.add_argument("-T", "--torch-device", dest="torch_device", help="TORCH_DEVICE value")
    p.add_argument("-O", "--ocr-engine", dest="ocr_engine", help="OCR_ENGINE value")
    p.add_argument(
        "-P",
        "--pytorch-alloc-conf",
        dest="pytorch_alloc_conf",
        help="PYTORCH_CUDA_ALLOC_CONF value",
    )
    p.add_argument(
        "-G",
        "--cuda-visible-devices",
        dest="cuda_visible_devices",
        help="CUDA_VISIBLE_DEVICES value",
    )
    p.add_argument(
        "-E",
        "--env",
        action="append",
        metavar="KEY=VALUE",
        help="Set environment variable(s); can be repeated",
    )
    p.add_argument("-m", "--mode", choices=["auto", "fast", "marker"], help="Processing mode")
    p.add_argument("-o", "--out", dest="outdir", help="Output directory")
    p.add_argument(
        "-f",
        "--output-format",
        choices=["md", "txt"],
        help="Output format for fast path (marker remains markdown)",
    )
    p.add_argument(
        "-S",
        "--include",
        action="append",
        help="Glob pattern(s) to include when scanning a folder",
    )
    p.add_argument(
        "-X",
        "--exclude",
        action="append",
        help="Glob pattern(s) to exclude when scanning a folder",
    )
    p.add_argument(
        "-V",
        "--version",
        action="version",
        version=_compute_version(),
        help="Show version and exit",
    )
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
    p.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="Log actions only; do not write outputs or run Marker",
    )
    p.add_argument(
        "-p",
        "--progress",
        action="store_true",
        help="Show incremental progress (pages, slices) while processing",
    )
    p.add_argument("-q", "--quiet", action="store_true", help="Set log level to ERROR (overridden by --log-level)")
    p.add_argument("-v", "--verbose", action="store_true", help="Set log level to DEBUG (overridden by --log-level)")
    p.add_argument("--log-json", action="store_true", help="Emit logs as JSON lines (ts, level, message)")
    p.add_argument("--log-file", help="Append logs to a file (1MB simple rotation)")
    p.add_argument(
        "-w",
        "--no-warn-unknown-env",
        action="store_true",
        help="Do not warn when encountering unknown environment keys",
    )
    # Reliability knobs
    p.add_argument("-t", "--timeout", type=int, dest="timeout", help="Marker subprocess timeout (seconds)")
    p.add_argument("-x", "--retries", type=int, dest="retries", help="Retries for marker subprocess")
    # Resume/skip existing
    p.add_argument("-R", "--resume", action="store_true", help="Skip PDFs whose outputs already exist")
    # First-run checklist
    p.add_argument("-D", "--check-deps", action="store_true", help="Check and optionally install missing dependencies")
    p.add_argument("-y", "--yes", action="store_true", help="Assume yes for dependency prompts when using --check-deps")
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

    # Known env keys to avoid noisy warnings (case-sensitive comparison after upper())
    KNOWN_ENV = {
        # Project envs
        "SMART_PDF_MD_MODE",
        "SMART_PDF_MD_MARKER_MOCK",
        "SMART_PDF_MD_MARKER_MOCK_FAIL",
        "SMART_PDF_MD_IMAGES",
        "SMART_PDF_MD_OUTPUT_DIR",
        "SMART_PDF_MD_TEXT_MIN_CHARS",
        "SMART_PDF_MD_TEXT_MIN_RATIO",
        "SMART_PDF_MD_MOCK_FAIL_IF_SLICE_GT",
        "SMART_PDF_MD_DRY_RUN",
        "SMART_PDF_MD_LOG_LEVEL",
        "SMART_PDF_MD_PROGRESS",
        "SMART_PDF_MD_PYTHON",
        "SMART_PDF_MD_COVERAGE",
        # Marker/Torch common envs
        "TORCH_DEVICE",
        "OCR_ENGINE",
        "PYTORCH_CUDA_ALLOC_CONF",
        "CUDA_VISIBLE_DEVICES",
    }

    # Determine whether to warn on unknown env keys: default True, can be disabled
    warn_unknown_env = True
    if cfg.get("warn_unknown_env") is not None:
        try:
            warn_unknown_env = bool(cfg.get("warn_unknown_env"))  # type: ignore[arg-type]
        except Exception:
            warn_unknown_env = True
    if ns.no_warn_unknown_env:
        warn_unknown_env = False

    def _warn_unknown_env(key: str) -> None:
        if warn_unknown_env and key.upper() not in KNOWN_ENV:
            log(f"[WARN ] unknown env key: {key}", level="WARNING")

    # Apply environment variables from config first, then CLI overrides
    if isinstance(cfg.get("env"), dict):
        import os as _os

        for k, v in cfg["env"].items():  # type: ignore[assignment]
            _os.environ[str(k)] = str(v)
            _warn_unknown_env(str(k))
    if ns.env:
        import os as _os

        for item in ns.env:
            if "=" not in item:
                log(f"[WARN ] ignoring invalid --env entry: {item}", level="WARNING")
                continue
            k, v = item.split("=", 1)
            _os.environ[k] = v
            _warn_unknown_env(k)

    # Apply convenience env flags (CLI overrides config)
    # Accept config keys: torch_device, ocr_engine, pytorch_cuda_alloc_conf, cuda_visible_devices
    import os as _os

    torch_device = ns.torch_device if ns.torch_device else cfg.get("torch_device")
    if torch_device is not None:
        _os.environ["TORCH_DEVICE"] = str(torch_device)
    ocr_engine = ns.ocr_engine if ns.ocr_engine else cfg.get("ocr_engine")
    if ocr_engine is not None:
        _os.environ["OCR_ENGINE"] = str(ocr_engine)
    pa_conf = ns.pytorch_alloc_conf if ns.pytorch_alloc_conf else cfg.get("pytorch_cuda_alloc_conf")
    if pa_conf is not None:
        _os.environ["PYTORCH_CUDA_ALLOC_CONF"] = str(pa_conf)
    cuda_devices = (
        ns.cuda_visible_devices if ns.cuda_visible_devices else cfg.get("cuda_visible_devices")
    )
    if cuda_devices is not None:
        _os.environ["CUDA_VISIBLE_DEVICES"] = str(cuda_devices)

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
        mode=(
            ns.mode.lower()
            if ns.mode
            else str(cfg.get("mode")).lower()
            if cfg.get("mode")
            else None
        ),
        images=(
            True
            if ns.images
            else False
            if ns.no_images
            else bool(cfg.get("images"))
            if cfg.get("images") is not None
            else None
        ),
        outdir=(
            ns.outdir
            if ns.outdir is not None
            else str(cfg.get("outdir"))
            if cfg.get("outdir")
            else None
        ),
        min_chars=(
            ns.min_chars
            if ns.min_chars is not None
            else int(cfg.get("min_chars"))
            if cfg.get("min_chars") is not None
            else None
        ),
        min_ratio=(
            ns.min_ratio
            if ns.min_ratio is not None
            else float(cfg.get("min_ratio"))
            if cfg.get("min_ratio") is not None
            else None
        ),
        mock=(True if ns.mock else bool(cfg.get("mock")) if cfg.get("mock") is not None else None),
        mock_fail=(
            True
            if ns.mock_fail
            else bool(cfg.get("mock_fail"))
            if cfg.get("mock_fail") is not None
            else None
        ),
        log_level=(
            ns.log_level
            if ns.log_level
            else str(cfg.get("log_level")).upper()
            if cfg.get("log_level")
            else None
        ),
        dry_run=(
            True
            if ns.dry_run
            else bool(cfg.get("dry_run"))
            if cfg.get("dry_run") is not None
            else None
        ),
        progress=(
            True
            if ns.progress
            else bool(cfg.get("progress"))
            if cfg.get("progress") is not None
            else None
        ),
        output_format=(
            ns.output_format
            if ns.output_format
            else str(cfg.get("output_format")).lower()
            if cfg.get("output_format")
            else None
        ),
        include=(
            ns.include
            if ns.include
            else list(cfg.get("include"))
            if isinstance(cfg.get("include"), list)
            else None
        ),
        exclude=(
            ns.exclude
            if ns.exclude
            else list(cfg.get("exclude"))
            if isinstance(cfg.get("exclude"), list)
            else None
        ),
        log_json=(True if cfg.get("log_json") else None),
        log_file=(str(cfg.get("log_file")) if cfg.get("log_file") else None),
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



