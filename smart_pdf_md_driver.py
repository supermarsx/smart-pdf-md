import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import fitz

LOWRES = 96
HIGHRES = 120
MODE = os.environ.get("SMART_PDF_MD_MODE", "auto").lower()
MOCK = os.environ.get("SMART_PDF_MD_MARKER_MOCK", "0") == "1"
MOCK_FAIL = os.environ.get("SMART_PDF_MD_MARKER_MOCK_FAIL", "0") == "1"
IMAGES = os.environ.get("SMART_PDF_MD_IMAGES", "0") == "1"
OUTDIR = os.environ.get("SMART_PDF_MD_OUTPUT_DIR")
MIN_CHARS = int(os.environ.get("SMART_PDF_MD_TEXT_MIN_CHARS", "100"))
MIN_RATIO = float(os.environ.get("SMART_PDF_MD_TEXT_MIN_RATIO", "0.2"))
MOCK_FAIL_IF_SLICE_GT = int(os.environ.get("SMART_PDF_MD_MOCK_FAIL_IF_SLICE_GT", "0"))


def log(msg):
    print(msg, flush=True)


def mock_write_markdown(pdf, outdir, note):
    out = Path(outdir) / (Path(pdf).stem + ".md")
    prev = out.read_text(encoding="utf-8") if out.exists() else ""
    text = f"# MOCK MARKER OUTPUT\n{note}\nSource: {pdf}\n"
    out.write_text(prev + ("\n\n" if prev else "") + text, encoding="utf-8")
    return 0


def which_marker_single():
    p = shutil.which("marker_single")
    return [p] if p else [sys.executable, "-m", "marker.scripts.convert_single"]


def try_open(pdf):
    try:
        return fitz.open(pdf)
    except Exception as e:
        log(f"[WARN ] PyMuPDF cannot open: {e!r}")
        return None


def is_textual(pdf, min_chars_per_page=MIN_CHARS, min_ratio=MIN_RATIO):
    doc = try_open(pdf)
    if not doc or len(doc) == 0:
        return False
    text_pages = 0
    for page in doc:
        t = page.get_text("text")
        if t and len("".join(t.split())) >= min_chars_per_page:
            text_pages += 1
    return (text_pages / len(doc)) >= min_ratio


def convert_text(pdf, outdir):
    t0 = time.perf_counter()
    doc = fitz.open(pdf)
    parts = [p.get_text("text") for p in doc]
    out = Path(outdir) / (Path(pdf).stem + ".md")
    out.write_text("\n\n".join(parts), encoding="utf-8")
    log(f"[TEXT ] {pdf} -> {out}  ({time.perf_counter() - t0:.2f}s)")


def marker_single_pass(pdf, outdir):
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
    return subprocess.run(cmd).returncode


def marker_slice(pdf, outdir, start, end):
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
    return subprocess.run(cmd).returncode


def marker_convert(pdf, outdir, slice_pages):
    doc = try_open(pdf)
    if not doc:
        rc = marker_single_pass(pdf, outdir)
        if rc != 0:
            log(f"[ERROR] marker_single rc={rc}")
            return 3
        log("[OK   ] single-pass done")
        return 0
    total = len(doc)
    doc.close()
    start = 0
    cur = int(slice_pages)
    log(f"[MRK_S] total_pages={total} slice={cur} dpi={LOWRES}/{HIGHRES}")
    while start < total:
        end = min(start + cur - 1, total - 1)
        t0 = time.perf_counter()
        rc = marker_slice(pdf, outdir, start, end)
        dt = time.perf_counter() - t0
        if rc != 0:
            if cur <= 5:
                log(f"[ERROR] slice {start}-{end} failed rc={rc} (min slice)")
                return 2
            cur = max(5, cur // 2)
            log(f"[WARN ] retry with slice={cur}")
            continue
        log(f"[OK   ] pages {start}-{end} in {dt:.2f}s")
        start = end + 1
    return 0


def process_one(pdf, idx, total, slice_pages):
    pdf = Path(pdf)
    outdir = Path(OUTDIR) if OUTDIR else pdf.parent
    outdir.mkdir(parents=True, exist_ok=True)
    log("=" * 64)
    log(f"[file ] ({idx}/{total}) {pdf}")
    try:
        if MODE == "fast":
            log("[path ] FORCED FAST -> PyMuPDF")
            convert_text(str(pdf), str(outdir))
            return 0
        if MODE == "marker":
            log("[path ] FORCED MARKER -> marker_single")
            return marker_convert(str(pdf), str(outdir), slice_pages)
        if is_textual(str(pdf)):
            log("[path ] TEXTUAL -> fast PyMuPDF")
            convert_text(str(pdf), str(outdir))
            return 0
        log("[path ] NON-TEXTUAL -> marker_single")
        return marker_convert(str(pdf), str(outdir), slice_pages)
    except Exception as e:
        log(f"[FALL ] unhandled error: {e!r}")
        return 9


def main():
    if len(sys.argv) < 3:
        log("[USAGE] smart_pdf_md_driver.py INPUT SLICE")
        sys.exit(2)
    inp = Path(sys.argv[1])
    slice_pages = int(sys.argv[2])
    if inp.exists() and inp.is_dir():
        files = sorted([p for p in inp.rglob("*.pdf")])
        log(f"[scan ] folder: {inp}  files={len(files)}")
    elif inp.exists():
        files = [inp]
        log(f"[scan ] single file: {inp}")
    else:
        log(f"[ERROR] input not found: {inp}")
        sys.exit(1)
    t0 = time.perf_counter()
    fails = 0
    exit_code = 0
    for i, f in enumerate(files, 1):
        try:
            rc = process_one(f, i, len(files), slice_pages)
        except Exception as e:
            log(f"[CRASH] {f}: {e!r}")
            rc = 10
        if rc != 0:
            fails += 1
            if exit_code == 0:
                exit_code = rc
    log(f"[DONE ] total={len(files)} failures={fails} elapsed={time.perf_counter() - t0:.2f}s")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
