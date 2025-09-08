"""Core conversion logic for smart-pdf-md.

Provides routing between a fast text-extraction path (PyMuPDF) and the Marker pipeline
with slice-based backoff for robustness. Public functions include small, focused
docstrings and typed parameters for clarity.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable

try:  # PyMuPDF is optional for build environments
    import fitz  # type: ignore
except Exception as e:  # pragma: no cover - best effort
    fitz = None  # type: ignore[assignment]
    FITZ_IMPORT_ERROR = e
else:
    FITZ_IMPORT_ERROR = None


LOWRES = 96
HIGHRES = 120
# Configurable globals (overridable via set_config)
MODE = os.environ.get("SMART_PDF_MD_MODE", "auto").lower()
MOCK = os.environ.get("SMART_PDF_MD_MARKER_MOCK", "0") == "1"
MOCK_FAIL = os.environ.get("SMART_PDF_MD_MARKER_MOCK_FAIL", "0") == "1"
IMAGES = os.environ.get("SMART_PDF_MD_IMAGES", "0") == "1"
OUTDIR = os.environ.get("SMART_PDF_MD_OUTPUT_DIR")
MIN_CHARS = int(os.environ.get("SMART_PDF_MD_TEXT_MIN_CHARS", "100"))
MIN_RATIO = float(os.environ.get("SMART_PDF_MD_TEXT_MIN_RATIO", "0.2"))
MOCK_FAIL_IF_SLICE_GT = int(os.environ.get("SMART_PDF_MD_MOCK_FAIL_IF_SLICE_GT", "0"))
DRY_RUN = os.environ.get("SMART_PDF_MD_DRY_RUN", "0") == "1"
PROGRESS = os.environ.get("SMART_PDF_MD_PROGRESS", "0") == "1"
OUTPUT_FORMAT = os.environ.get("SMART_PDF_MD_OUTPUT_FORMAT", "md").lower()
INCLUDE: list[str] = []
EXCLUDE: list[str] = []
LOG_JSON = os.environ.get("SMART_PDF_MD_LOG_JSON", "0") == "1"
LOG_FILE = os.environ.get("SMART_PDF_MD_LOG_FILE")
_LEVELS = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}
_LOG_LEVEL_NAME = os.environ.get("SMART_PDF_MD_LOG_LEVEL", "INFO").upper()
LOG_LEVEL = _LEVELS.get(_LOG_LEVEL_NAME, 20)


def set_config(
    *,
    mode: str | None = None,
    images: bool | None = None,
    outdir: str | None = None,
    min_chars: int | None = None,
    min_ratio: float | None = None,
    mock: bool | None = None,
    mock_fail: bool | None = None,
    mock_fail_if_slice_gt: int | None = None,
    log_level: str | None = None,
    dry_run: bool | None = None,
    progress: bool | None = None,
    output_format: str | None = None,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    log_json: bool | None = None,
    log_file: str | None = None,
) -> None:
    """Override runtime configuration values in memory.

    Parameters mirror environment variables used by the CLI and legacy scripts.
    """
    global \
        MODE, \
        IMAGES, \
        OUTDIR, \
        MIN_CHARS, \
        MIN_RATIO, \
        MOCK, \
        MOCK_FAIL, \
        MOCK_FAIL_IF_SLICE_GT, \
        LOG_LEVEL, \
        DRY_RUN, \
        PROGRESS, \
        OUTPUT_FORMAT, \
        INCLUDE, \
        EXCLUDE, \
        LOG_JSON, \
        LOG_FILE
    if mode is not None:
        MODE = mode
    if images is not None:
        IMAGES = images
    if outdir is not None:
        OUTDIR = outdir
    if min_chars is not None:
        MIN_CHARS = int(min_chars)
    if min_ratio is not None:
        MIN_RATIO = float(min_ratio)
    if mock is not None:
        MOCK = mock
    if mock_fail is not None:
        MOCK_FAIL = mock_fail
    if mock_fail_if_slice_gt is not None:
        MOCK_FAIL_IF_SLICE_GT = int(mock_fail_if_slice_gt)
    if log_level is not None:
        lvl = _LEVELS.get(str(log_level).upper())
        if lvl is not None:
            LOG_LEVEL = lvl
    if dry_run is not None:
        DRY_RUN = bool(dry_run)
    if progress is not None:
        PROGRESS = bool(progress)
    if output_format is not None:
        OUTPUT_FORMAT = str(output_format).lower()
    if include is not None:
        INCLUDE = list(include)
    if exclude is not None:
        EXCLUDE = list(exclude)
    if log_json is not None:
        LOG_JSON = bool(log_json)
    if log_file is not None:
        LOG_FILE = log_file


def _maybe_rotate_log_file(path: Path, max_bytes: int = 1_000_000) -> None:
    try:
        if path.exists() and path.stat().st_size > max_bytes:
            backup = path.with_suffix(path.suffix + ".1")
            try:
                backup.unlink()
            except Exception:
                pass
            path.replace(backup)
    except Exception:
        pass


def log(msg: str, level: str = "INFO") -> None:
    """Print a single-line message at a given level if above threshold.

    Emits plain text by default; when LOG_JSON is enabled, emits a JSON line and
    mirrors output to LOG_FILE if configured.
    """
    lv = _LEVELS.get(str(level).upper(), 20)
    if lv < LOG_LEVEL:
        return
    out = msg
    if LOG_JSON:
        import json as _json
        from datetime import datetime, timezone

        out = _json.dumps({
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": level.upper(),
            "message": msg,
        }, ensure_ascii=False)
    print(out, flush=True)
    if LOG_FILE:
        p = Path(LOG_FILE)
        _maybe_rotate_log_file(p)
        try:
            with p.open("a", encoding="utf-8") as fh:
                fh.write(out + "\n")
        except Exception:
            pass


def mock_write_markdown(pdf: str, outdir: str | Path, note: str) -> int:
    """Write a small mock Markdown file for test/mocked runs and return 0."""
    out_path = Path(outdir) / (Path(pdf).stem + ".md")
    prev = out_path.read_text(encoding="utf-8") if out_path.exists() else ""
    text = f"# MOCK MARKER OUTPUT\n{note}\nSource: {pdf}\n"
    out_path.write_text(prev + ("\n\n" if prev else "") + text, encoding="utf-8")
    return 0


def which_marker_single() -> list[str]:
    """Return command to invoke marker's single-file converter.

    Prefers the `marker_single` executable; falls back to `python -m marker...`.
    """
    p = shutil.which("marker_single")
    if p:
        return [p]
    if getattr(sys, "frozen", False):
        env = os.environ.get("SMART_PDF_MD_PYTHON")
        candidates: list[str | None] = [env] if env else []
        base = getattr(sys, "_base_executable", None)
        if base and Path(base).exists():
            candidates.append(base)
        exe = Path(sys.executable)
        candidates += [
            shutil.which("python3"),
            shutil.which("python"),
            shutil.which("py"),
            str(exe.with_name("python")),
            str(exe.with_name("python3")),
        ]
        for c in candidates:
            if c and Path(c).exists():
                return [str(c), "-m", "marker.scripts.convert_single"]
        raise RuntimeError("no Python interpreter found for marker fallback")
    return [sys.executable, "-m", "marker.scripts.convert_single"]


def try_open(pdf: str):  # type: ignore[override]
    """Best-effort open of a PDF via PyMuPDF; returns None on failure."""
    if not fitz:
        log(f"[WARN ] PyMuPDF not installed: {FITZ_IMPORT_ERROR!r}", level="WARNING")
        return None
    try:
        return fitz.open(pdf)
    except Exception as e:  # pragma: no cover - environment-specific
        log(f"[WARN ] PyMuPDF cannot open: {e!r}", level="WARNING")
        return None


def is_textual(
    pdf: str, min_chars_per_page: int | None = None, min_ratio: float | None = None
) -> bool:
    """Heuristic to decide if a PDF likely contains real text pages."""
    if min_chars_per_page is None:
        min_chars_per_page = MIN_CHARS
    if min_ratio is None:
        min_ratio = MIN_RATIO
    doc = try_open(pdf)
    if not doc:
        return False
    try:
        total = len(doc)
        if total == 0:
            return False
        text_pages = 0
        for page in doc:  # type: ignore[assignment]
            t = page.get_text("text")
            if t and len("".join(t.split())) >= min_chars_per_page:
                text_pages += 1
        return (text_pages / total) >= min_ratio
    finally:
        doc.close()


def convert_text(pdf: str, outdir: str | Path) -> int:
    """Extract plain text from each page using PyMuPDF and write Markdown."""
    if DRY_RUN:
        out = Path(outdir) / (Path(pdf).stem + ".md")
        log(f"[DRY  ] would write text to {out}")
        return 0
    if not fitz:
        log(f"[ERROR] PyMuPDF not installed: {FITZ_IMPORT_ERROR!r}", level="ERROR")
        return 1
    t0 = time.perf_counter()
    doc = try_open(pdf)
    if not doc:
        return 1
    try:
        total = len(doc)
        last_pct = -1
        stem = Path(pdf).stem
        ext = ".txt" if OUTPUT_FORMAT == "txt" else ".md"
        out_path = Path(outdir) / (stem + ext)
        with out_path.open("w", encoding="utf-8") as fh:
            for idx, p in enumerate(doc, 1):  # type: ignore[assignment]
                text = p.get_text("text")
                if idx > 1:
                    fh.write("\n\n")
                fh.write(text)
                if PROGRESS and total > 0:
                    pct = int((idx * 100) / total)
                    if pct // 5 != last_pct // 5:
                        log(f"[PROG ] text {idx}/{total} pages ({pct}%)")
                        last_pct = pct
    finally:
        doc.close()
    out = Path(outdir) / (Path(pdf).stem + (".txt" if OUTPUT_FORMAT == "txt" else ".md"))
    log(f"[TEXT ] {pdf} -> {out}  ({time.perf_counter() - t0:.2f}s)")
    return 0


def marker_single_pass(pdf: str, outdir: str | Path) -> int:
    """Execute marker once for all pages, or mock when enabled."""
    if DRY_RUN:
        log(f"[DRY  ] would run marker_single on {pdf} -> {outdir}")
        return 0
    if MOCK:
        if MOCK_FAIL:
            return 1
        return mock_write_markdown(pdf, outdir, "mock marker single-pass")
    ms = which_marker_single()
    cmd = ms + [str(pdf), "--output_format", "markdown"]
    if not IMAGES:
        cmd += ["--disable_image_extraction"]
    cmd += [
        "--page_range",
        "0-999999",
        "--output_dir",
        str(outdir),
        "--lowres_image_dpi",
        str(LOWRES),
        "--highres_image_dpi",
        str(HIGHRES),
    ]
    log(f"[RUN  ] {' '.join(cmd)}")
    return subprocess.run(cmd).returncode  # noqa: S603


def marker_slice(pdf: str, outdir: str | Path, start: int, end: int) -> int:
    """Execute marker for a page slice (inclusive indices), or mock when enabled."""
    if DRY_RUN:
        log(f"[DRY  ] would run marker slice {start}-{end} for {pdf} -> {outdir}")
        return 0
    if MOCK:
        if MOCK_FAIL or (MOCK_FAIL_IF_SLICE_GT and (end - start + 1) > MOCK_FAIL_IF_SLICE_GT):
            return 1
        return mock_write_markdown(pdf, outdir, f"mock marker slice {start}-{end}")
    ms = which_marker_single()
    cmd = ms + [str(pdf), "--output_format", "markdown"]
    if not IMAGES:
        cmd += ["--disable_image_extraction"]
    cmd += [
        "--page_range",
        f"{start}-{end}",
        "--output_dir",
        str(outdir),
        "--lowres_image_dpi",
        str(LOWRES),
        "--highres_image_dpi",
        str(HIGHRES),
    ]
    log(f"[RUN  ] {' '.join(cmd)}")
    return subprocess.run(cmd).returncode  # noqa: S603


def marker_convert(pdf: str, outdir: str | Path, slice_pages: int) -> int:
    """Convert using slice-based backoff; falls back to single-pass on open failure."""
    if DRY_RUN:
        log(f"[DRY  ] would run marker convert (slice={slice_pages}) for {pdf} -> {outdir}")
        return 0
    doc = try_open(pdf)
    if not doc:
        rc = marker_single_pass(pdf, outdir)
        if rc != 0:
            log(f"[ERROR] marker_single rc={rc}", level="ERROR")
            return 3
        log("[OK   ] single-pass done")
        return 0
    total = len(doc)
    doc.close()
    start = 0
    cur = int(slice_pages)
    log(f"[MRK_S] total_pages={total} slice={cur} dpi={LOWRES}/{HIGHRES}")
    done = 0
    while start < total:
        end = min(start + cur - 1, total - 1)
        t0 = time.perf_counter()
        rc = marker_slice(pdf, outdir, start, end)
        dt = time.perf_counter() - t0
        if rc != 0:
            if cur <= 5:
                log(f"[ERROR] slice {start}-{end} failed rc={rc} (min slice)", level="ERROR")
                return 2
            cur = max(5, cur // 2)
            log(f"[WARN ] retry with slice={cur}", level="WARNING")
            continue
        done += end - start + 1
        if PROGRESS and total > 0:
            pct = int((done * 100) / total)
            log(f"[PROG ] slice {start}-{end} ok; {done}/{total} pages ({pct}%) in {dt:.2f}s")
        else:
            log(f"[OK   ] pages {start}-{end} in {dt:.2f}s")
        start = end + 1
    return 0


def _pattern_match(path: Path, patterns: list[str]) -> bool:
    from fnmatch import fnmatch

    s = str(path)
    return any(fnmatch(s, pat) or fnmatch(path.name, pat) for pat in patterns)


def iter_input_files(inp: Path) -> Iterable[Path]:
    """Yield one or many PDF paths depending on input being a file or directory."""
    if inp.exists() and inp.is_dir():
        files = sorted(p for p in inp.rglob("*.pdf"))
        if INCLUDE:
            files = [p for p in files if _pattern_match(p.relative_to(inp), INCLUDE)]
        if EXCLUDE:
            files = [p for p in files if not _pattern_match(p.relative_to(inp), EXCLUDE)]
        log(f"[scan ] folder: {inp}  files={len(files)}")
        return files
    if inp.exists():
        log(f"[scan ] single file: {inp}")
        return [inp]
    log(f"[ERROR] input not found: {inp}", level="ERROR")
    return []


def process_one(pdf: Path, idx: int, total: int, slice_pages: int) -> int:
    """Process a single PDF and return an exit code reflecting the outcome."""
    outdir = Path(OUTDIR) if OUTDIR else pdf.parent
    outdir.mkdir(parents=True, exist_ok=True)
    log("=" * 64)
    log(f"[file ] ({idx}/{total}) {pdf}")
    if DRY_RUN:
        if MODE == "fast":
            log("[DRY  ] mode=fast -> would use PyMuPDF fast path")
        elif MODE == "marker":
            log("[DRY  ] mode=marker -> would use Marker path")
        else:
            log("[DRY  ] mode=auto -> would route based on heuristics (not evaluated in dry-run)")
        return 0
    try:
        if MODE == "fast":
            log("[path ] FORCED FAST -> PyMuPDF")
            return convert_text(str(pdf), str(outdir))
        if MODE == "marker":
            log("[path ] FORCED MARKER -> marker_single")
            return marker_convert(str(pdf), str(outdir), slice_pages)
        if is_textual(str(pdf)):
            log("[path ] TEXTUAL -> fast PyMuPDF")
            return convert_text(str(pdf), str(outdir))
        log("[path ] NON-TEXTUAL -> marker_single")
        return marker_convert(str(pdf), str(outdir), slice_pages)
    except Exception as e:  # pragma: no cover - safety
        log(f"[FALL ] unhandled error: {e!r}", level="ERROR")
        return 9

