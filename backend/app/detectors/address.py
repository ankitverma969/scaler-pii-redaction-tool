import re

from spacy.tokens import Doc

from app.detectors.nlp import SpacyProvider
from app.detectors.semantic_filters import trim_span
from app.models.entities import DetectedEntity, PIIType


class AddressDetector:
    source = "address_heuristic"
    _label_pattern = re.compile(
        r"\b(?:Registered\s+Office|Corporate\s+Office|Registered\s+Address|"
        r"Office\s+Address|Branch\s+Office|Manufacturing\s+Facility|Address|"
        r"Located\s+at|Situated\s+at)\b\s*(?::|-)?\s*",
        re.IGNORECASE,
    )
    _terminator_pattern = re.compile(
        r"\b(?:Telephone|Tel|Phone|Mobile|Email|E-mail|Website|Contact\s+Person|"
        r"SEBI\s+Registration|CIN|DIN)\b\s*(?::|\+|\(|$)",
        re.IGNORECASE,
    )
    _pin_pattern = re.compile(r"\b[1-9]\d{2}\s?\d{3}\b")
    _street_tokens = re.compile(
        r"\b(?:Flat|Plot|Building|Tower|Floor|Wing|House|Apartment|Office\s+No|Block|"
        r"Unit|Room|Road|Rd|Street|Lane|Marg|Nagar|Colony|Complex|Industrial\s+Area|"
        r"Business\s+Centre|Village|Taluka|District|Phase)\b",
        re.IGNORECASE,
    )
    _location_tokens = re.compile(
        r"\b(?:Pune|Mumbai|Delhi|Bengaluru|Bangalore|Chennai|Hyderabad|Kolkata|"
        r"Maharashtra|Karnataka|Gujarat|India|East|West|North|South)\b",
        re.IGNORECASE,
    )

    def __init__(self, spacy_provider: SpacyProvider | None = None) -> None:
        self.spacy_provider = spacy_provider or SpacyProvider()

    def detect(self, text: str, doc: Doc | None = None) -> list[DetectedEntity]:
        if not text:
            return []

        doc = doc or self.spacy_provider.nlp(text)
        entities: list[DetectedEntity] = []
        entities.extend(self._from_labeled_candidates(text))
        if not entities:
            entities.extend(self._from_unlabeled_candidates(text))
        return _dedupe_and_sort(entities)

    def _from_labeled_candidates(self, text: str) -> list[DetectedEntity]:
        entities: list[DetectedEntity] = []
        for label_match in self._label_pattern.finditer(text):
            start = label_match.end()
            end = self._candidate_end(text, start)
            start, end = trim_span(text, start, end)
            if start >= end:
                continue
            candidate = text[start:end]
            score = self._score(candidate, has_label=True)
            if score >= 3 and self._has_address_evidence(candidate):
                entities.append(
                    DetectedEntity(
                        text=candidate,
                        start=start,
                        end=end,
                        pii_type=PIIType.ADDRESS,
                        confidence=0.93 if score >= 5 else 0.86,
                        source="address_context",
                    )
                )
        return entities

    def _from_unlabeled_candidates(self, text: str) -> list[DetectedEntity]:
        candidate_end = self._candidate_end(text, 0)
        stripped_start, stripped_end = trim_span(text, 0, candidate_end)
        candidate = text[stripped_start:stripped_end]
        if self._score(candidate, has_label=False) >= 4 and self._has_address_evidence(candidate):
            return [
                DetectedEntity(
                    text=candidate,
                    start=stripped_start,
                    end=stripped_end,
                    pii_type=PIIType.ADDRESS,
                    confidence=0.88,
                    source=self.source,
                )
            ]
        return []

    def _candidate_end(self, text: str, start: int) -> int:
        search_end = min(len(text), start + 260)
        candidate_window = text[start:search_end]
        terminator = self._terminator_pattern.search(candidate_window)
        if terminator:
            return start + terminator.start()
        semicolon = candidate_window.find(";")
        if semicolon != -1:
            return start + semicolon
        return search_end

    def _score(self, candidate: str, has_label: bool) -> int:
        score = 2 if has_label else 0
        if self._street_tokens.search(candidate):
            score += 2
        if self._has_pin(candidate):
            score += 2
        if self._location_tokens.search(candidate):
            score += 1
        if candidate.count(",") >= 2:
            score += 1
        if "\n" in candidate:
            score += 1
        if len(candidate.split()) >= 6:
            score += 1
        return score

    def _has_address_evidence(self, candidate: str) -> bool:
        if self._has_pin(candidate):
            return bool(
                self._street_tokens.search(candidate)
                or self._location_tokens.search(candidate)
                or candidate.count(",") >= 2
            )
        if len(candidate.split()) > 15:
            return False
        if self._street_tokens.search(candidate) and self._location_tokens.search(candidate):
            return True
        return bool(
            re.search(r"\d", candidate)
            and candidate.count(",") >= 2
            and self._location_tokens.search(candidate)
        )

    def _has_pin(self, candidate: str) -> bool:
        for match in self._pin_pattern.finditer(candidate):
            if match.start() >= 2 and candidate[match.start() - 1] == "-":
                if candidate[match.start() - 2].isalpha():
                    continue
            if match.start() >= 1 and candidate[match.start() - 1].isalpha():
                continue
            return True
        return False


def _dedupe_and_sort(entities: list[DetectedEntity]) -> list[DetectedEntity]:
    by_key: dict[tuple[int, int, PIIType], DetectedEntity] = {}
    for entity in entities:
        key = (entity.start, entity.end, entity.pii_type)
        existing = by_key.get(key)
        if existing is None or entity.confidence > existing.confidence:
            by_key[key] = entity
    return sorted(by_key.values(), key=lambda item: (item.start, item.end, item.pii_type.value, item.source))
