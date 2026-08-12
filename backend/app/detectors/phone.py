import re

from app.detectors.validators import normalize_digits
from app.models.entities import DetectedEntity, PIIType


class PhoneDetector:
    source = "regex_phone"
    _mobile_pattern = re.compile(
        r"(?<![A-Za-z0-9])(?:\+?91[\s-]*)?[6-9]\d{4}[\s-]?\d{5}(?![A-Za-z0-9])"
    )
    _landline_pattern = re.compile(
        r"(?<![A-Za-z0-9])(?:\+?91[\s-]*)?(?:\(?0?\d{2,4}\)?[\s-]*)"
        r"(?:\d{3,5}[\s-]\d{4}|\d{8})(?![A-Za-z0-9])"
    )
    _context_pattern = re.compile(
        r"\b(?:Telephone|Tel|Phone|Mobile|Mob|Contact)\b", re.IGNORECASE
    )

    def detect(self, text: str) -> list[DetectedEntity]:
        if not text:
            return []

        entities: list[DetectedEntity] = []
        for pattern, structural_confidence in (
            (self._mobile_pattern, 0.88),
            (self._landline_pattern, 0.82),
        ):
            for match in pattern.finditer(text):
                candidate = match.group(0)
                if self._is_valid_phone_candidate(candidate, text, match.start(), match.end()):
                    confidence = (
                        0.94
                        if self._has_phone_context(text, match.start(), match.end())
                        else structural_confidence
                    )
                    entities.append(
                        DetectedEntity(
                            text=candidate,
                            start=match.start(),
                            end=match.end(),
                            pii_type=PIIType.PHONE,
                            confidence=confidence,
                            source=self.source,
                        )
                    )

        return _dedupe_entities(entities)

    def _is_valid_phone_candidate(
        self, candidate: str, text: str, start: int, end: int
    ) -> bool:
        digits = normalize_digits(candidate)
        if digits.startswith("91") and len(digits) > 10:
            national = digits[2:]
        else:
            national = digits

        if not 10 <= len(national) <= 11:
            return False
        if len(set(national)) == 1:
            return False
        if self._near_negative_label(text, start):
            return False

        is_mobile = len(national) == 10 and national[0] in "6789"
        if is_mobile:
            return True

        return self._has_phone_context(text, start, end)

    def _has_phone_context(self, text: str, start: int, end: int) -> bool:
        window = text[max(0, start - 40) : min(len(text), end + 15)]
        return self._context_pattern.search(window) is not None

    @staticmethod
    def _near_negative_label(text: str, start: int) -> bool:
        window = text[max(0, start - 35) : start].lower()
        negative_terms = (
            "cin",
            "din",
            "sebi",
            "registration",
            "shares",
            "share",
            "section",
            "regulation",
            "pin",
            "pincode",
            "fiscal",
            "year",
            "dated",
        )
        return any(term in window for term in negative_terms)


def _dedupe_entities(entities: list[DetectedEntity]) -> list[DetectedEntity]:
    by_span: dict[tuple[int, int, PIIType], DetectedEntity] = {}
    for entity in entities:
        key = (entity.start, entity.end, entity.pii_type)
        existing = by_span.get(key)
        if existing is None or entity.confidence > existing.confidence:
            by_span[key] = entity
    return sorted(by_span.values(), key=lambda item: (item.start, item.end, item.pii_type.value))
