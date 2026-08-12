from typing import Protocol

from app.models.entities import DetectedEntity


class Detector(Protocol):
    def detect(self, text: str) -> list[DetectedEntity]:
        ...
