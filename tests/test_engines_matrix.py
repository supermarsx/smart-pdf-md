import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


def make_text_pdf(path: Path, text: str = "Hello Engines") -> None:
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
    "engine, imports, executables, env_keys",
    [
        ("pypdf", ["pypdf"], [], []),
        ("pypdfium2", ["pypdfium2"], [], []),
        ("pytesseract", ["pdf2image", "PIL", "pytesseract"], ["pdftoppm"], []),
        ("unstructured", ["unstructured.partition.pdf"], [], []),
        ("pdftotree", ["pdftotree", "markdownify"], [], []),
        ("tabula", ["tabula", "pandas"], ["java"], []),
        ("grobid", ["requests"], [], ["GROBID_URL"]),
        ("pdfx", ["pdfx"], [], []),
        ("ghostscript", [], ["gs", "gswin64c", "gswin32c"], []),
        # borb: if borb missing, engine falls back to pypdf; accept either being present
        ("borb", [], [], []),
        # pdfrw: if pdfrw missing, falls back to pypdf; accept either
        ("pdfrw", [], [], []),
        ("pdfquery", ["pdfminer.high_level"], [], []),
        ("easyocr", ["easyocr", "pdf2image", "PIL"], ["pdftoppm"], []),
        ("kraken", ["pdf2image", "PIL"], ["kraken", "pdftoppm"], []),
    ],
)
def test_engine_matrix_optional(
    tmp_path: Path, engine: str, imports: list[str], executables: list[str], env_keys: list[str]
) -> None:
    # Ensure base dependency for generating input
    pytest.importorskip("fitz")

    # Skip when required imports are missing
    for name in imports:
        pytest.importorskip(name)

    # Skip when required executables are missing (any one of the list is enough)
    if executables:
        if not any(shutil.which(x) for x in executables):
            pytest.skip(f"required executable(s) not available: {executables}")

    # Skip when required environment variables are not set
    for key in env_keys:
        if not os.environ.get(key):
            pytest.skip(f"environment var not set: {key}")

    # Special handling for borb/pdfrw: allow fallback to pypdf if primary missing
    if engine in {"borb", "pdfrw"}:
        have_primary = (
            shutil.which("borb") is not None
            if engine == "borb"
            else shutil.which("pdfrw") is not None
        )
        try:
            __import__("pypdf")
            have_pypdf = True
        except Exception:  # pragma: no cover - simple availability gate
            have_pypdf = False
        if not have_primary and not have_pypdf:
            pytest.skip("neither primary package nor pypdf fallback available")

    pdf = tmp_path / "e.pdf"
    make_text_pdf(pdf, f"Engine {engine} Test")
    res = run_cli([str(pdf), "40", "-e", engine])
    assert res.returncode == 0, res.stdout + "\n" + res.stderr
    md = tmp_path / "e.md"
    assert md.exists()


def test_marker_engine_with_mock(tmp_path: Path) -> None:
    pytest.importorskip("fitz")
    pdf = tmp_path / "m.pdf"
    make_text_pdf(pdf, "Marker Mock Test")
    res = run_cli([str(pdf), "40", "-e", "marker"], env={"SMART_PDF_MD_MARKER_MOCK": "1"})
    assert res.returncode == 0, res.stdout + "\n" + res.stderr
    assert (tmp_path / "m.md").exists()
