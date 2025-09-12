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
from typing import Any, Iterable

FITZ_IMPORT_ERROR: Exception | None = None
fitz: Any | None
try:  # PyMuPDF is optional for build environments
    import fitz as _fitz

    fitz = _fitz
except Exception as e:  # pragma: no cover - best effort
    fitz = None
    FITZ_IMPORT_ERROR = e


LOWRES = 96
HIGHRES = 120
# Configurable globals (overridable via set_config)
MODE = os.environ.get("SMART_PDF_MD_MODE", "auto").lower()
ENGINE = os.environ.get("SMART_PDF_MD_ENGINE")
ENGINE_TEXTUAL = os.environ.get("SMART_PDF_MD_ENGINE_TEXTUAL")
ENGINE_NON_TEXTUAL = os.environ.get("SMART_PDF_MD_ENGINE_NON_TEXTUAL")
TABLES = os.environ.get("SMART_PDF_MD_TABLES", "0") == "1"
TABLES_FLAVOR = os.environ.get("SMART_PDF_MD_TABLES_FLAVOR", "stream").lower()
MOCK = os.environ.get("SMART_PDF_MD_MARKER_MOCK", "0") == "1"
MOCK_FAIL = os.environ.get("SMART_PDF_MD_MARKER_MOCK_FAIL", "0") == "1"
IMAGES = os.environ.get("SMART_PDF_MD_IMAGES", "0") == "1"
OUTDIR = os.environ.get("SMART_PDF_MD_OUTPUT_DIR")
MIN_CHARS = int(os.environ.get("SMART_PDF_MD_TEXT_MIN_CHARS", "10"))
MIN_RATIO = float(os.environ.get("SMART_PDF_MD_TEXT_MIN_RATIO", "0.2"))
MOCK_FAIL_IF_SLICE_GT = int(os.environ.get("SMART_PDF_MD_MOCK_FAIL_IF_SLICE_GT", "0"))
DRY_RUN = os.environ.get("SMART_PDF_MD_DRY_RUN", "0") == "1"
PROGRESS = os.environ.get("SMART_PDF_MD_PROGRESS", "0") == "1"
RESUME = os.environ.get("SMART_PDF_MD_RESUME", "0") == "1"
OUTPUT_FORMAT = os.environ.get("SMART_PDF_MD_OUTPUT_FORMAT", "md").lower()
INCLUDE: list[str] = []
EXCLUDE: list[str] = []
LOG_JSON = os.environ.get("SMART_PDF_MD_LOG_JSON", "0") == "1"
LOG_FILE = os.environ.get("SMART_PDF_MD_LOG_FILE")
_LEVELS = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}
_LOG_LEVEL_NAME = os.environ.get("SMART_PDF_MD_LOG_LEVEL", "INFO").upper()
LOG_LEVEL = _LEVELS.get(_LOG_LEVEL_NAME, 20)
MARKER_TIMEOUT = int(os.environ.get("SMART_PDF_MD_MARKER_TIMEOUT", "0"))
MARKER_RETRIES = int(os.environ.get("SMART_PDF_MD_MARKER_RETRIES", "0"))


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
    engine: str | None = None,
    engine_textual: str | None = None,
    engine_non_textual: str | None = None,
    tables: bool | None = None,
    tables_flavor: str | None = None,
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
        LOG_FILE, \
        ENGINE, \
        ENGINE_TEXTUAL, \
        ENGINE_NON_TEXTUAL, \
        TABLES, \
        TABLES_FLAVOR
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
    if engine is not None:
        ENGINE = engine
    if engine_textual is not None:
        ENGINE_TEXTUAL = engine_textual
    if engine_non_textual is not None:
        ENGINE_NON_TEXTUAL = engine_non_textual
    if tables is not None:
        TABLES = bool(tables)
    if tables_flavor is not None:
        TABLES_FLAVOR = str(tables_flavor).lower()
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

        out = _json.dumps(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "level": level.upper(),
                "message": msg,
            },
            ensure_ascii=False,
        )
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


