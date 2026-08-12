import re

from app.detectors.validators import is_valid_date
from app.models.entities import DetectedEntity, PIIType


class DOBDetector:
    source = "context_dob"
    _context_pattern = re.compile(
        r"\b(?:D\.?O\.?B\.?|Date\s+of\s+Birth|Birth\s+Date|Born(?:\s+on)?)\b"
        r"\s*(?::|-)?\s*",
        re.IGNORECASE,
    )
    _date_pattern = re.compile(
        r"\b(?:"
        r"\d{1,2}[/-]\d{1,2}[/-]\d{4}|"
        r"\d{4}-\d{1,2}-\d{1,2}|"
        r"\d{1,2}\s+"
        r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t|tember)?|Oct(?:ober)?|Nov(?:ember)?|"
        r"Dec(?:ember)?)\s+\d{4}|"
        r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t|tember)?|Oct(?:ober)?|Nov(?:ember)?|"
        r"Dec(?:ember)?)\s+\d{1,2},?\s+\d{4}"
        r")\b",
        re.IGNORECASE,
    )

    def detect(self, text: str) -> list[DetectedEntity]:
        if not text:
            return []

        entities: list[DetectedEntity] = []
        for context_match in self._context_pattern.finditer(text):
            search_start = context_match.end()
            search_end = min(len(text), search_start + 40)
            date_match = self._date_pattern.search(text, search_start, search_end)
            if date_match is None:
                continue
            candidate = date_match.group(0)
            if is_valid_date(candidate):
                entities.append(
                    DetectedEntity(
                        text=candidate,
                        start=date_match.start(),
                        end=date_match.end(),
                        pii_type=PIIType.DOB,
                        confidence=0.95,
                        source=self.source,
                    )
                )
        return entities
