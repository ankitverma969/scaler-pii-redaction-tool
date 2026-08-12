import re

from app.detectors.validators import normalize_digits, passes_luhn
from app.models.entities import DetectedEntity, PIIType


class CreditCardDetector:
    source = "luhn_credit_card"
    _pattern = re.compile(
        r"(?<![A-Za-z0-9])"
        r"(?:\d{13,19}|\d{4}(?:[ -]\d{4}){2,4}|\d{4}[ -]\d{6}[ -]\d{5})"
        r"(?![A-Za-z0-9])"
    )

    def detect(self, text: str) -> list[DetectedEntity]:
        if not text:
            return []

        entities: list[DetectedEntity] = []
        for match in self._pattern.finditer(text):
            candidate = match.group(0)
            digits = normalize_digits(candidate)
            if not 13 <= len(digits) <= 19:
                continue
            if self._looks_like_phone(candidate, digits):
                continue
            if passes_luhn(candidate):
                entities.append(
                    DetectedEntity(
                        text=candidate,
                        start=match.start(),
                        end=match.end(),
                        pii_type=PIIType.CREDIT_CARD,
                        confidence=0.97,
                        source=self.source,
                    )
                )
        return entities

    @staticmethod
    def _looks_like_phone(candidate: str, digits: str) -> bool:
        stripped = candidate.strip()
        return stripped.startswith("+") or (
            digits.startswith("91") and len(digits) in {12, 13}
        )
