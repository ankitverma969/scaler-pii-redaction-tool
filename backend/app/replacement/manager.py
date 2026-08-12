from __future__ import annotations

from collections import Counter, defaultdict

from app.core.config import settings
from app.models import DetectedEntity, PIIType
from app.replacement.generators import ReplacementGenerators, differs_after_normalization
from app.replacement.models import PlannedReplacement, ReplacementStats
from app.replacement.normalization import normalize_for_replacement


class ReplacementPlanError(ValueError):
    pass


class ReplacementManager:
    def __init__(self, seed: int | None = None) -> None:
        self.seed = settings.default_redaction_seed if seed is None else seed
        self._generators = ReplacementGenerators(self.seed)
        self._canonical_by_key: dict[tuple[PIIType, str], str] = {}
        self._generated_by_type: dict[PIIType, set[str]] = defaultdict(set)
        self._counts_by_type: Counter[str] = Counter()

    def get_replacement(self, entity: DetectedEntity) -> str:
        key = self._mapping_key(entity)
        canonical = self._canonical_by_key.get(key)
        if canonical is None:
            canonical = self._generate_unique_canonical(entity, key)
            self._canonical_by_key[key] = canonical
            self._counts_by_type[entity.pii_type.value] += 1
        rendered = self._generators.render(entity.pii_type, entity.text, canonical)
        if not differs_after_normalization(entity.pii_type, entity.text, rendered):
            canonical = self._generate_unique_canonical(entity, key, force_retry_start=100)
            self._canonical_by_key[key] = canonical
            rendered = self._generators.render(entity.pii_type, entity.text, canonical)
        return rendered

    def plan(self, entities: list[DetectedEntity]) -> list[PlannedReplacement]:
        self._validate_plan_entities(entities)
        return [
            PlannedReplacement(entity=entity, replacement=self.get_replacement(entity))
            for entity in sorted(entities, key=lambda item: (item.start, item.end, item.pii_type.value))
        ]

    def plan_right_to_left(self, entities: list[DetectedEntity]) -> list[PlannedReplacement]:
        return sorted(self.plan(entities), key=lambda item: item.start, reverse=True)

    def stats(self) -> ReplacementStats:
        return ReplacementStats(
            total=sum(self._counts_by_type.values()),
            counts_by_type={pii_type.value: self._counts_by_type.get(pii_type.value, 0) for pii_type in PIIType},
        )

    def _mapping_key(self, entity: DetectedEntity) -> tuple[PIIType, str]:
        return (entity.pii_type, normalize_for_replacement(entity.pii_type, entity.text))

    def _generate_unique_canonical(
        self,
        entity: DetectedEntity,
        key: tuple[PIIType, str],
        force_retry_start: int = 0,
    ) -> str:
        used = self._generated_by_type[entity.pii_type]
        for retry in range(force_retry_start, force_retry_start + 25):
            canonical = self._generators.generate_canonical(
                entity.pii_type, entity.text, key[1], retry=retry
            )
            rendered = self._generators.render(entity.pii_type, entity.text, canonical)
            normalized_rendered = normalize_for_replacement(entity.pii_type, rendered)
            if (
                normalized_rendered not in used
                and differs_after_normalization(entity.pii_type, entity.text, rendered)
            ):
                used.add(normalized_rendered)
                return canonical

        suffix = len(used) + 1
        fallback = f"{self._generators.generate_canonical(entity.pii_type, entity.text, key[1], retry=999)} {suffix}"
        used.add(normalize_for_replacement(entity.pii_type, fallback))
        return fallback

    @staticmethod
    def _validate_plan_entities(entities: list[DetectedEntity]) -> None:
        sorted_entities = sorted(entities, key=lambda item: (item.start, item.end))
        previous: DetectedEntity | None = None
        for entity in sorted_entities:
            if entity.pii_type not in set(PIIType):
                raise ReplacementPlanError(f"Unsupported PII type: {entity.pii_type}")
            if not entity.text:
                raise ReplacementPlanError("Cannot plan replacement for empty entity text")
            if entity.start < 0 or entity.end <= entity.start:
                raise ReplacementPlanError("Invalid entity span")
            if previous is not None and previous.end > entity.start:
                raise ReplacementPlanError("Replacement plan entities must not overlap")
            previous = entity
