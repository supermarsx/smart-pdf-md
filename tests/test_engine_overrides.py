import os
import subprocess
import sys
from pathlib import Path


def run_cli(args: list[str], *, env: dict | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, "-m", "smart_pdf_md"] + args
    proc_env = os.environ.copy()
    if env:
        proc_env.update(env)
    return subprocess.run(cmd, env=proc_env, capture_output=True, text=True)


def make_text_pdf(path: Path, text: str = "Hello") -> None:
    import fitz  # type: ignore

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=12)
    doc.save(path)
    doc.close()


def make_blank_pdf(path: Path) -> None:
    import fitz  # type: ignore

    doc = fitz.open()
    doc.new_page()
    doc.save(path)
    doc.close()


def test_engine_textual_override_fast(tmp_path: Path) -> None:
    pdf = tmp_path / "t.pdf"
    make_text_pdf(pdf, "override test")
    res = run_cli([str(pdf), "40"], env={"SMART_PDF_MD_ENGINE_TEXTUAL": "fast"})
    assert res.returncode == 0, res.stdout + "\n" + res.stderr


def test_engine_nontextual_override_marker_with_mock(tmp_path: Path) -> None:
    pdf = tmp_path / "n.pdf"
    make_blank_pdf(pdf)
    res = run_cli(
        [str(pdf), "40"],
        env={
            "SMART_PDF_MD_ENGINE_NON_TEXTUAL": "marker",
            "SMART_PDF_MD_MARKER_MOCK": "1",
        },
    )
    assert res.returncode == 0, res.stdout + "\n" + res.stderr
