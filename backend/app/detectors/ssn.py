import re

from app.detectors.validators import is_valid_ssn
from app.models.entities import DetectedEntity, PIIType


class SSNDetector:
    source = "regex_ssn"
    _pattern = re.compile(r"(?<![A-Za-z0-9])\d{3}-\d{2}-\d{4}(?![A-Za-z0-9])")

    def detect(self, text: str) -> list[DetectedEntity]:
        if not text:
            return []

        entities: list[DetectedEntity] = []
        for match in self._pattern.finditer(text):
            candidate = match.group(0)
            if is_valid_ssn(candidate):
                entities.append(
                    DetectedEntity(
                        text=candidate,
                        start=match.start(),
                        end=match.end(),
                        pii_type=PIIType.SSN,
                        confidence=0.96,
                        source=self.source,
                    )
                )
        return entities