def try_open(pdf: str):
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
        for page in doc:
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
            for idx, p in enumerate(doc, 1):
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


def _ensure_exec(name: str) -> str | None:
    """Return executable path if found in PATH, else None."""
    from shutil import which

    return which(name)


def convert_via_poppler(pdf: str, outdir: str | Path) -> int:
    """Convert using Poppler's pdftohtml and markdownify.

    Requires `pdftohtml` to be available on PATH and the Python package
    `markdownify` (optional extra). Falls back with an error if missing.
    """
    exe = _ensure_exec("pdftohtml")
    if not exe:
        log("[ERROR] pdftohtml not found in PATH (install Poppler)", level="ERROR")
        return 4
    try:
        import markdownify
    except Exception:
        log("[ERROR] python package 'markdownify' not installed", level="ERROR")
        return 4
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        html_path = Path(td) / "out.html"
        cmd = [exe, "-s", "-i", "-q", "-noframes", str(pdf), str(html_path)]
        log(f"[RUN  ] {' '.join(cmd)}")
        rc = subprocess.run(cmd).returncode  # noqa: S603
        if rc != 0:
            log(f"[ERROR] pdftohtml rc={rc}", level="ERROR")
            return 4
        html = html_path.read_text(encoding="utf-8", errors="ignore")
        md = markdownify.markdownify(html, heading_style="ATX")
    out = Path(outdir) / (Path(pdf).stem + ".md")
    out.write_text(md, encoding="utf-8")
    log(f"[OK   ] poppler-html2md {pdf} -> {out}")
    return 0


def convert_via_pdfminer(pdf: str, outdir: str | Path) -> int:
    """Convert using pdfminer.six high-level text extraction."""
    try:
        from pdfminer.high_level import extract_text
    except Exception:
        log("[ERROR] python package 'pdfminer.six' not installed", level="ERROR")
        return 4
    text = extract_text(pdf) or ""
    out = Path(outdir) / (Path(pdf).stem + (".txt" if OUTPUT_FORMAT == "txt" else ".md"))
    out.write_text(text, encoding="utf-8")
    log(f"[OK   ] pdfminer {pdf} -> {out}")
    return 0


def convert_via_pdfplumber(pdf: str, outdir: str | Path) -> int:
    """Convert using pdfplumber page-wise text extraction."""
    try:
        import pdfplumber
    except Exception:
        log("[ERROR] python package 'pdfplumber' not installed", level="ERROR")
        return 4
    parts: list[str] = []
    with pdfplumber.open(pdf) as doc:
        for page in doc.pages:
            txt = page.extract_text() or ""
            parts.append(txt)
    text = "\n\n".join(parts)
    out = Path(outdir) / (Path(pdf).stem + (".txt" if OUTPUT_FORMAT == "txt" else ".md"))
    out.write_text(text, encoding="utf-8")
    log(f"[OK   ] pdfplumber {pdf} -> {out}")
    return 0


def convert_via_ocrmypdf(pdf: str, outdir: str | Path) -> int:
    """Convert with OCRmyPDF to add a text layer, then fast convert.

    Requires `ocrmypdf` CLI (and system Tesseract). If successful, routes
    the OCRed PDF through the fast PyMuPDF text converter.
    """
    exe = _ensure_exec("ocrmypdf")
    if not exe:
        log("[ERROR] ocrmypdf not found in PATH (install OCRmyPDF/Tesseract)", level="ERROR")
        return 4
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        ocr_pdf = Path(td) / "ocr.pdf"
        cmd = [exe, "--skip-text", "--quiet", str(pdf), str(ocr_pdf)]
        log(f"[RUN  ] {' '.join(cmd)}")
        rc = subprocess.run(cmd).returncode  # noqa: S603
        if rc != 0 or not ocr_pdf.exists():
            log(f"[ERROR] ocrmypdf rc={rc}", level="ERROR")
            return 4
        rc = convert_text(str(ocr_pdf), str(outdir))
        if rc == 0:
            ext = ".txt" if OUTPUT_FORMAT == "txt" else ".md"
            src = Path(outdir) / (ocr_pdf.stem + ext)
            dst = Path(outdir) / (Path(pdf).stem + ext)
            if src != dst:
                try:
                    src.replace(dst)
                except Exception:
                    pass
        return rc


