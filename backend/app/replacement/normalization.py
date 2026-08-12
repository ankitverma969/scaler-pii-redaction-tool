import ipaddress
import re

from app.detectors.validators import normalize_digits, parse_supported_date
from app.models import PIIType


def normalize_for_replacement(pii_type: PIIType, value: str) -> str:
    normalized = value.strip()

    if pii_type in {PIIType.PERSON, PIIType.COMPANY, PIIType.ADDRESS}:
        return _collapse_whitespace(normalized).casefold()

    if pii_type == PIIType.EMAIL:
        return normalized.casefold()

    if pii_type in {PIIType.PHONE, PIIType.SSN, PIIType.CREDIT_CARD}:
        return normalize_digits(normalized)

    if pii_type == PIIType.DOB:
        parsed = parse_supported_date(normalized)
        return parsed.isoformat() if parsed is not None else _collapse_whitespace(normalized).casefold()

    if pii_type == PIIType.IP_ADDRESS:
        try:
            return str(ipaddress.ip_address(normalized))
        except ValueError:
            return normalized.casefold()

    return _collapse_whitespace(normalized).casefold()


def _collapse_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())
