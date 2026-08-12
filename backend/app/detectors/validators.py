import ipaddress
import re
from datetime import date


MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


def normalize_digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def passes_luhn(value: str) -> bool:
    digits = [int(char) for char in normalize_digits(value)]
    if not 13 <= len(digits) <= 19:
        return False

    checksum = 0
    double = False
    for digit in reversed(digits):
        if double:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
        double = not double
    return checksum % 10 == 0


def is_valid_ssn(value: str) -> bool:
    match = re.fullmatch(r"(\d{3})-(\d{2})-(\d{4})", value)
    if not match:
        return False

    area, group, serial = (int(part) for part in match.groups())
    if area == 0 or area == 666 or area >= 900:
        return False
    if group == 0 or serial == 0:
        return False
    return True


def is_valid_ipv4(value: str) -> bool:
    try:
        return ipaddress.ip_address(value).version == 4
    except ValueError:
        return False


def parse_supported_date(value: str) -> date | None:
    value = re.sub(r"\s+", " ", value.strip())

    iso_match = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", value)
    if iso_match:
        return _date_from_parts(
            int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3))
        )

    slash_or_dash = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", value)
    if slash_or_dash:
        first, second, year = (int(part) for part in slash_or_dash.groups())
        return _first_valid_date(
            (year, second, first),
            (year, first, second),
        )

    day_month = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", value)
    if day_month:
        month = MONTHS.get(day_month.group(2).lower())
        if month is None:
            return None
        return _date_from_parts(int(day_month.group(3)), month, int(day_month.group(1)))

    month_day = re.fullmatch(r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})", value)
    if month_day:
        month = MONTHS.get(month_day.group(1).lower())
        if month is None:
            return None
        return _date_from_parts(int(month_day.group(3)), month, int(month_day.group(2)))

    return None


def is_valid_date(value: str) -> bool:
    return parse_supported_date(value) is not None


def _first_valid_date(*parts: tuple[int, int, int]) -> date | None:
    for year, month, day in parts:
        parsed = _date_from_parts(year, month, day)
        if parsed is not None:
            return parsed
    return None


def _date_from_parts(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None
