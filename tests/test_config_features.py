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


def make_text_pdf(path: Path, text: str = "Hello") -> None:
    ensure_pymupdf()
    import fitz  # type: ignore

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=12)
    doc.save(path)
    doc.close()


def make_blank_pdf(path: Path) -> None:
    ensure_pymupdf()
    import fitz  # type: ignore

    doc = fitz.open()
    doc.new_page()
    doc.save(path)
    doc.close()


def run_batch(input_path: Path, *, env: dict | None = None, slice_pages: int = 40) -> subprocess.CompletedProcess:
    root = Path(__file__).resolve().parents[1]
    if os.name == "nt":
        script = root / "smart-pdf-md.bat"
        cmd = [str(script), str(input_path), str(slice_pages)]
    else:
        script = root / "smart-pdf-md.sh"
        cmd = ["bash", str(script), str(input_path), str(slice_pages)]
    assert script.exists(), f"Missing script at {script}"
    proc_env = os.environ.copy()
    if env:
        proc_env.update(env)
    return subprocess.run(cmd, env=proc_env, capture_output=True, text=True)


def test_output_dir_fast_mode(tmp_path: Path):
    """Outputs should go to custom directory when specified (fast mode)."""
    pdf = tmp_path / "x.pdf"
    outdir = tmp_path / "out"
    make_text_pdf(pdf)
    result = run_batch(pdf, env={"SMART_PDF_MD_MODE": "fast", "SMART_PDF_MD_OUTPUT_DIR": str(outdir)})
    assert result.returncode == 0, result.stdout
    md = outdir / "x.md"
    assert md.exists(), "Output not written to custom outdir"


def test_mock_marker_failure_sets_nonzero_exit(tmp_path: Path):
    """Mocked marker failure should produce a non-zero exit in auto routing."""
    pdf = tmp_path / "y.pdf"
    make_blank_pdf(pdf)
    result = run_batch(pdf, env={"SMART_PDF_MD_MARKER_MOCK": "1", "SMART_PDF_MD_MARKER_MOCK_FAIL": "1"})
    assert result.returncode != 0, "Expected non-zero exit when mock marker fails"
