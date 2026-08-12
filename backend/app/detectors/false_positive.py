from __future__ import annotations

import re
from collections.abc import Iterable

from app.detectors.semantic_filters import is_false_company, is_false_person, normalize_phrase
from app.models.entities import DetectedEntity, PIIType


CIN_PATTERN = re.compile(r"\b[UL]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}\b")
SEBI_ID_PATTERN = re.compile(r"\bIN[A-Z]\d{9}\b")
DIN_CONTEXT_PATTERN = re.compile(r"\bDIN\s*[:\-]?\s*\d{8}\b", re.IGNORECASE)
PIN_ONLY_PATTERN = re.compile(r"\b[1-9]\d{5}\b")
SECTION_PATTERN = re.compile(r"\bsection\s+\d+[A-Za-z()]*\b", re.IGNORECASE)
REGULATION_PATTERN = re.compile(r"\bregulation(?:s)?\s+\d+[A-Za-z()]*\b", re.IGNORECASE)
ORDINARY_DATE_CONTEXT = re.compile(
    r"\b(?:dated|incorporated|agreement|fiscal|year ended|offer opens|certificate)\b",
    re.IGNORECASE,
)
FINANCIAL_CONTEXT = re.compile(
    r"\b(?:INR|Rs\.?|million|lakh|crore|shares?|percentage|percent|%)\b",
    re.IGNORECASE,
)
GENERIC_HEADING_PHRASES = {
    "general information",
    "risk factors",
    "board of directors",
    "financial information",
    "capital structure",
    "the offer",
    "summary financial statements",
    "book running lead managers",
    "corporate governance",
}


def should_reject(entity: DetectedEntity, text: str) -> str | None:
    """Return a stable reason code if a candidate is a cross-cutting false positive."""
    if not _entity_invariants_hold(entity, text):
        return "invalid_span"

    if _is_protected_identifier(entity, text):
        return "protected_identifier"

    if _is_financial_or_legal_number(entity, text):
        return "financial_or_legal_number"

    normalized = normalize_phrase(entity.text)
    if normalized in GENERIC_HEADING_PHRASES:
        return "generic_heading"

    if entity.pii_type == PIIType.PERSON and is_false_person(entity.text):
        return "generic_heading"

    if entity.pii_type == PIIType.COMPANY and is_false_company(entity.text):
        return "regulator_or_committee"

    if entity.pii_type == PIIType.ADDRESS and _is_weak_standalone_location(entity.text):
        return "weak_address_location"

    return None


def filter_false_positives(
    entities: Iterable[DetectedEntity], text: str
) -> tuple[list[DetectedEntity], dict[str, int]]:
    accepted: list[DetectedEntity] = []
    rejected: dict[str, int] = {}
    for entity in entities:
        reason = should_reject(entity, text)
        if reason is None:
            accepted.append(entity)
        else:
            rejected[reason] = rejected.get(reason, 0) + 1
    return accepted, rejected


def _entity_invariants_hold(entity: DetectedEntity, text: str) -> bool:
    return (
        0 <= entity.start < entity.end <= len(text)
        and entity.text == text[entity.start : entity.end]
        and 0.0 <= entity.confidence <= 1.0
    )


def _is_protected_identifier(entity: DetectedEntity, text: str) -> bool:
    if CIN_PATTERN.fullmatch(entity.text) or SEBI_ID_PATTERN.fullmatch(entity.text):
        return True
    window = _context_window(text, entity.start, entity.end, before=20, after=20)
    if DIN_CONTEXT_PATTERN.search(window):
        return True
    return False


def _is_financial_or_legal_number(entity: DetectedEntity, text: str) -> bool:
    if entity.pii_type not in {
        PIIType.PHONE,
        PIIType.SSN,
        PIIType.CREDIT_CARD,
        PIIType.DOB,
        PIIType.IP_ADDRESS,
    }:
        return False

    window = _context_window(text, entity.start, entity.end, before=35, after=35)
    if SECTION_PATTERN.search(window) or REGULATION_PATTERN.search(window):
        return True
    if entity.pii_type == PIIType.DOB and ORDINARY_DATE_CONTEXT.search(window):
        return True
    if entity.pii_type in {PIIType.PHONE, PIIType.CREDIT_CARD, PIIType.SSN}:
        if FINANCIAL_CONTEXT.search(window):
            return True
        if entity.pii_type == PIIType.PHONE and PIN_ONLY_PATTERN.fullmatch(entity.text):
            return True
    return False


def _is_weak_standalone_location(value: str) -> bool:
    normalized = normalize_phrase(value)
    return normalized in {
        "pune",
        "mumbai",
        "maharashtra",
        "india",
        "government of maharashtra",
    }


def _context_window(
    text: str, start: int, end: int, before: int = 40, after: int = 40
) -> str:
    return text[max(0, start - before) : min(len(text), end + after)]
