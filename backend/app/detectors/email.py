import re

from app.models.entities import DetectedEntity, PIIType


class EmailDetector:
    source = "regex_email"
    _pattern = re.compile(
        r"(?<![A-Za-z0-9._%+-])"
        r"[A-Za-z0-9](?:[A-Za-z0-9._%+-]{0,62}[A-Za-z0-9])?"
        r"@"
        r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+"
        r"[A-Za-z]{2,63}"
        r"(?![A-Za-z0-9._%+-])",
        re.IGNORECASE,
    )

    def detect(self, text: str) -> list[DetectedEntity]:
        if not text:
            return []

        entities: list[DetectedEntity] = []
        for match in self._pattern.finditer(text):
            candidate = match.group(0)
            if self._is_valid(candidate):
                entities.append(
                    DetectedEntity(
                        text=candidate,
                        start=match.start(),
                        end=match.end(),
                        pii_type=PIIType.EMAIL,
                        confidence=0.98,
                        source=self.source,
                    )
                )
        return entities

    @staticmethod
    def _is_valid(candidate: str) -> bool:
        local, domain = candidate.rsplit("@", 1)
        if ".." in local or ".." in domain:
            return False
        if local.startswith(".") or local.endswith("."):
            return False
        return bool(local and domain and "." in domain)
