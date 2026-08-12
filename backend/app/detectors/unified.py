from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from app.detectors.false_positive import filter_false_positives
from app.detectors.resolver import EntityResolver
from app.detectors.semantic import SemanticPIIDetector
from app.detectors.structured import StructuredPIIDetector
from app.document.models import TextBlock
from app.models.entities import DetectedEntity, PIIType


@dataclass(frozen=True)
class DetectionDiagnostics:
    raw_count: int
    accepted_count: int
    rejected_count: int
    counts_by_type_raw: dict[str, int]
    counts_by_type_final: dict[str, int]
    rejected_by_reason: dict[str, int]


@dataclass(frozen=True)
class DetectionResult:
    entities: list[DetectedEntity]
    diagnostics: DetectionDiagnostics


@dataclass(frozen=True)
class BlockDetections:
    block_id: str
    entities: list[DetectedEntity]


class PIIDetector:
    def __init__(
        self,
        structured_detector: StructuredPIIDetector | None = None,
        semantic_detector: SemanticPIIDetector | None = None,
        resolver: EntityResolver | None = None,
    ) -> None:
        self.structured_detector = structured_detector or StructuredPIIDetector()
        self.semantic_detector = semantic_detector or SemanticPIIDetector()
        self.resolver = resolver or EntityResolver()

    def detect(self, text: str) -> list[DetectedEntity]:
        return self.detect_with_diagnostics(text).entities

    def detect_with_diagnostics(self, text: str) -> DetectionResult:
        raw_candidates = self._raw_candidates(text)
        return self._resolve_with_diagnostics(text, raw_candidates)

    def detect_many(self, texts: Iterable[str]) -> list[list[DetectedEntity]]:
        return [result.entities for result in self.detect_many_with_diagnostics(texts)]

    def detect_many_with_diagnostics(self, texts: Iterable[str]) -> list[DetectionResult]:
        text_list = list(texts)
        semantic_results = self.semantic_detector.detect_many(text_list)
        results: list[DetectionResult] = []
        for text, semantic_entities in zip(text_list, semantic_results, strict=True):
            raw_candidates = [*self.structured_detector.detect(text), *semantic_entities]
            results.append(self._resolve_with_diagnostics(text, raw_candidates))
        return results

    def detect_blocks(self, blocks: Iterable[TextBlock]) -> list[BlockDetections]:
        block_list = list(blocks)
        results = self.detect_many(block.text for block in block_list)
        return [
            BlockDetections(block_id=block.block_id, entities=entities)
            for block, entities in zip(block_list, results, strict=True)
        ]

    def _raw_candidates(self, text: str) -> list[DetectedEntity]:
        if not text:
            return []
        return [
            *self.structured_detector.detect(text),
            *self.semantic_detector.detect(text),
        ]

    def _resolve_with_diagnostics(
        self, text: str, raw_candidates: list[DetectedEntity]
    ) -> DetectionResult:
        filtered, filter_rejections = filter_false_positives(raw_candidates, text)
        resolution = self.resolver.resolve(text, filtered)
        rejected_by_reason = Counter(filter_rejections)
        rejected_by_reason.update(resolution.rejected_by_reason)

        raw_count = len(raw_candidates)
        accepted_count = len(resolution.entities)
        rejected_count = raw_count - accepted_count
        diagnostics = DetectionDiagnostics(
            raw_count=raw_count,
            accepted_count=accepted_count,
            rejected_count=rejected_count,
            counts_by_type_raw=_counts_by_type(raw_candidates),
            counts_by_type_final=_counts_by_type(resolution.entities),
            rejected_by_reason=dict(sorted(rejected_by_reason.items())),
        )
        return DetectionResult(entities=resolution.entities, diagnostics=diagnostics)


def _counts_by_type(entities: Iterable[DetectedEntity]) -> dict[str, int]:
    counts = Counter(entity.pii_type.value for entity in entities)
    return {pii_type.value: counts.get(pii_type.value, 0) for pii_type in PIIType}
