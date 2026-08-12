from app.detectors.credit_card import CreditCardDetector
from app.detectors.dob import DOBDetector
from app.detectors.email import EmailDetector
from app.detectors.ip_address import IPAddressDetector
from app.detectors.phone import PhoneDetector
from app.detectors.ssn import SSNDetector
from app.models.entities import DetectedEntity, PIIType


class StructuredPIIDetector:
    def __init__(self) -> None:
        self.detectors = (
            EmailDetector(),
            PhoneDetector(),
            SSNDetector(),
            CreditCardDetector(),
            DOBDetector(),
            IPAddressDetector(),
        )

    def detect(self, text: str) -> list[DetectedEntity]:
        if not text:
            return []

        entities: list[DetectedEntity] = []
        for detector in self.detectors:
            entities.extend(detector.detect(text))

        return _dedupe_and_sort(entities)


def _dedupe_and_sort(entities: list[DetectedEntity]) -> list[DetectedEntity]:
    by_key: dict[tuple[int, int, PIIType, str], DetectedEntity] = {}
    for entity in entities:
        by_key[(entity.start, entity.end, entity.pii_type, entity.source)] = entity
    return sorted(
        by_key.values(),
        key=lambda entity: (entity.start, entity.end, entity.pii_type.value, entity.source),
    )
