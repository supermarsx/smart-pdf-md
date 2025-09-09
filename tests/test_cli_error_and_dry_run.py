import os
import subprocess
import sys
from pathlib import Path


def run_cli(args: list[str], *, env: dict | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, "-m", "smart_pdf_md"] + args
    proc_env = os.environ.copy()
    root = Path(__file__).resolve().parents[1]
    proc_env["PYTHONPATH"] = str(root / "src") + (
        os.pathsep + proc_env.get("PYTHONPATH", "") if proc_env.get("PYTHONPATH") else ""
    )
    if env:
        proc_env.update(env)
    return subprocess.run(cmd, env=proc_env, capture_output=True, text=True)


def test_forced_unknown_engine_returns_error(tmp_path: Path) -> None:
    pdf = tmp_path / "u.pdf"
    pdf.write_bytes(b"%PDF-1.4 invalid content")
    res = run_cli([str(pdf), "5"], env={"SMART_PDF_MD_ENGINE": "nope"})
    assert res.returncode == 9
    assert "unknown engine: nope" in (res.stdout + res.stderr)


def test_dry_run_skips_execution(tmp_path: Path) -> None:
    pdf = tmp_path / "d.pdf"
    out = tmp_path / "d.md"
    pdf.write_bytes(b"%PDF-1.4 invalid content")
    res = run_cli(
        [str(pdf), "5", "-n"], env={"SMART_PDF_MD_ENGINE": "nope"}
    )  # dry-run should not error
    assert res.returncode == 0
    assert "[DRY  ]" in (res.stdout + res.stderr)
    assert not out.exists()
