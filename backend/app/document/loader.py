from pathlib import Path
from typing import Union

from docx import Document
from docx.opc.exceptions import PackageNotFoundError


PathLike = Union[str, Path]


class DocxLoadError(Exception):
    """Base error for DOCX loading failures."""


class DocxNotFoundError(DocxLoadError):
    """Raised when the requested DOCX file does not exist."""


class UnsupportedDocumentTypeError(DocxLoadError):
    """Raised when the input path is not a .docx file."""


class InvalidDocxError(DocxLoadError):
    """Raised when python-docx cannot open the input as a valid DOCX."""


def load_docx(path: PathLike):
    input_path = Path(path)

    if not input_path.exists() or not input_path.is_file():
        raise DocxNotFoundError(f"DOCX file not found: {input_path}")

    if input_path.suffix.lower() != ".docx":
        raise UnsupportedDocumentTypeError(
            f"Unsupported document type: {input_path.suffix or '<none>'}"
        )

    try:
        return Document(input_path)
    except PackageNotFoundError as exc:
        raise InvalidDocxError(f"Invalid DOCX file: {input_path}") from exc
    except Exception as exc:
        raise InvalidDocxError(f"Could not open DOCX file: {input_path}") from exc