def convert_via_layout(pdf: str, outdir: str | Path) -> int:
    """Convert using PyMuPDF4LLM to Markdown (layout-aware)."""
    try:
        from pymupdf4llm import to_markdown
    except Exception:
        log("[ERROR] python package 'pymupdf4llm' not installed", level="ERROR")
        return 4
    if not fitz:
        log("[ERROR] PyMuPDF not available for layout engine", level="ERROR")
        return 4
    doc = try_open(pdf)
    if not doc:
        return 4
    try:
        md = to_markdown(doc)
    finally:
        try:
            doc.close()
        except Exception:
            pass
    out = Path(outdir) / (Path(pdf).stem + ".md")
    out.write_text(md, encoding="utf-8")
    log(f"[OK   ] layout(PyMuPDF4LLM) {pdf} -> {out}")
    return 0


def extract_tables_to_md(pdf: str, outdir: str | Path, *, flavor: str | None = None) -> None:
    """Best-effort table extraction to Markdown using camelot (stream).

    Writes a sibling file '<stem>.tables.md' when tables are found.
    Fails silently with warnings (does not change exit code).
    """
    if not TABLES:
        return
    try:
        import camelot
    except Exception:
        log("[WARN ] --tables set but 'camelot-py' not installed", level="WARNING")
        return
    mode = (flavor or TABLES_FLAVOR or "stream").lower()
    tables = None

    def _read(fl: str):
        return camelot.read_pdf(pdf, pages="all", flavor=fl)

    try:
        if mode == "auto":
            try:
                tables = _read("lattice")
            except Exception as _e1:  # noqa: F841
                try:
                    tables = _read("stream")
                except Exception as _e2:  # noqa: F841
                    tables = None
        else:
            tables = _read(mode)
    except Exception as e:  # pragma: no cover - environment-dependent
        log(f"[WARN ] camelot.read_pdf({mode}) failed: {e!r}", level="WARNING")
        tables = None
    if not tables or getattr(tables, "n", 0) == 0:
        log("[info ] no tables detected by camelot")
        return
    parts: list[str] = [f"# Tables extracted from {Path(pdf).name}"]
    for i in range(getattr(tables, "n", 0)):
        try:
            t = tables[i]
            df = t.df  # pandas DataFrame
            md = df.to_markdown(index=False)
            parts.append(f"\n\n## Table {i + 1}\n\n{md}")
        except Exception:
            continue
    if len(parts) > 1:
        out = Path(outdir) / (Path(pdf).stem + ".tables.md")
        out.write_text("".join(parts), encoding="utf-8")
        log(f"[OK   ] tables -> {out}")


def convert_via_pypdf(pdf: str, outdir: str | Path) -> int:
    try:
        from pypdf import PdfReader
    except Exception:
        log("[ERROR] python package 'pypdf' not installed", level="ERROR")
        return 4
    try:
        reader = PdfReader(pdf)
    except Exception as e:
        log(f"[ERROR] pypdf cannot open: {e!r}", level="ERROR")
        return 4
    texts: list[str] = []
    for page in reader.pages:
        try:
            t = page.extract_text() or ""
        except Exception:
            t = ""
        texts.append(t)
    text = "\n\n".join(texts)
    out = Path(outdir) / (Path(pdf).stem + (".txt" if OUTPUT_FORMAT == "txt" else ".md"))
    out.write_text(text, encoding="utf-8")
    log(f"[OK   ] pypdf {pdf} -> {out}")
    return 0


