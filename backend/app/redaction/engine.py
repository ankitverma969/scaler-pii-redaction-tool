from __future__ import annotations

import os
import uuid
from collections import Counter
from pathlib import Path
from time import perf_counter

from app.detectors.unified import PIIDetector
from app.document.loader import load_docx
from app.document.mutation import apply_replacements_to_block, apply_replacements_to_text
from app.document.traversal import collect_document_statistics, iter_text_blocks
from app.document.validation import validate_redacted_docx
from app.models import PIIType
from app.redaction.result import RedactionResult
from app.replacement import ReplacementManager


class RedactionEngineError(RuntimeError):
    """Raised when an end-to-end DOCX redaction job cannot complete safely."""


class RedactionEngine:
    def __init__(self, detector: PIIDetector | None = None) -> None:
        self.detector = detector or PIIDetector()

    def redact(
        self,
        input_path: str | Path,
        output_path: str | Path,
        seed: int = 42,
    ) -> RedactionResult:
        started_at = perf_counter()
        source_path = Path(input_path)
        target_path = Path(output_path)
        if source_path.resolve() == target_path.resolve():
            raise RedactionEngineError("Input and output paths must be different")

        document = load_docx(source_path)
        source_statistics = collect_document_statistics(document)
        blocks = list(iter_text_blocks(document))
        source_block_ids = [block.block_id for block in blocks]

        detection_results = self.detector.detect_many(block.text for block in blocks)
        replacement_manager = ReplacementManager(seed=seed)
        expected_transformed_text: dict[str, str] = {}
        counts_by_type: Counter[str] = Counter()
        total_entities = 0
        total_planned = 0
        total_applied = 0
        blocks_with_replacements = 0

        for block, entities in zip(blocks, detection_results, strict=True):
            if not entities:
                continue

            plans = replacement_manager.plan(entities)
            expected_transformed_text[block.block_id] = apply_replacements_to_text(
                block.text, plans
            )
            applied = apply_replacements_to_block(block, plans)

            total_entities += len(entities)
            total_planned += len(plans)
            total_applied += applied
            blocks_with_replacements += 1
            counts_by_type.update(entity.pii_type.value for entity in entities)

        if total_planned != total_applied:
            raise RedactionEngineError("Planned and applied replacement counts differ")

        target_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = target_path.with_name(
            f".{target_path.stem}.{uuid.uuid4().hex}.tmp.docx"
        )

        try:
            document.save(temp_path)
            validate_redacted_docx(
                temp_path,
                source_statistics=source_statistics,
                source_block_ids=source_block_ids,
                expected_transformed_text=expected_transformed_text,
            )
            os.replace(temp_path, target_path)
            validation = validate_redacted_docx(
                target_path,
                source_statistics=source_statistics,
                source_block_ids=source_block_ids,
                expected_transformed_text=expected_transformed_text,
            )
        finally:
            if temp_path.exists():
                temp_path.unlink()

        return RedactionResult(
            output_path=target_path,
            total_entities=total_entities,
            total_planned=total_planned,
            total_applied=total_applied,
            counts_by_type={
                pii_type.value: counts_by_type.get(pii_type.value, 0)
                for pii_type in PIIType
            },
            blocks_processed=len(blocks),
            blocks_with_replacements=blocks_with_replacements,
            duration_seconds=perf_counter() - started_at,
            validation=validation,
        )
