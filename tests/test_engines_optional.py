import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


def make_text_pdf(path: Path, text: str = "Hello") -> None:
    import fitz  # type: ignore

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=12)
    doc.save(path)
    doc.close()


def run_cli(args: list[str], *, env: dict | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, "-m", "smart_pdf_md"] + args
    proc_env = os.environ.copy()
    if env:
        proc_env.update(env)
    return subprocess.run(cmd, env=proc_env, capture_output=True, text=True)


@pytest.mark.parametrize(
    "engine, import_name",
    [
        ("pdfminer", "pdfminer.high_level"),
        ("pdfplumber", "pdfplumber"),
        ("layout", "pymupdf4llm"),
        ("docling", "docling.document_converter"),
    ],
)
def test_python_engine_if_installed(tmp_path: Path, engine: str, import_name: str) -> None:
    pytest.importorskip(import_name)
    pdf = tmp_path / "e.pdf"
    make_text_pdf(pdf, "Engine Test")
    res = run_cli([str(pdf), "40", "-e", engine])
    assert res.returncode == 0, res.stdout + "\n" + res.stderr
    md = tmp_path / "e.md"
    assert md.exists()


def test_poppler_engine_if_available(tmp_path: Path) -> None:
    if shutil.which("pdftohtml") is None:
        pytest.skip("pdftohtml not available")
    pytest.importorskip("markdownify")
    pdf = tmp_path / "p.pdf"
    make_text_pdf(pdf, "Poppler Test")
    res = run_cli([str(pdf), "40", "-e", "poppler"])  # writes .md
    assert res.returncode == 0, res.stdout + "\n" + res.stderr
    md = tmp_path / "p.md"
    assert md.exists()


def test_ocrmypdf_engine_if_available(tmp_path: Path) -> None:
    if shutil.which("ocrmypdf") is None:
        pytest.skip("ocrmypdf not available")
    pdf = tmp_path / "o.pdf"
    make_text_pdf(pdf, "OCR Test")
    res = run_cli([str(pdf), "40", "-e", "ocrmypdf"])  # fast path after OCR
    assert res.returncode == 0, res.stdout + "\n" + res.stderr
    md = tmp_path / "o.md"
    assert md.exists()


def test_tables_stream_if_installed(tmp_path: Path) -> None:
    camelot = pytest.importorskip("camelot")  # noqa: F841
    pdf = tmp_path / "t.pdf"
    make_text_pdf(pdf, "A,B\n1,2\n3,4")
    res = run_cli([str(pdf), "40", "-m", "fast", "--tables", "--tables-mode", "stream"])
    assert res.returncode == 0, res.stdout + "\n" + res.stderr
    # Tables may or may not be detected reliably; just ensure no crash.


def test_lattice_engine_alias_if_installed(tmp_path: Path) -> None:
    camelot = pytest.importorskip("camelot")  # noqa: F841
    # Ghostscript is required for lattice; skip if not present
    if shutil.which("gs") is None and shutil.which("gswin64c") is None:
        pytest.skip("Ghostscript not available for lattice mode")
    pdf = tmp_path / "l.pdf"
    # Draw grid lines to help lattice detection
    import fitz  # type: ignore

    doc = fitz.open()
    page = doc.new_page()
    page.draw_line((72, 120), (300, 120))
    page.draw_line((72, 160), (300, 160))
    page.draw_line((72, 200), (300, 200))
    page.draw_line((72, 120), (72, 200))
    page.draw_line((186, 120), (186, 200))
    page.draw_line((300, 120), (300, 200))
    page.insert_text((80, 110), "H1  H2", fontsize=12)
    doc.save(pdf)
    doc.close()
    res = run_cli([str(pdf), "40", "-e", "lattice", "--tables"])
    assert res.returncode == 0, res.stdout + "\n" + res.stderr
    # Prefer that a tables file was generated; tolerate absence (layout-dependent)
    tables_md = tmp_path / "l.tables.md"
    if not tables_md.exists():
        pytest.xfail("lattice tables not detected; environment-dependent")


def test_engine_env_override_fast(tmp_path: Path) -> None:
    pdf = tmp_path / "env.pdf"
    make_text_pdf(pdf, "Env Engine Test")
    res = run_cli([str(pdf), "40"], env={"SMART_PDF_MD_ENGINE": "fast"})
    assert res.returncode == 0, res.stdout + "\n" + res.stderr