def convert_via_pypdfium2(pdf: str, outdir: str | Path) -> int:
    try:
        import pypdfium2 as pdfium
    except Exception:
        log("[ERROR] python package 'pypdfium2' not installed", level="ERROR")
        return 4
    try:
        doc = pdfium.PdfDocument(pdf)
    except Exception as e:
        log(f"[ERROR] pypdfium2 cannot open: {e!r}", level="ERROR")
        return 4
    parts: list[str] = []
    try:
        for i in range(len(doc)):
            page = doc[i]
            textpage = page.get_textpage()
            try:
                txt = textpage.get_text_range(0, textpage.count_chars()) or ""
            except Exception:
                txt = textpage.get_text_bounded() or ""  # fallback
            parts.append(txt)
    finally:
        try:
            doc.close()
        except Exception:
            pass
    out = Path(outdir) / (Path(pdf).stem + (".txt" if OUTPUT_FORMAT == "txt" else ".md"))
    out.write_text("\n\n".join(parts), encoding="utf-8")
    log(f"[OK   ] pypdfium2 {pdf} -> {out}")
    return 0


def convert_via_pytesseract(pdf: str, outdir: str | Path) -> int:
    try:
        from pdf2image import convert_from_path
        from PIL import Image  # noqa: F401
        import pytesseract
    except Exception:
        log("[ERROR] packages 'pdf2image', 'Pillow', and 'pytesseract' required", level="ERROR")
        return 4
    try:
        images = convert_from_path(pdf)
    except Exception as e:
        log(f"[ERROR] pdf2image failed: {e!r}", level="ERROR")
        return 4
    parts: list[str] = []
    for img in images:
        try:
            parts.append(pytesseract.image_to_string(img))
        except Exception:
            parts.append("")
    out = Path(outdir) / (Path(pdf).stem + ".md")
    out.write_text("\n\n".join(parts), encoding="utf-8")
    log(f"[OK   ] pytesseract {pdf} -> {out}")
    return 0


def convert_via_doctr(pdf: str, outdir: str | Path) -> int:
    try:
        from doctr.io import DocumentFile
        from doctr.models import ocr_predictor
    except Exception:
        log("[ERROR] python package 'python-doctr' not installed", level="ERROR")
        return 4
    try:
        doc = DocumentFile.from_pdf(pdf)
        model = ocr_predictor(pretrained=True)
        result = model(doc)
        # Export to Markdown-like text from dict
        export = result.export()
        blocks: list[str] = []
        for page in export.get("pages", []) or []:
            for block in page.get("blocks", []) or []:
                for line in block.get("lines", []) or []:
                    words = [w.get("value", "") for w in (line.get("words", []) or [])]
                    blocks.append(" ".join(words))
        text = "\n".join(blocks)
    except Exception as e:  # pragma: no cover - heavy model
        log(f"[ERROR] doctr OCR failed: {e!r}", level="ERROR")
        return 4
    out = Path(outdir) / (Path(pdf).stem + ".md")
    out.write_text(text, encoding="utf-8")
    log(f"[OK   ] doctr {pdf} -> {out}")
    return 0


def convert_via_unstructured(pdf: str, outdir: str | Path) -> int:
    try:
        from unstructured.partition.pdf import partition_pdf
    except Exception:
        log("[ERROR] python package 'unstructured' not installed", level="ERROR")
        return 4
    try:
        elements = partition_pdf(filename=pdf)
    except Exception as e:
        log(f"[ERROR] unstructured failed: {e!r}", level="ERROR")
        return 4
    text = "\n\n".join([getattr(el, "text", "") or "" for el in elements])
    out = Path(outdir) / (Path(pdf).stem + ".md")
    out.write_text(text, encoding="utf-8")
    log(f"[OK   ] unstructured {pdf} -> {out}")
    return 0


def convert_via_tabula(pdf: str, outdir: str | Path) -> int:
    try:
        import tabula
        import pandas as pd  # noqa: F401
    except Exception:
        log("[ERROR] packages 'tabula-py' and 'pandas' required", level="ERROR")
        return 4
    try:
        dfs = tabula.read_pdf(pdf, pages="all", lattice=True)
    except Exception as e:
        log(f"[ERROR] tabula.read_pdf failed: {e!r}", level="ERROR")
        return 4
    parts: list[str] = [f"# Tables extracted from {Path(pdf).name}"]
    for i, df in enumerate(dfs or [], 1):
        try:
            parts.append(f"\n\n## Table {i}\n\n{df.to_markdown(index=False)}")
        except Exception:
            continue
    out = Path(outdir) / (Path(pdf).stem + ".md")
    out.write_text("".join(parts), encoding="utf-8")
    log(f"[OK   ] tabula {pdf} -> {out}")
    return 0


