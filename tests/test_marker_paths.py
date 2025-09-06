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


def make_blank_pdf(path: Path) -> None:
    ensure_pymupdf()
    import fitz  # type: ignore

    doc = fitz.open()
    doc.new_page()  # no text content
    doc.save(path)
    doc.close()


def run_batch(
    input_path: Path, *, env: dict | None = None, slice_pages: int = 40
) -> subprocess.CompletedProcess:
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


def test_auto_routes_to_marker_with_mock(tmp_path: Path):
    """Auto routing should select marker for blank PDFs (with mock)."""
    pdf = tmp_path / "scanned.pdf"
    md = tmp_path / "scanned.md"
    make_blank_pdf(pdf)

    result = run_batch(pdf, env={"SMART_PDF_MD_MARKER_MOCK": "1"})

    assert result.returncode == 0, f"batch failed: {result.stdout}\n{result.stderr}"
    assert md.exists(), "Mock Marker output not created"
    assert "MOCK MARKER OUTPUT" in md.read_text(encoding="utf-8")


def test_forced_marker_mode_with_mock(tmp_path: Path):
    """Forced marker mode via env should call marker path (with mock)."""
    pdf = tmp_path / "forced.pdf"
    md = tmp_path / "forced.md"
    make_blank_pdf(pdf)

    result = run_batch(pdf, env={"SMART_PDF_MD_MODE": "marker", "SMART_PDF_MD_MARKER_MOCK": "1"})

    assert result.returncode == 0, f"batch failed: {result.stdout}\n{result.stderr}"
    assert md.exists(), "Mock Marker output not created"
    assert "MOCK MARKER OUTPUT" in md.read_text(encoding="utf-8")
