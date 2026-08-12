from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path

from app.document.loader import load_docx
from app.document.models import DocumentStatistics
from app.document.traversal import collect_document_statistics, iter_text_blocks


@dataclass(frozen=True)
class DocumentValidationResult:
    path: Path
    file_exists: bool
    file_size: int
    valid_zip_package: bool
    reopen_success: bool
    block_ids_match: bool
    transformed_text_match: bool
    structural_match: bool
    source_statistics: DocumentStatistics
    output_statistics: DocumentStatistics

    @property
    def success(self) -> bool:
        return (
            self.file_exists
            and self.file_size > 0
            and self.valid_zip_package
            and self.reopen_success
            and self.block_ids_match
            and self.transformed_text_match
            and self.structural_match
        )


class DocumentValidationError(RuntimeError):
    """Raised when a saved DOCX fails structural or logical validation."""


def validate_redacted_docx(
    output_path: str | Path,
    source_statistics: DocumentStatistics,
    source_block_ids: list[str],
    expected_transformed_text: dict[str, str],
) -> DocumentValidationResult:
    path = Path(output_path)
    file_exists = path.exists() and path.is_file()
    file_size = path.stat().st_size if file_exists else 0
    valid_zip = zipfile.is_zipfile(path) if file_exists else False

    reopen_success = False
    output_statistics = source_statistics
    block_ids_match = False
    transformed_text_match = False

    if valid_zip:
        document = load_docx(path)
        reopen_success = True
        output_statistics = collect_document_statistics(document)
        output_blocks = list(iter_text_blocks(document))
        output_by_id = {block.block_id: block.text for block in output_blocks}
        block_ids_match = source_block_ids == [block.block_id for block in output_blocks]
        transformed_text_match = all(
            output_by_id.get(block_id) == expected_text
            for block_id, expected_text in expected_transformed_text.items()
        )

    result = DocumentValidationResult(
        path=path,
        file_exists=file_exists,
        file_size=file_size,
        valid_zip_package=valid_zip,
        reopen_success=reopen_success,
        block_ids_match=block_ids_match,
        transformed_text_match=transformed_text_match,
        structural_match=_structural_match(source_statistics, output_statistics),
        source_statistics=source_statistics,
        output_statistics=output_statistics,
    )
    if not result.success:
        raise DocumentValidationError(f"Redacted DOCX validation failed: {path}")
    return result


def _structural_match(
    source: DocumentStatistics, output: DocumentStatistics
) -> bool:
    return (
        source.section_count == output.section_count
        and source.table_count == output.table_count
        and source.nested_table_count == output.nested_table_count
        and source.text_block_count == output.text_block_count
        and source.header_part_count == output.header_part_count
        and source.footer_part_count == output.footer_part_count
        and source.embedded_media_count == output.embedded_media_count
    )
