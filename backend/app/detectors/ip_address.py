import re

from app.detectors.validators import is_valid_ipv4
from app.models.entities import DetectedEntity, PIIType


class IPAddressDetector:
    source = "validated_ipv4"
    _pattern = re.compile(r"(?<![A-Za-z0-9])(?:\d{1,3}\.){3}\d{1,3}(?![A-Za-z0-9])")

    def detect(self, text: str) -> list[DetectedEntity]:
        if not text:
            return []

        entities: list[DetectedEntity] = []
        for match in self._pattern.finditer(text):
            candidate = match.group(0)
            if is_valid_ipv4(candidate):
                entities.append(
                    DetectedEntity(
                        text=candidate,
                        start=match.start(),
                        end=match.end(),
                        pii_type=PIIType.IP_ADDRESS,
                        confidence=0.97,
                        source=self.source,
                    )
                )
        return entities
