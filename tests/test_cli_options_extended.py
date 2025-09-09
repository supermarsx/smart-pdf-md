import os
import subprocess
import sys
from pathlib import Path

import pytest


def run_cli(args: list[str], *, env: dict | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, "-m", "smart_pdf_md"] + args
    proc_env = os.environ.copy()
    # Ensure src is importable when running from repo
    root = Path(__file__).resolve().parents[1]
    proc_env["PYTHONPATH"] = str(root / "src") + (
        os.pathsep + proc_env.get("PYTHONPATH", "") if proc_env.get("PYTHONPATH") else ""
    )
    if env:
        proc_env.update(env)
    return subprocess.run(cmd, env=proc_env, capture_output=True, text=True)


def test_include_exclude_patterns(tmp_path: Path) -> None:
    # Create nested directories with placeholder PDFs (invalid content is fine for --mock)
    (tmp_path / "docs" / "Handbooks").mkdir(parents=True)
    (tmp_path / "trash" / "drafts").mkdir(parents=True)
    keep = tmp_path / "docs" / "Handbooks" / "keep.pdf"
    drop = tmp_path / "trash" / "drafts" / "drop_draft.pdf"
    keep.write_bytes(b"%PDF-1.4 invalid but present")
    drop.write_bytes(b"%PDF-1.4 invalid but present")

    res = run_cli(
        [
            str(tmp_path),
            "40",
            "--mock",
            "-S",
            "**/Handbooks/*.pdf",
            "-X",
            "**/*draft*.pdf",
        ]
    )
    assert res.returncode == 0, res.stdout + "\n" + res.stderr
    # Only included path should produce an output
    assert (tmp_path / "docs" / "Handbooks" / "keep.md").exists()
    assert not (tmp_path / "trash" / "drafts" / "drop_draft.md").exists()


def test_output_format_txt_fast(tmp_path: Path) -> None:
    pytest.importorskip("fitz")
    import fitz  # type: ignore

    pdf = tmp_path / "t.pdf"
    # Generate a small textual PDF
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "TXT Output Test", fontsize=12)
    doc.save(pdf)
    doc.close()

    res = run_cli([str(pdf), "5", "-m", "fast", "-f", "txt"])
    assert res.returncode == 0, res.stdout + "\n" + res.stderr
    out = tmp_path / "t.txt"
    assert out.exists()
    assert "TXT Output Test" in out.read_text(encoding="utf-8")


def test_env_warnings_toggle(tmp_path: Path) -> None:
    # Unknown env key should warn by default
    pdf = tmp_path / "e.pdf"
    pdf.write_bytes(b"not real pdf")
    res1 = run_cli([str(pdf), "5", "--env", "FOO=bar", "--mock"])
    assert res1.returncode == 0
    assert "unknown env key: FOO" in (res1.stdout + res1.stderr)

    # Suppress warnings with --no-warn-unknown-env
    res2 = run_cli([str(pdf), "5", "--env", "FOO=bar", "--no-warn-unknown-env", "--mock"])
    assert res2.returncode == 0
    assert "unknown env key: FOO" not in (res2.stdout + res2.stderr)


def test_tables_mode_without_camelot(tmp_path: Path) -> None:
    # Without camelot installed, --tables should not crash and should still produce output
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"not real pdf")
    res = run_cli([str(pdf), "5", "--tables", "--tables-mode", "lattice", "--mock"])
    assert res.returncode == 0, res.stdout + "\n" + res.stderr
    assert (tmp_path / "a.md").exists()
