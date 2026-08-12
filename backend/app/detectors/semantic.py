from collections.abc import Iterable

from app.detectors.address import AddressDetector
from app.detectors.company import CompanyDetector
from app.detectors.nlp import SpacyProvider
from app.detectors.person import PersonDetector
from app.models.entities import DetectedEntity, PIIType


class SemanticPIIDetector:
    def __init__(self, spacy_provider: SpacyProvider | None = None) -> None:
        self.spacy_provider = spacy_provider or SpacyProvider()
        self.person_detector = PersonDetector(self.spacy_provider)
        self.company_detector = CompanyDetector(self.spacy_provider)
        self.address_detector = AddressDetector(self.spacy_provider)

    def detect(self, text: str) -> list[DetectedEntity]:
        if not text:
            return []

        doc = self.spacy_provider.nlp(text)
        entities: list[DetectedEntity] = []
        entities.extend(self.person_detector.detect(text, doc))
        entities.extend(self.company_detector.detect(text, doc))
        entities.extend(self.address_detector.detect(text, doc))
        return _dedupe_and_sort(entities)

    def detect_many(self, texts: Iterable[str]) -> list[list[DetectedEntity]]:
        text_list = list(texts)
        results: list[list[DetectedEntity]] = []
        for text, doc in zip(text_list, self.spacy_provider.pipe(text_list), strict=True):
            if not text:
                results.append([])
                continue
            entities: list[DetectedEntity] = []
            entities.extend(self.person_detector.detect(text, doc))
            entities.extend(self.company_detector.detect(text, doc))
            entities.extend(self.address_detector.detect(text, doc))
            results.append(_dedupe_and_sort(entities))
        return results


def _dedupe_and_sort(entities: list[DetectedEntity]) -> list[DetectedEntity]:
    by_key: dict[tuple[int, int, PIIType], DetectedEntity] = {}
    source_rank = {
        "context_person": 4,
        "legal_suffix_company": 4,
        "address_context": 4,
        "address_heuristic": 3,
        "spacy_person": 2,
        "spacy_company": 2,
    }
    for entity in entities:
        key = (entity.start, entity.end, entity.pii_type)
        existing = by_key.get(key)
        if existing is None or (
            entity.confidence,
            source_rank.get(entity.source, 0),
        ) > (existing.confidence, source_rank.get(existing.source, 0)):
            by_key[key] = entity
    return sorted(
        by_key.values(),
        key=lambda entity: (entity.start, entity.end, entity.pii_type.value, entity.source),
    )