def convert_via_grobid(pdf: str, outdir: str | Path) -> int:
    url = os.environ.get("GROBID_URL")
    if not url:
        log("[ERROR] set GROBID_URL to your grobid server base URL", level="ERROR")
        return 4
    try:
        import requests  # type: ignore[import-untyped]
        import xml.etree.ElementTree as ET
    except Exception:
        log("[ERROR] python package 'requests' required for grobid engine", level="ERROR")
        return 4
    try:
        with open(pdf, "rb") as fh:
            files = {"input": (Path(pdf).name, fh, "application/pdf")}
            resp = requests.post(
                url.rstrip("/") + "/api/processFulltextDocument", files=files, timeout=120
            )
        if resp.status_code != 200:
            log(f"[ERROR] grobid http {resp.status_code}", level="ERROR")
            return 4
        tei = resp.text
    except Exception as e:
        log(f"[ERROR] grobid request failed: {e!r}", level="ERROR")
        return 4
    # Write TEI alongside and produce a minimal markdown from paragraphs
    tei_path = Path(outdir) / (Path(pdf).stem + ".tei.xml")
    tei_path.write_text(tei, encoding="utf-8")
    try:
        root = ET.fromstring(tei)
        ns = {"tei": root.tag.split("}")[0].strip("{") if "}" in root.tag else ""}
        paras = []
        for p in root.findall(".//tei:p", ns) if ns.get("tei") else root.findall(".//p"):
            paras.append("".join(p.itertext()).strip())
        md = "\n\n".join(paras) if paras else f"(See {tei_path.name})"
    except Exception:
        md = f"(See {tei_path.name})"
    out = Path(outdir) / (Path(pdf).stem + ".md")
    out.write_text(md, encoding="utf-8")
    log(f"[OK   ] grobid {pdf} -> {out}")
    return 0


def convert_via_pdfx(pdf: str, outdir: str | Path) -> int:
    try:
        import pdfx
    except Exception:
        log("[ERROR] python package 'pdfx' not installed", level="ERROR")
        return 4
    try:
        px = pdfx.PDFx(pdf)
        refs: dict[str, list[str]] = {}
        try:
            refs = px.get_references() or {}
        except Exception:
            refs = {}
        parts: list[str] = []
        if refs:
            parts.append(f"# References extracted from {Path(pdf).name}\n")
            for k in sorted(refs.keys()):
                vals = refs.get(k) or []
                if not vals:
                    continue
                parts.append(f"\n## {k}\n")
                for v in vals:
                    parts.append(f"- {v}\n")
        if not parts:
            # Fallback to pdfminer text extraction when no refs gathered
            return convert_via_pdfminer(pdf, outdir)
        out = Path(outdir) / (Path(pdf).stem + ".md")
        out.write_text("".join(parts), encoding="utf-8")
        log(f"[OK   ] pdfx {pdf} -> {out}")
        return 0
    except Exception as e:
        log(f"[ERROR] pdfx failed: {e!r}", level="ERROR")
        return 4


