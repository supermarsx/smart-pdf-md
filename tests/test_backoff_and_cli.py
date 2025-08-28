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
    doc.new_page()
    doc.save(path)
    doc.close()


def run_batch_args(args: list[str], *, env: dict | None = None) -> subprocess.CompletedProcess:
    root = Path(__file__).resolve().parents[1]
    if os.name == "nt":
        script = root / "smart-pdf-md.bat"
        cmd = [str(script)] + args
    else:
        script = root / "smart-pdf-md.sh"
        cmd = ["bash", str(script)] + args
    assert script.exists(), f"Missing script at {script}"
    proc_env = os.environ.copy()
    if env:
        proc_env.update(env)
    return subprocess.run(cmd, env=proc_env, capture_output=True, text=True)


def test_cli_flags_mode_out_and_images(tmp_path: Path):
    """CLI flags should map to env and allow forcing marker + outdir + images."""
    pdf = tmp_path / "c.pdf"
    outdir = tmp_path / "cli-out"
    make_blank_pdf(pdf)
    # Force marker path with mock using CLI flags only
    res = run_batch_args([str(pdf), "40", "--mode", "marker", "--mock", "--out", str(outdir), "--images"], env={})
    assert res.returncode == 0, res.stdout
    assert (outdir / "c.md").exists()


def test_slice_backoff_with_mock_threshold(tmp_path: Path):
    """Backoff should halve slice until threshold then succeed (with mock)."""
    pdf = tmp_path / "d.pdf"
    make_blank_pdf(pdf)
    # Start with large slice, fail slices > 10, expect backoff to <=10 and succeed
    res = run_batch_args([str(pdf), "40"], env={
        "SMART_PDF_MD_MARKER_MOCK": "1",
        "SMART_PDF_MD_MOCK_FAIL_IF_SLICE_GT": "10",
        # Ensure we are on marker path (blank pdf should route there automatically)
    })
    assert res.returncode == 0, res.stdout
    assert (tmp_path / "d.md").exists()
