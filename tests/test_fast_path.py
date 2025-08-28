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


def make_text_pdf(path: Path, text: str = "Hello from smart-pdf-md") -> None:
    ensure_pymupdf()
    import fitz  # type: ignore

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=12)
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


def test_single_file_fast_path(tmp_path: Path):
    """A small textual PDF should convert to .md via fast path."""
    pdf = tmp_path / "sample.pdf"
    md = tmp_path / "sample.md"
    text = "Hello from smart-pdf-md"
    make_text_pdf(pdf, text)

    result = run_batch(pdf, env={"SMART_PDF_MD_MODE": "fast"})
    assert result.returncode == 0, f"batch failed: {result.stdout}\n{result.stderr}"
    assert md.exists(), "Markdown output not created"
    content = md.read_text(encoding="utf-8")
    assert "Hello" in content and "smart-pdf-md" in content


def test_directory_fast_path(tmp_path: Path):
    """Directory traversal in fast mode should convert multiple files."""
    pdf1 = tmp_path / "a.pdf"
    pdf2 = tmp_path / "b.pdf"
    make_text_pdf(pdf1, "Alpha Bravo")
    make_text_pdf(pdf2, "Charlie Delta")

    result = run_batch(tmp_path, env={"SMART_PDF_MD_MODE": "fast"})
    assert result.returncode == 0, f"batch failed: {result.stdout}\n{result.stderr}"

    md1 = tmp_path / "a.md"
    md2 = tmp_path / "b.md"
    assert md1.exists() and md2.exists(), "Markdown outputs missing"
    assert "Alpha" in md1.read_text(encoding="utf-8")
    assert "Charlie" in md2.read_text(encoding="utf-8")