def convert_via_ghostscript(pdf: str, outdir: str | Path) -> int:
    exe = _ensure_exec("gs") or _ensure_exec("gswin64c") or _ensure_exec("gswin32c")
    if not exe:
        log("[ERROR] ghostscript executable not found (gs/gswin64c)", level="ERROR")
        return 4
    # Use txtwrite device to dump plain text to stdout
    cmd = [
        exe,
        "-q",
        "-dNOPAUSE",
        "-dBATCH",
        "-sDEVICE=txtwrite",
        "-sOutputFile=-",
        str(pdf),
    ]
    log(f"[RUN  ] {' '.join(cmd)}")
    try:
        proc = subprocess.run(cmd, capture_output=True)  # noqa: S603
        if proc.returncode != 0:
            log(f"[ERROR] ghostscript rc={proc.returncode}", level="ERROR")
            return 4
        data = proc.stdout
        try:
            text = data.decode("utf-8")
        except Exception:
            text = data.decode("latin-1", errors="ignore")
        out = Path(outdir) / (Path(pdf).stem + (".txt" if OUTPUT_FORMAT == "txt" else ".md"))
        out.write_text(text, encoding="utf-8")
        log(f"[OK   ] ghostscript {pdf} -> {out}")
        return 0
    except Exception as e:
        log(f"[ERROR] ghostscript failed: {e!r}", level="ERROR")
        return 4


def convert_via_borb(pdf: str, outdir: str | Path) -> int:
    try:
        # Prefer borb text extraction if available
        from borb.toolkit.text.simple_text_extraction import SimpleTextExtraction
        from borb.pdf import PDF
    except Exception:
        # Fallback via pypdf engine
        log("[WARN ] 'borb' not installed; falling back to pypdf", level="WARNING")
        return convert_via_pypdf(pdf, outdir)
    try:
        # borb API: PDF.loads returns Document; using in-memory loader
        with open(pdf, "rb") as fh:
            doc = PDF.loads(fh)
        ste = SimpleTextExtraction()
        texts: list[str] = []
        for page in doc.get_pages():
            try:
                ste.reset()
                ste.extract(page)
                texts.append(ste.get_text())
            except Exception:
                texts.append("")
        out = Path(outdir) / (Path(pdf).stem + (".txt" if OUTPUT_FORMAT == "txt" else ".md"))
        out.write_text("\n\n".join(texts), encoding="utf-8")
        log(f"[OK   ] borb {pdf} -> {out}")
        return 0
    except Exception as e:
        log(f"[ERROR] borb extraction failed: {e!r}", level="ERROR")
        return 4


def convert_via_pdfrw(pdf: str, outdir: str | Path) -> int:
    try:
        import pdfrw  # noqa: F401
    except Exception:
        log("[WARN ] 'pdfrw' not installed; falling back to pypdf", level="WARNING")
        return convert_via_pypdf(pdf, outdir)
    # pdfrw does not provide robust text extraction; use pypdf as a fallback strategy
    return convert_via_pypdf(pdf, outdir)


def convert_via_pdfquery(pdf: str, outdir: str | Path) -> int:
    # pdfquery builds on pdfminer; use pdfminer extraction for plain text
    try:
        from pdfminer.high_level import extract_text
    except Exception:
        log("[ERROR] 'pdfminer.six' not installed for pdfquery engine", level="ERROR")
        return 4
    try:
        text = extract_text(pdf) or ""
    except Exception as e:
        log(f"[ERROR] pdfquery/pdfminer failed: {e!r}", level="ERROR")
        return 4
    out = Path(outdir) / (Path(pdf).stem + (".txt" if OUTPUT_FORMAT == "txt" else ".md"))
    out.write_text(text, encoding="utf-8")
    log(f"[OK   ] pdfquery {pdf} -> {out}")
    return 0


def convert_via_easyocr(pdf: str, outdir: str | Path) -> int:
    try:
        from pdf2image import convert_from_path
        from PIL import Image  # noqa: F401
        import easyocr
    except Exception:
        log("[ERROR] packages 'easyocr', 'pdf2image', and 'Pillow' required", level="ERROR")
        return 4
    try:
        images = convert_from_path(pdf)
    except Exception as e:
        log(f"[ERROR] pdf2image failed: {e!r}", level="ERROR")
        return 4
    reader = None
    try:
        reader = easyocr.Reader(["en"], gpu=False)
    except Exception as e:
        log(f"[ERROR] easyocr init failed: {e!r}", level="ERROR")
        return 4
    lines: list[str] = []
    for img in images:
        try:
            result = reader.readtext(img)
            for _bbox, text, _conf in result:
                lines.append(text)
        except Exception:
            continue
    out = Path(outdir) / (Path(pdf).stem + ".md")
    out.write_text("\n".join(lines), encoding="utf-8")
    log(f"[OK   ] easyocr {pdf} -> {out}")
    return 0


