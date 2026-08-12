import subprocess
import sys
from pathlib import Path

from docx import Document

from app.document import iter_text_blocks, load_docx


def test_cli_redacts_synthetic_docx_without_printing_pii(tmp_path: Path) -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    source = tmp_path / "cli-source.docx"
    output = tmp_path / "cli-output.docx"
    document = Document()
    document.add_paragraph("Email: cli-person@example.com")
    document.save(source)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "app",
            "--input",
            str(source),
            "--output",
            str(output),
            "--seed",
            "42",
        ],
        cwd=backend_dir,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stderr
    assert output.exists()
    assert "cli-person@example.com" not in result.stdout
    assert "cli-person@example.com" not in result.stderr
    output_text = "\n".join(block.text for block in iter_text_blocks(load_docx(output)))
    assert "cli-person@example.com" not in output_text
    assert "validation: success" in result.stdout
