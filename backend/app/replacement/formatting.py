import re
from datetime import date


MONTH_NAMES = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]


def apply_case_style(original: str, replacement: str) -> str:
    letters = [char for char in original if char.isalpha()]
    if letters and all(char.isupper() for char in letters):
        return replacement.upper()
    return replacement


def render_digits_with_template(
    template: str, replacement_digits: str, preserve_prefix_digits: int = 0
) -> str:
    original_digits = re.sub(r"\D", "", template)
    digits = replacement_digits
    if preserve_prefix_digits:
        digits = original_digits[:preserve_prefix_digits] + replacement_digits[preserve_prefix_digits:]
    if len(digits) < len(original_digits):
        digits = digits + ("0" * (len(original_digits) - len(digits)))

    iterator = iter(digits[: len(original_digits)])
    rendered: list[str] = []
    for char in template:
        rendered.append(next(iterator) if char.isdigit() else char)
    return "".join(rendered)


def render_dob_like(original: str, replacement_date: date) -> str:
    value = original.strip()
    if re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", value):
        return replacement_date.strftime("%Y-%m-%d")
    if re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", value):
        return replacement_date.strftime("%d/%m/%Y")
    if re.fullmatch(r"\d{1,2}-\d{1,2}-\d{4}", value):
        return replacement_date.strftime("%d-%m-%Y")
    if re.fullmatch(r"\d{1,2}\s+[A-Za-z]+\s+\d{4}", value):
        return f"{replacement_date.day} {MONTH_NAMES[replacement_date.month - 1]} {replacement_date.year}"
    if re.fullmatch(r"[A-Za-z]+\s+\d{1,2},?\s+\d{4}", value):
        return f"{MONTH_NAMES[replacement_date.month - 1]} {replacement_date.day}, {replacement_date.year}"
    return replacement_date.strftime("%Y-%m-%d")
