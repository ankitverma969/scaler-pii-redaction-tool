from dataclasses import dataclass
from enum import Enum


class PIIType(str, Enum):
    PERSON = "PERSON"
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    COMPANY = "COMPANY"
    ADDRESS = "ADDRESS"
    SSN = "SSN"
    CREDIT_CARD = "CREDIT_CARD"
    DOB = "DOB"
    IP_ADDRESS = "IP_ADDRESS"


@dataclass(frozen=True)
class DetectedEntity:
    text: str
    start: int
    end: int
    pii_type: PIIType
    confidence: float
    source: str

    def __post_init__(self) -> None:
        if self.start < 0 or self.end <= self.start:
            raise ValueError("DetectedEntity offsets must use a non-empty [start, end) span")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("DetectedEntity confidence must be between 0.0 and 1.0")
        if not self.source:
            raise ValueError("DetectedEntity source must be non-empty")
