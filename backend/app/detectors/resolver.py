from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from app.models.entities import DetectedEntity, PIIType


TYPE_PRIORITY: dict[PIIType, int] = {
    PIIType.EMAIL: 0,
    PIIType.SSN: 1,
    PIIType.CREDIT_CARD: 2,
    PIIType.IP_ADDRESS: 3,
    PIIType.PHONE: 4,
    PIIType.DOB: 5,
    PIIType.ADDRESS: 6,
    PIIType.COMPANY: 7,
    PIIType.PERSON: 8,
}

SOURCE_PRIORITY: dict[str, int] = {
    "regex_email": 100,
    "regex_ssn": 95,
    "luhn_credit_card": 92,
    "validated_ipv4": 90,
    "regex_phone": 88,
    "context_dob": 85,
    "address_context": 80,
    "legal_suffix_company": 75,
    "context_person": 70,
    "address_heuristic": 65,
    "spacy_company": 55,
    "spacy_person": 50,
}


@dataclass(frozen=True)
class ResolutionResult:
    entities: list[DetectedEntity]
    rejected_by_reason: dict[str, int]


class EntityResolver:
    def resolve(
        self, text: str, candidates: Iterable[DetectedEntity]
    ) -> ResolutionResult:
        valid_candidates = [candidate for candidate in candidates if _valid(candidate, text)]
        deduped, duplicate_rejections = self._dedupe_exact(valid_candidates)
        same_type_resolved, same_type_rejections = self._resolve_same_type(deduped)
        final_entities, overlap_rejections = self._resolve_cross_type(same_type_resolved, text)

        reasons = Counter()
        reasons.update(duplicate_rejections)
        reasons.update(same_type_rejections)
        reasons.update(overlap_rejections)
        return ResolutionResult(
            entities=sorted(
                final_entities,
                key=lambda entity: (
                    entity.start,
                    entity.end,
                    TYPE_PRIORITY[entity.pii_type],
                    entity.source,
                ),
            ),
            rejected_by_reason=dict(reasons),
        )

    def _dedupe_exact(
        self, candidates: list[DetectedEntity]
    ) -> tuple[list[DetectedEntity], dict[str, int]]:
        grouped: dict[tuple[int, int, PIIType], list[DetectedEntity]] = {}
        for candidate in candidates:
            grouped.setdefault((candidate.start, candidate.end, candidate.pii_type), []).append(
                candidate
            )

        accepted: list[DetectedEntity] = []
        rejected = 0
        for group in grouped.values():
            selected = max(group, key=_same_type_selection_key)
            accepted.append(selected)
            rejected += len(group) - 1
        return accepted, {"exact_duplicate": rejected} if rejected else {}

    def _resolve_same_type(
        self, candidates: list[DetectedEntity]
    ) -> tuple[list[DetectedEntity], dict[str, int]]:
        accepted: list[DetectedEntity] = []
        rejected = 0
        for pii_type in PIIType:
            type_candidates = [candidate for candidate in candidates if candidate.pii_type == pii_type]
            selected: list[DetectedEntity] = []
            for candidate in sorted(type_candidates, key=_same_type_selection_key, reverse=True):
                if any(_overlap(candidate, existing) for existing in selected):
                    rejected += 1
                    continue
                selected.append(candidate)
            accepted.extend(selected)
        return accepted, {"same_type_overlap": rejected} if rejected else {}

    def _resolve_cross_type(
        self, candidates: list[DetectedEntity], text: str
    ) -> tuple[list[DetectedEntity], dict[str, int]]:
        selected: list[DetectedEntity] = []
        rejected = Counter()

        for candidate in sorted(candidates, key=lambda entity: _cross_type_selection_key(entity, text), reverse=True):
            overlaps = [entity for entity in selected if _overlap(candidate, entity)]
            if not overlaps:
                selected.append(candidate)
                continue

            if all(_candidate_wins(candidate, existing, text) for existing in overlaps):
                for existing in overlaps:
                    selected.remove(existing)
                    rejected[_overlap_reason(existing, candidate)] += 1
                selected.append(candidate)
            else:
                winner = max(overlaps, key=lambda entity: _cross_type_selection_key(entity, text))
                rejected[_overlap_reason(candidate, winner)] += 1

        return selected, dict(rejected)


def _valid(entity: DetectedEntity, text: str) -> bool:
    return (
        0 <= entity.start < entity.end <= len(text)
        and entity.text == text[entity.start : entity.end]
        and 0.0 <= entity.confidence <= 1.0
    )


def _same_type_selection_key(entity: DetectedEntity) -> tuple[int, float, int, int, str]:
    length = entity.end - entity.start
    if entity.pii_type in {PIIType.ADDRESS, PIIType.COMPANY}:
        completeness = length
        confidence = entity.confidence
    else:
        completeness = int(entity.confidence * 1000)
        confidence = length / 1000
    return (
        completeness,
        confidence,
        SOURCE_PRIORITY.get(entity.source, 0),
        -entity.start,
        entity.source,
    )


def _cross_type_selection_key(entity: DetectedEntity, text: str) -> tuple[int, float, int, int, str]:
    return (
        -TYPE_PRIORITY[entity.pii_type],
        _contextual_confidence(entity, text),
        SOURCE_PRIORITY.get(entity.source, 0),
        entity.end - entity.start,
        entity.source,
    )


def _contextual_confidence(entity: DetectedEntity, text: str) -> float:
    if entity.pii_type == PIIType.PHONE and _has_phone_context(entity, text):
        return max(entity.confidence, 0.99)
    return entity.confidence


def _candidate_wins(candidate: DetectedEntity, existing: DetectedEntity, text: str) -> bool:
    if candidate.pii_type == PIIType.PHONE and existing.pii_type == PIIType.CREDIT_CARD:
        if _has_phone_context(candidate, text):
            return True
    if candidate.pii_type == PIIType.CREDIT_CARD and existing.pii_type == PIIType.PHONE:
        if _has_phone_context(existing, text):
            return False
    return _cross_type_selection_key(candidate, text) > _cross_type_selection_key(existing, text)


def _overlap(first: DetectedEntity, second: DetectedEntity) -> bool:
    return first.start < second.end and second.start < first.end


def _contains(first: DetectedEntity, second: DetectedEntity) -> bool:
    return first.start <= second.start and first.end >= second.end


def _overlap_reason(rejected: DetectedEntity, winner: DetectedEntity) -> str:
    if winner.pii_type == PIIType.EMAIL:
        return "semantic_inside_email"
    if winner.pii_type == PIIType.COMPANY and rejected.pii_type == PIIType.PERSON:
        return "person_inside_company"
    if winner.pii_type == PIIType.ADDRESS and rejected.pii_type in {PIIType.PERSON, PIIType.COMPANY}:
        return "semantic_inside_address"
    if _contains(winner, rejected):
        return "lower_priority_contained_overlap"
    if _contains(rejected, winner):
        return "higher_priority_contained_overlap"
    return "lower_priority_partial_overlap"


def _has_phone_context(entity: DetectedEntity, text: str) -> bool:
    window = text[max(0, entity.start - 40) : min(len(text), entity.end + 20)]
    return bool(
        entity.pii_type == PIIType.PHONE
        and re.search(r"\b(?:Telephone|Tel|Phone|Mobile|Mob|Contact)\b", window, re.I)
    )
