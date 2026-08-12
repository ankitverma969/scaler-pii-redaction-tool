from app.document.loader import (
    DocxLoadError,
    DocxNotFoundError,
    InvalidDocxError,
    UnsupportedDocumentTypeError,
    load_docx,
)
from app.document.models import (
    DocumentStatistics,
    RunSlice,
    RunSpan,
    SourceType,
    TextBlock,
)
from app.document.mutation import (
    DocumentMutationError,
    apply_replacements_to_block,
    apply_replacements_to_text,
)
from app.document.traversal import collect_document_statistics, iter_text_blocks
from app.document.validation import (
    DocumentValidationError,
    DocumentValidationResult,
    validate_redacted_docx,
)

__all__ = [
    "DocxLoadError",
    "DocxNotFoundError",
    "DocumentMutationError",
    "DocumentStatistics",
    "DocumentValidationError",
    "DocumentValidationResult",
    "InvalidDocxError",
    "RunSlice",
    "RunSpan",
    "SourceType",
    "TextBlock",
    "UnsupportedDocumentTypeError",
    "apply_replacements_to_block",
    "apply_replacements_to_text",
    "collect_document_statistics",
    "iter_text_blocks",
    "load_docx",
    "validate_redacted_docx",
]
