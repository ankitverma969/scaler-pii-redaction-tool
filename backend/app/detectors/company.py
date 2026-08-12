import re

from spacy.tokens import Doc

from app.detectors.nlp import SpacyProvider
from app.detectors.semantic_filters import is_false_company, trim_span
from app.models.entities import DetectedEntity, PIIType


LEGAL_SUFFIX_PATTERN = (
    r"(?:Private\s+Limited|Pvt\.?\s+Ltd\.?|Limited|Ltd\.?|LLP|L\.L\.P\.)"
)


class CompanyDetector:
    _legal_suffix_regex = re.compile(
        r"\b(?!Private\b|Pvt\b|Ltd\b|Limited\b|LLP\b|L\.L\.P\b)"
        r"[A-Z][A-Za-z&'()-]*"
        r"(?:\s+(?!Private\b|Pvt\b|Ltd\b|Limited\b|LLP\b|L\.L\.P\b)"
        r"[A-Z][A-Za-z&'()-]*){0,8}\s+"
        + LEGAL_SUFFIX_PATTERN
        + r"\b",
    )
    _commercial_evidence = re.compile(
        r"\b(?:Limited|Ltd\.?|LLP|Pvt|Private|Bank|Securities|Finance|"
        r"Industries|Management|Technologies|Services|Systems)\b",
        re.IGNORECASE,
    )

    def __init__(self, spacy_provider: SpacyProvider | None = None) -> None:
        self.spacy_provider = spacy_provider or SpacyProvider()

    def detect(self, text: str, doc: Doc | None = None) -> list[DetectedEntity]:
        if not text:
            return []

        doc = doc or self.spacy_provider.nlp(text)
        entities: list[DetectedEntity] = []
        entities.extend(self._from_legal_suffix(text))
        entities.extend(self._from_spacy(text, doc))
        return _dedupe_and_sort(entities)

    def _from_legal_suffix(self, text: str) -> list[DetectedEntity]:
        entities: list[DetectedEntity] = []
        for match in self._legal_suffix_regex.finditer(text):
            start, end = trim_span(text, match.start(), match.end())
            candidate = text[start:end]
            if self._is_valid_company(candidate):
                entities.append(
                    DetectedEntity(
                        text=candidate,
                        start=start,
                        end=end,
                        pii_type=PIIType.COMPANY,
                        confidence=0.95,
                        source="legal_suffix_company",
                    )
                )
        return entities

    def _from_spacy(self, text: str, doc: Doc) -> list[DetectedEntity]:
        entities: list[DetectedEntity] = []
        for ent in doc.ents:
            if ent.label_ != "ORG":
                continue
            start, end = trim_span(text, ent.start_char, ent.end_char)
            candidate = text[start:end]
            if self._is_valid_company(candidate) and self._commercial_evidence.search(candidate):
                entities.append(
                    DetectedEntity(
                        text=candidate,
                        start=start,
                        end=end,
                        pii_type=PIIType.COMPANY,
                        confidence=0.88,
                        source="spacy_company",
                    )
                )
        return entities

    @staticmethod
    def _is_valid_company(candidate: str) -> bool:
        if not candidate or is_false_company(candidate):
            return False
        words = candidate.split()
        return 2 <= len(words) <= 12


def _dedupe_and_sort(entities: list[DetectedEntity]) -> list[DetectedEntity]:
    by_key: dict[tuple[int, int, PIIType], DetectedEntity] = {}
    source_rank = {"legal_suffix_company": 2, "spacy_company": 1}
    for entity in entities:
        key = (entity.start, entity.end, entity.pii_type)
        existing = by_key.get(key)
        if existing is None or (
            entity.confidence,
            source_rank.get(entity.source, 0),
        ) > (existing.confidence, source_rank.get(existing.source, 0)):
            by_key[key] = entity
    return sorted(by_key.values(), key=lambda item: (item.start, item.end, item.pii_type.value, item.source))
