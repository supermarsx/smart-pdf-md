import os
import subprocess
import sys
from pathlib import Path

import pytest


def ensure_pymupdf():
    pytest.importorskip("fitz")


def make_text_pdf(path: Path, text: str = "Hello") -> None:
    ensure_pymupdf()
    import fitz  # type: ignore

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=12)
    doc.save(path)
    doc.close()


def run_script(args: list[str], *, env: dict | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, "-m", "smart_pdf_md"] + args
    proc_env = os.environ.copy()
    root = Path(__file__).resolve().parents[1]
    proc_env["PYTHONPATH"] = str(root / "src") + (
        os.pathsep + proc_env.get("PYTHONPATH", "") if proc_env.get("PYTHONPATH") else ""
    )
    if env:
        proc_env.update(env)
    return subprocess.run(cmd, env=proc_env, capture_output=True, text=True)


def test_cli_mock_fail_returns_nonzero(tmp_path: Path):
    pdf = tmp_path / "bad.pdf"
    pdf.write_bytes(b"not a real pdf")  # deliberately unopenable by fitz
    res = run_script([str(pdf), "40", "--mock-fail"], env={})
    assert res.returncode != 0


def test_single_pass_marker_when_unopenable_pdf(tmp_path: Path):
    pdf = tmp_path / "odd.pdf"
    md = tmp_path / "odd.md"
    pdf.write_bytes(b"not a real pdf")  # fitz.open() will fail -> single-pass path
    res = run_script([str(pdf), "40", "--mock"], env={})
    assert res.returncode == 0
    assert md.exists(), "Mock single-pass should create output"
    assert "MOCK MARKER OUTPUT" in md.read_text(encoding="utf-8")


def test_first_nonzero_exitcode_selected(tmp_path: Path):
    # Create one fast-path file and one marker-failing file; expect exit=2 from the failing file
    good = tmp_path / "good.pdf"
    bad = tmp_path / "bad2.pdf"
    make_text_pdf(good, "Some Text")
    bad.write_bytes(b"%PDF-1.4\n% not actually valid content")  # unopenable -> single-pass

    res = run_script(
        [str(tmp_path), "40"],
        env={
            "SMART_PDF_MD_MARKER_MOCK": "1",
            "SMART_PDF_MD_MARKER_MOCK_FAIL": "1",  # fail marker always
        },
    )
    # First non-zero will come from the first file that routes to marker and fails at min-slice/single-pass
    assert res.returncode in (2, 3)


def test_cli_min_chars_and_ratio_force_fast(tmp_path: Path):
    """CLI min-chars/min-ratio can force fast path on minimal-content PDFs."""
    pdf = tmp_path / "blank.pdf"
    md = tmp_path / "blank.md"
    # Create a valid, but effectively blank, PDF
    ensure_pymupdf()
    import fitz  # type: ignore

    doc = fitz.open()
    doc.new_page()
    doc.save(pdf)
    doc.close()
    # Heuristic flags should push to fast path even with no text
    res = run_script(
        [str(pdf), "40", "--min-chars", "1", "--min-ratio", "0", "--mode", "auto"], env={}
    )
    assert res.returncode == 0
    assert md.exists()
