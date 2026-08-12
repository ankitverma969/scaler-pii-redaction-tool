import subprocess
import sys
from pathlib import Path

from docx import Document

from app.document import iter_text_blocks, load_docx


def run_cli(args):
    backend_dir = Path(__file__).resolve().parents[1]
    return subprocess.run(
        [sys.executable, "-m", "app", *args],
        cwd=backend_dir,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_cli_redacts_synthetic_docx_without_printing_pii(tmp_path: Path) -> None:
    source = tmp_path / "cli-source.docx"
    output = tmp_path / "cli-output.docx"
    document = Document()
    document.add_paragraph("Email: cli-person@example.com")
    document.save(source)

    result = run_cli(
        [
            "--input",
            str(source),
            "--output",
            str(output),
            "--seed",
            "42",
        ]
    )

    assert result.returncode == 0, result.stderr
    assert output.exists()
    assert "cli-person@example.com" not in result.stdout
    assert "cli-person@example.com" not in result.stderr
    output_text = "\n".join(block.text for block in iter_text_blocks(load_docx(output)))
    assert "cli-person@example.com" not in output_text
    assert "validation: success" in result.stdout


def test_cli_rejects_missing_input_without_creating_output(tmp_path: Path) -> None:
    output = tmp_path / "missing-output.docx"

    result = run_cli(
        ["--input", str(tmp_path / "missing.docx"), "--output", str(output)]
    )

    assert result.returncode != 0
    assert not output.exists()
    assert "validation: success" not in result.stdout


def test_cli_rejects_invalid_docx_without_printing_contents(tmp_path: Path) -> None:
    secret = "private.person@example.com"
    source = tmp_path / "invalid.docx"
    output = tmp_path / "invalid-output.docx"
    source.write_text(secret)

    result = run_cli(["--input", str(source), "--output", str(output)])

    assert result.returncode != 0
    assert not output.exists()
    assert secret not in result.stdout
    assert secret not in result.stderr
