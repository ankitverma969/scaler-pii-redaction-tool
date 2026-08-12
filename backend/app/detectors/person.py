import re

from spacy.tokens import Doc

from app.detectors.nlp import SpacyProvider
from app.detectors.semantic_filters import (
    ROLE_STOP_PATTERN,
    is_false_person,
    is_name_like,
    trim_span,
)
from app.models.entities import DetectedEntity, PIIType


class PersonDetector:
    _context_pattern = re.compile(
        r"\b(?:Contact\s+Person|Promoters?|Director|Managing\s+Director|"
        r"Joint\s+Managing\s+Director|Whole-time\s+Director|Independent\s+Director|"
        r"Executive\s+Director|Company\s+Secretary|Compliance\s+Officer|"
        r"Chief\s+Executive\s+Officer|Chief\s+Financial\s+Officer|CEO|CFO|"
        r"Key\s+Managerial\s+Personnel|Senior\s+Management|Auditor|Chairman)\b"
        r"\s*(?::|-)?\s*",
        re.IGNORECASE,
    )
    _name_pattern = re.compile(
        r"\b(?:[A-Z][A-Za-z']+|[A-Z]\.)(?:\s+(?:[A-Z][A-Za-z']+|[A-Z]\.)){1,4}\b"
    )

    def __init__(self, spacy_provider: SpacyProvider | None = None) -> None:
        self.spacy_provider = spacy_provider or SpacyProvider()

    def detect(self, text: str, doc: Doc | None = None) -> list[DetectedEntity]:
        if not text:
            return []

        doc = doc or self.spacy_provider.nlp(text)
        entities: list[DetectedEntity] = []
        entities.extend(self._from_spacy(text, doc))
        entities.extend(self._from_context(text))
        return _dedupe_and_sort(entities)

    def _from_spacy(self, text: str, doc: Doc) -> list[DetectedEntity]:
        entities: list[DetectedEntity] = []
        for ent in doc.ents:
            if ent.label_ != "PERSON":
                continue
            start, end = trim_span(text, ent.start_char, ent.end_char)
            if start >= end:
                continue
            candidate = text[start:end]
            if is_false_person(candidate) or not is_name_like(candidate):
                continue
            entities.append(
                DetectedEntity(
                    text=candidate,
                    start=start,
                    end=end,
                    pii_type=PIIType.PERSON,
                    confidence=0.88,
                    source="spacy_person",
                )
            )
        return entities

    def _from_context(self, text: str) -> list[DetectedEntity]:
        entities: list[DetectedEntity] = []
        for context_match in self._context_pattern.finditer(text):
            tail_start = context_match.end()
            tail_end = min(len(text), tail_start + 120)
            tail = text[tail_start:tail_end]
            line_break = tail.find("\n")
            if line_break != -1:
                tail = tail[:line_break]
                tail_end = tail_start + len(tail)
            stop_match = ROLE_STOP_PATTERN.search(tail, 1)
            if stop_match:
                tail = tail[: stop_match.start()]
                tail_end = tail_start + len(tail)

            for name_match in self._name_pattern.finditer(tail):
                start = tail_start + name_match.start()
                end = tail_start + name_match.end()
                if self._has_bad_prefix_between(text[tail_start:start]):
                    continue
                candidate = text[start:end]
                if is_name_like(candidate):
                    entities.append(
                        DetectedEntity(
                            text=candidate,
                            start=start,
                            end=end,
                            pii_type=PIIType.PERSON,
                            confidence=0.94,
                            source="context_person",
                        )
                    )
        return entities

    @staticmethod
    def _has_bad_prefix_between(value: str) -> bool:
        return bool(re.search(r"\b(?:Email|Telephone|Tel|Phone|Website|Address)\b", value, re.I))


def _dedupe_and_sort(entities: list[DetectedEntity]) -> list[DetectedEntity]:
    by_key: dict[tuple[int, int, PIIType], DetectedEntity] = {}
    source_rank = {"context_person": 2, "spacy_person": 1}
    for entity in entities:
        key = (entity.start, entity.end, entity.pii_type)
        existing = by_key.get(key)
        if existing is None or (
            entity.confidence,
            source_rank.get(entity.source, 0),
        ) > (existing.confidence, source_rank.get(existing.source, 0)):
            by_key[key] = entity
    return sorted(by_key.values(), key=lambda item: (item.start, item.end, item.pii_type.value, item.source))
