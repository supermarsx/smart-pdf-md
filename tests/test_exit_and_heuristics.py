import os
import subprocess
import sys
from pathlib import Path


def ensure_pymupdf():
    try:
        import importlib.util  # noqa: F401

        if importlib.util.find_spec("fitz") is None:
            raise ImportError
    except Exception:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "pymupdf"])  # noqa: S603,S607


def make_blank_pdf(path: Path, pages: int = 1) -> None:
    ensure_pymupdf()
    import fitz  # type: ignore

    doc = fitz.open()
    for _ in range(pages):
        doc.new_page()
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


def test_nonexistent_input_exit1(tmp_path: Path):
    """Running with a non-existent input path returns exit code 1."""
    bad = tmp_path / "does_not_exist.pdf"
    res = run_script([str(bad), "40"], env={"SMART_PDF_MD_MARKER_MOCK": "1"})
    assert res.returncode == 1


def test_heuristics_force_fast_on_blank_pdf(tmp_path: Path):
    """CLI/env heuristics can force fast path even on blank PDFs."""
    pdf = tmp_path / "blank.pdf"
    md = tmp_path / "blank.md"
    make_blank_pdf(pdf)
    # Default heuristic would route to marker; lower the ratio to 0 to force "textual"
    res = run_script(
        [str(pdf), "40"],
        env={
            "SMART_PDF_MD_TEXT_MIN_RATIO": "0",
            "SMART_PDF_MD_MODE": "auto",
        },
    )
    assert res.returncode == 0
    assert md.exists(), "Fast path should write an md even for blank (empty content)"


def test_min_slice_failure_exit2(tmp_path: Path):
    """When mock enforces failure above threshold, min-slice failure yields exit code 2."""
    pdf = tmp_path / "scan.pdf"
    make_blank_pdf(pdf, pages=7)
    # With mock, fail any slice > 4; initial slice 5 triggers min-slice failure when cur=5
    res = run_script(
        [str(pdf), "5"],
        env={
            "SMART_PDF_MD_MARKER_MOCK": "1",
            "SMART_PDF_MD_MOCK_FAIL_IF_SLICE_GT": "4",
        },
    )
    assert res.returncode == 2