def convert_via_kraken(pdf: str, outdir: str | Path) -> int:
    try:
        from pdf2image import convert_from_path
        from PIL import Image  # noqa: F401
    except Exception:
        log("[ERROR] packages 'pdf2image' and 'Pillow' required for kraken", level="ERROR")
        return 4
    exe = _ensure_exec("kraken")
    if not exe:
        log("[ERROR] 'kraken' CLI not found in PATH", level="ERROR")
        return 4
    import tempfile

    try:
        images = convert_from_path(pdf)
    except Exception as e:
        log(f"[ERROR] pdf2image failed: {e!r}", level="ERROR")
        return 4
    texts: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        for i, img in enumerate(images):
            img_path = Path(td) / f"p{i}.png"
            txt_path = Path(td) / f"p{i}.txt"
            try:
                img.save(img_path)
                # kraken -i image.png image.txt (default segmentation + recognition)
                rc = subprocess.run([exe, "-i", str(img_path), str(txt_path)]).returncode  # noqa: S603
                if rc == 0 and txt_path.exists():
                    texts.append(txt_path.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                continue
    out = Path(outdir) / (Path(pdf).stem + ".md")
    out.write_text("\n\n".join(texts), encoding="utf-8")
    log(f"[OK   ] kraken {pdf} -> {out}")
    return 0


def _run_with_tables(pdf: str, outdir: str | Path, fn: Any, *, flavor: str | None = None) -> int:
    # Call the provided engine runner and, on success, extract tables when requested.
    rc = int(fn(str(pdf), str(outdir)))
    if rc == 0 and TABLES:
        extract_tables_to_md(str(pdf), str(outdir), flavor=flavor)
    return rc


def convert_via_docling(pdf: str, outdir: str | Path) -> int:
    """Convert using IBM Docling to Markdown.

    Requires the `docling` package. Produces markdown via Docling's converter.
    """
    try:
        from docling.document_converter import DocumentConverter
    except ImportError:
        log("[ERROR] python package 'docling' not installed", level="ERROR")
        return 4
    except Exception as e:  # pragma: no cover - best effort
        log(f"[ERROR] docling import failed: {e!r}", level="ERROR")
        return 4
    try:
        conv = DocumentConverter()
        res = conv.convert(str(pdf))
        md = res.document.export_to_markdown()
    except Exception as e:  # pragma: no cover - best effort
        log(f"[ERROR] docling conversion failed: {e!r}", level="ERROR")
        return 4
    out = Path(outdir) / (Path(pdf).stem + ".md")
    out.write_text(md, encoding="utf-8")
    log(f"[OK   ] docling {pdf} -> {out}")
    return 0


def _run_engine_by_name(eng: str, pdf: str, outdir: str | Path, slice_pages: int) -> int:
    e = eng.lower()
    if e in ("pymupdf", "fast"):
        return _run_with_tables(pdf, outdir, convert_text)
    if e in ("marker",):
        rc = marker_convert(str(pdf), str(outdir), slice_pages)
        if rc == 0 and TABLES:
            extract_tables_to_md(str(pdf), str(outdir))
        return rc
    if e in ("poppler", "poppler-html2md", "html2md"):
        return _run_with_tables(pdf, outdir, convert_via_poppler)
    if e in ("pdfminer", "pdfminer.six"):
        return _run_with_tables(pdf, outdir, convert_via_pdfminer)
    if e in ("pdfplumber",):
        return _run_with_tables(pdf, outdir, convert_via_pdfplumber)
    if e in ("ocrmypdf", "ocr"):
        rc = convert_via_ocrmypdf(str(pdf), str(outdir))
        if rc == 0 and TABLES:
            extract_tables_to_md(str(pdf), str(outdir))
        return rc
    if e in ("docling",):
        return _run_with_tables(pdf, outdir, convert_via_docling)
    if e in ("layout", "pymupdf4llm"):
        return _run_with_tables(pdf, outdir, convert_via_layout)
    if e in ("lattice", "camelot-lattice"):
        return _run_with_tables(pdf, outdir, convert_text, flavor="lattice")
    if e in ("pypdf",):
        return _run_with_tables(pdf, outdir, convert_via_pypdf)
    if e in ("pypdfium2",):
        return _run_with_tables(pdf, outdir, convert_via_pypdfium2)
    if e in ("pytesseract", "tesseract"):
        return _run_with_tables(pdf, outdir, convert_via_pytesseract)
    if e in ("unstructured",):
        return _run_with_tables(pdf, outdir, convert_via_unstructured)
    # pdftotree engine removed
    if e in ("tabula", "tabula-py"):
        return _run_with_tables(pdf, outdir, convert_via_tabula)
    if e in ("grobid",):
        return _run_with_tables(pdf, outdir, convert_via_grobid)
    if e in ("pdfx",):
        return _run_with_tables(pdf, outdir, convert_via_pdfx)
    if e in ("ghostscript", "gs"):
        return _run_with_tables(pdf, outdir, convert_via_ghostscript)
    if e in ("borb",):
        return _run_with_tables(pdf, outdir, convert_via_borb)
    if e in ("pdfrw",):
        return _run_with_tables(pdf, outdir, convert_via_pdfrw)
    if e in ("pdfquery",):
        return _run_with_tables(pdf, outdir, convert_via_pdfquery)
    if e in ("easyocr",):
        return _run_with_tables(pdf, outdir, convert_via_easyocr)
    if e in ("kraken",):
        return _run_with_tables(pdf, outdir, convert_via_kraken)
    log(f"[ERROR] unknown engine: {eng}", level="ERROR")
    return 9


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
    import os as _os

    # Normalize to forward slashes for cross-platform consistency with docs/examples
    s_full = str(path).replace(_os.sep, "/")
    s_name = path.name
    for pat in patterns:
        p = pat.replace("\\", "/").replace(_os.sep, "/")
        if fnmatch(s_full, p) or fnmatch(s_name, p):
            return True
    return False


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
        # Forced engine overrides mode/heuristics when provided
        if ENGINE:
            eng = ENGINE.lower()
            log(f"[eng  ] FORCED ENGINE -> {eng}")
            return _run_engine_by_name(eng, str(pdf), str(outdir), slice_pages)
        if MODE == "fast":
            log("[path ] FORCED FAST -> PyMuPDF")
            return _run_with_tables(str(pdf), str(outdir), convert_text)
        if MODE == "marker":
            log("[path ] FORCED MARKER -> marker_single")
            rc = marker_convert(str(pdf), str(outdir), slice_pages)
            if rc == 0 and TABLES:
                extract_tables_to_md(str(pdf), str(outdir))
            return rc
        if is_textual(str(pdf)):
            # Auto textual routing; allow override engine for textual category
            if ENGINE_TEXTUAL:
                log(f"[path ] TEXTUAL -> engine={ENGINE_TEXTUAL}")
                return _run_engine_by_name(ENGINE_TEXTUAL, str(pdf), str(outdir), slice_pages)
            log("[path ] TEXTUAL -> fast PyMuPDF")
            return _run_with_tables(str(pdf), str(outdir), convert_text)
        # Non-textual
        if ENGINE_NON_TEXTUAL:
            log(f"[path ] NON-TEXTUAL -> engine={ENGINE_NON_TEXTUAL}")
            return _run_engine_by_name(ENGINE_NON_TEXTUAL, str(pdf), str(outdir), slice_pages)
        log("[path ] NON-TEXTUAL -> marker_single")
        rc = marker_convert(str(pdf), str(outdir), slice_pages)
        if rc == 0 and TABLES:
            extract_tables_to_md(str(pdf), str(outdir))
        return rc
    except Exception as e:  # pragma: no cover - safety
        log(f"[FALL ] unhandled error: {e!r}", level="ERROR")
        return 9
