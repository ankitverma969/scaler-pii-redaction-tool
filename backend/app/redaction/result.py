from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.document.validation import DocumentValidationResult


@dataclass(frozen=True)
class RedactionResult:
    output_path: Path
    total_entities: int
    total_planned: int
    total_applied: int
    counts_by_type: dict[str, int]
    blocks_processed: int
    blocks_with_replacements: int
    duration_seconds: float
    validation: DocumentValidationResult
