from __future__ import annotations

import hashlib
import ipaddress
import random
import re
from datetime import date, timedelta

from faker import Faker

from app.detectors.validators import normalize_digits, parse_supported_date
from app.models import PIIType
from app.replacement.formatting import (
    apply_case_style,
    render_digits_with_template,
    render_dob_like,
)
from app.replacement.normalization import normalize_for_replacement


TEST_CARD_POOL = {
    15: ["378282246310005", "371449635398431"],
    16: [
        "4111111111111111",
        "5555555555554444",
        "6011111111111117",
        "2223000048400011",
    ],
}

COMPANY_PREFIXES = [
    "Aster",
    "Bluehaven",
    "Northfield",
    "Summit",
    "Aarohan",
    "Cedar",
    "Silverline",
    "Maple",
]
COMPANY_MIDDLES = [
    "Ridge",
    "Harbor",
    "Industrial",
    "Advisory",
    "Meridian",
    "Vertex",
    "Capital",
    "Prime",
]
COMPANY_DOMAINS = [
    "Technologies",
    "Systems",
    "Industries",
    "Services",
    "Management",
    "Finance",
    "Securities",
    "Consulting",
]
INDIAN_CITIES = ["Pune", "Mumbai", "Bengaluru", "Chennai", "Hyderabad", "Ahmedabad"]
INDIAN_STATES = ["Maharashtra", "Karnataka", "Tamil Nadu", "Telangana", "Gujarat"]


def stable_int(seed: int, *parts: str) -> int:
    payload = "|".join([str(seed), *parts]).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


class ReplacementGenerators:
    def __init__(self, seed: int) -> None:
        self.seed = seed

    def generate_canonical(self, pii_type: PIIType, original: str, normalized: str, retry: int = 0) -> str:
        rng = random.Random(stable_int(self.seed, pii_type.value, normalized, str(retry)))
        fake = Faker("en_IN")
        fake.seed_instance(stable_int(self.seed, "faker", pii_type.value, normalized, str(retry)))

        if pii_type == PIIType.PERSON:
            return fake.name()
        if pii_type == PIIType.COMPANY:
            return self._company(original, rng)
        if pii_type == PIIType.ADDRESS:
            return self._address(original, rng)
        if pii_type == PIIType.EMAIL:
            return self._email(rng)
        if pii_type == PIIType.PHONE:
            return self._digits_for_phone(original, rng)
        if pii_type == PIIType.SSN:
            return "000" + f"{rng.randrange(1, 100):02d}" + f"{rng.randrange(1, 10000):04d}"
        if pii_type == PIIType.CREDIT_CARD:
            return self._credit_card(original, rng)
        if pii_type == PIIType.DOB:
            return self._dob(original, rng).isoformat()
        if pii_type == PIIType.IP_ADDRESS:
            return self._ip(rng)
        raise ValueError(f"Unsupported PII type: {pii_type}")

    def render(self, pii_type: PIIType, original: str, canonical: str) -> str:
        if pii_type in {PIIType.PERSON, PIIType.COMPANY}:
            return apply_case_style(original, canonical)
        if pii_type == PIIType.ADDRESS:
            return self._render_address(original, canonical)
        if pii_type == PIIType.PHONE:
            preserve = 2 if normalize_digits(original).startswith("91") and len(normalize_digits(original)) > 10 else 0
            return render_digits_with_template(original, canonical, preserve_prefix_digits=preserve)
        if pii_type == PIIType.SSN:
            return render_digits_with_template(original, canonical)
        if pii_type == PIIType.CREDIT_CARD:
            return render_digits_with_template(original, canonical)
        if pii_type == PIIType.DOB:
            parsed = date.fromisoformat(canonical)
            return render_dob_like(original, parsed)
        return canonical

    def _company(self, original: str, rng: random.Random) -> str:
        suffix = _company_suffix(original)
        core = " ".join(
            [
                rng.choice(COMPANY_PREFIXES),
                rng.choice(COMPANY_MIDDLES),
                rng.choice(COMPANY_DOMAINS),
            ]
        )
        return f"{core} {suffix}" if suffix else core

    def _address(self, original: str, rng: random.Random) -> str:
        number = rng.randrange(101, 999)
        tower = rng.choice(["Aster Tower", "Bluehaven Plaza", "Northfield Centre", "Summit Complex"])
        area = rng.choice(["Baner", "Andheri East", "Indiranagar", "Navrangpura"])
        city = rng.choice(INDIAN_CITIES)
        state = rng.choice(INDIAN_STATES)
        pin = f"{rng.randrange(100000, 999999)}"
        if "\n" in original:
            return f"{number}, {tower}\n{area}, {city} - {pin}\n{state}, India"
        return f"{number}, {tower}, {area}, {city} - {pin}, {state}, India"

    def _render_address(self, original: str, canonical: str) -> str:
        if "\n" in original:
            return canonical
        return re.sub(r"\s*\n\s*", ", ", canonical)

    def _email(self, rng: random.Random) -> str:
        first = rng.choice(["aarav", "meera", "rohan", "ananya", "vikram", "priya", "rahul"])
        last = rng.choice(["mehta", "nair", "reddy", "shah", "iyer", "kulkarni", "rao"])
        suffix = rng.randrange(1000, 9999)
        return f"{first}.{last}{suffix}@example.com"

    def _digits_for_phone(self, original: str, rng: random.Random) -> str:
        digits = normalize_digits(original)
        preserve = "91" if digits.startswith("91") and len(digits) > 10 else ""
        remaining = len(digits) - len(preserve)
        subscriber = ("000" + f"{rng.randrange(0, 10 ** max(remaining - 3, 1)):0{max(remaining - 3, 1)}d}")[-remaining:]
        return preserve + subscriber

    def _credit_card(self, original: str, rng: random.Random) -> str:
        source_digits = normalize_digits(original)
        pool = TEST_CARD_POOL.get(len(source_digits), TEST_CARD_POOL[16])
        choices = [card for card in pool if card != source_digits] or pool
        return choices[rng.randrange(0, len(choices))]

    def _dob(self, original: str, rng: random.Random) -> date:
        start = date(1946, 1, 1)
        end = date(2008, 12, 31)
        days = (end - start).days
        generated = start + timedelta(days=rng.randrange(0, days + 1))
        parsed_original = parse_supported_date(original)
        if parsed_original == generated:
            generated = generated + timedelta(days=1)
        return generated

    def _ip(self, rng: random.Random) -> str:
        networks = [
            ipaddress.ip_network("192.0.2.0/24"),
            ipaddress.ip_network("198.51.100.0/24"),
            ipaddress.ip_network("203.0.113.0/24"),
        ]
        network = networks[rng.randrange(0, len(networks))]
        host = rng.randrange(1, 255)
        return str(network.network_address + host)


def _company_suffix(value: str) -> str:
    patterns = [
        "Private Limited",
        "Pvt. Ltd.",
        "Pvt Ltd",
        "Limited",
        "Ltd.",
        "Ltd",
        "LLP",
        "L.L.P.",
    ]
    lowered = value.casefold().rstrip(" .")
    for suffix in patterns:
        if lowered.endswith(suffix.casefold().rstrip(".")):
            return suffix
    return ""


def differs_after_normalization(pii_type: PIIType, original: str, replacement: str) -> bool:
    return normalize_for_replacement(pii_type, original) != normalize_for_replacement(pii_type, replacement)
