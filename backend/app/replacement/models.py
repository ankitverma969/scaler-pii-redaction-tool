from dataclasses import dataclass

from app.models import DetectedEntity, PIIType


@dataclass(frozen=True)
class PlannedReplacement:
    entity: DetectedEntity
    replacement: str

    @property
    def start(self) -> int:
        return self.entity.start

    @property
    def end(self) -> int:
        return self.entity.end

    @property
    def pii_type(self) -> PIIType:
        return self.entity.pii_type


@dataclass(frozen=True)
class ReplacementStats:
    total: int
    counts_by_type: dict[str, int]
