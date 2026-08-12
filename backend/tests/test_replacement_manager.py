import ipaddress
import logging
import re
from datetime import datetime

import pytest

from app.models import DetectedEntity, PIIType
from app.replacement import ReplacementManager
from app.replacement.manager import ReplacementPlanError
from app.replacement.normalization import normalize_for_replacement


TEST_CARD_VALUES = {
    "4111111111111111",
    "5555555555554444",
    "6011111111111117",
    "2223000048400011",
    "378282246310005",
    "371449635398431",
}


def entity(text: str, value: str, pii_type: PIIType, occurrence: int = 0) -> DetectedEntity:
    start = -1
    cursor = 0
    for _ in range(occurrence + 1):
        start = text.index(value, cursor)
        cursor = start + len(value)
    return DetectedEntity(
        text=value,
        start=start,
        end=start + len(value),
        pii_type=pii_type,
        confidence=0.99,
        source="test",
    )


def standalone(value: str, pii_type: PIIType) -> DetectedEntity:
    return DetectedEntity(
        text=value,
        start=0,
        end=len(value),
        pii_type=pii_type,
        confidence=0.99,
        source="test",
    )


def assert_different(entity_: DetectedEntity, replacement: str) -> None:
    assert replacement
    assert normalize_for_replacement(entity_.pii_type, entity_.text) != normalize_for_replacement(
        entity_.pii_type, replacement
    )


def test_person_replacement_consistency_case_and_seed_behavior() -> None:
    lower = standalone("Rahul Mehta", PIIType.PERSON)
    upper = standalone("RAHUL MEHTA", PIIType.PERSON)

    manager = ReplacementManager(seed=42)
    first = manager.get_replacement(lower)
    second = manager.get_replacement(lower)
    upper_rendered = manager.get_replacement(upper)

    assert first == second
    assert upper_rendered == first.upper()
    assert first == ReplacementManager(seed=42).get_replacement(lower)
    assert first != ReplacementManager(seed=99).get_replacement(lower)
    assert_different(lower, first)


def test_different_people_prefer_distinct_replacements() -> None:
    manager = ReplacementManager(seed=42)
    first = manager.get_replacement(standalone("Rahul Mehta", PIIType.PERSON))
    second = manager.get_replacement(standalone("Priya Shah", PIIType.PERSON))

    assert first != second


def test_company_replacement_preserves_suffix_and_case() -> None:
    manager = ReplacementManager(seed=42)
    private = manager.get_replacement(standalone("Aurora Systems Private Limited", PIIType.COMPANY))
    limited = manager.get_replacement(standalone("Northstar Securities Limited", PIIType.COMPANY))
    llp = manager.get_replacement(standalone("Example Finance LLP", PIIType.COMPANY))
    upper = manager.get_replacement(standalone("SUMMIT BANK LIMITED", PIIType.COMPANY))

    assert private.endswith("Private Limited")
    assert limited.endswith("Limited")
    assert llp.endswith("LLP")
    assert upper == upper.upper()
    assert len({private, limited, llp}) == 3


def test_email_replacement_uses_reserved_domain_and_unique_local_parts() -> None:
    manager = ReplacementManager(seed=42)
    first_entity = standalone("rahul@company.example", PIIType.EMAIL)
    second_entity = standalone("other@company.example", PIIType.EMAIL)
    first = manager.get_replacement(first_entity)
    second = manager.get_replacement(second_entity)

    assert first.endswith("@example.com")
    assert second.endswith("@example.com")
    assert re.fullmatch(r"[a-z]+\.[a-z]+\d{4}@example\.com", first)
    assert first != second
    assert "company.example" not in first
    assert_different(first_entity, first)


def test_phone_replacement_preserves_separators_and_normalized_identity() -> None:
    manager = ReplacementManager(seed=42)
    spaced = standalone("+91 98765 43210", PIIType.PHONE)
    hyphenated = standalone("+91-98765-43210", PIIType.PHONE)
    landline = standalone("+91 20 4505 3237", PIIType.PHONE)

    spaced_replacement = manager.get_replacement(spaced)
    hyphen_replacement = manager.get_replacement(hyphenated)
    landline_replacement = manager.get_replacement(landline)

    assert re.fullmatch(r"\+91 \d{5} \d{5}", spaced_replacement)
    assert re.fullmatch(r"\+91-\d{5}-\d{5}", hyphen_replacement)
    assert re.sub(r"\D", "", spaced_replacement) == re.sub(r"\D", "", hyphen_replacement)
    assert re.fullmatch(r"\+91 \d{2} \d{4} \d{4}", landline_replacement)
    assert_different(spaced, spaced_replacement)


def test_ssn_replacement_uses_reserved_visual_strategy() -> None:
    manager = ReplacementManager(seed=42)
    first = standalone("123-45-6789", PIIType.SSN)
    second = standalone("234-56-7890", PIIType.SSN)

    first_replacement = manager.get_replacement(first)
    second_replacement = manager.get_replacement(second)

    assert re.fullmatch(r"000-\d{2}-\d{4}", first_replacement)
    assert first_replacement != second_replacement
    assert_different(first, first_replacement)


def test_credit_card_replacement_uses_test_safe_pool_and_preserves_style() -> None:
    manager = ReplacementManager(seed=42)
    spaced = standalone("4111 1111 1111 1111", PIIType.CREDIT_CARD)
    hyphenated = standalone("4111-1111-1111-1111", PIIType.CREDIT_CARD)

    spaced_replacement = manager.get_replacement(spaced)
    hyphen_replacement = manager.get_replacement(hyphenated)

    assert re.sub(r"\D", "", spaced_replacement) in TEST_CARD_VALUES
    assert re.sub(r"\D", "", hyphen_replacement) in TEST_CARD_VALUES
    assert " " in spaced_replacement
    assert "-" in hyphen_replacement
    assert_different(spaced, spaced_replacement)


@pytest.mark.parametrize(
    "value,pattern",
    [
        ("12/04/1990", r"\d{2}/\d{2}/\d{4}"),
        ("12-04-1990", r"\d{2}-\d{2}-\d{4}"),
        ("1990-04-12", r"\d{4}-\d{2}-\d{2}"),
        ("12 April 1990", r"\d{1,2} [A-Z][a-z]+ \d{4}"),
        ("April 12, 1990", r"[A-Z][a-z]+ \d{1,2}, \d{4}"),
    ],
)
def test_dob_replacement_preserves_supported_formats(value: str, pattern: str) -> None:
    original = standalone(value, PIIType.DOB)
    replacement = ReplacementManager(seed=42).get_replacement(original)

    assert re.fullmatch(pattern, replacement)
    # Validate rendered date by trying the common numeric/month-name formats.
    if "/" in replacement:
        datetime.strptime(replacement, "%d/%m/%Y")
    elif re.fullmatch(r"\d{2}-\d{2}-\d{4}", replacement):
        datetime.strptime(replacement, "%d-%m-%Y")
    elif re.fullmatch(r"\d{4}-\d{2}-\d{2}", replacement):
        datetime.strptime(replacement, "%Y-%m-%d")
    assert_different(original, replacement)


def test_ip_replacement_uses_documentation_ranges() -> None:
    original = standalone("8.8.8.8", PIIType.IP_ADDRESS)
    replacement = ReplacementManager(seed=42).get_replacement(original)
    ip = ipaddress.ip_address(replacement)

    assert any(
        ip in ipaddress.ip_network(network)
        for network in ["192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24"]
    )
    assert_different(original, replacement)


def test_address_replacement_single_and_multiline_style() -> None:
    manager = ReplacementManager(seed=42)
    single = standalone(
        "201, Example Tower, Baner, Pune - 411045, Maharashtra, India", PIIType.ADDRESS
    )
    multiline = standalone(
        "801, Example Tower\nBaner, Pune - 411045\nMaharashtra, India", PIIType.ADDRESS
    )

    single_replacement = manager.get_replacement(single)
    multiline_replacement = manager.get_replacement(multiline)

    assert single_replacement
    assert "\n" not in single_replacement
    assert "\n" in multiline_replacement
    assert re.search(r"\b\d{6}\b", single_replacement)
    assert "Telephone" not in single_replacement
    assert_different(single, single_replacement)


def test_all_nine_replacement_plan() -> None:
    text = (
        "Rahul Mehta rahul@example.org +91 98765 43210 Aurora Systems Private Limited "
        "10 Example Road, Pune - 411045, Maharashtra, India 123-45-6789 "
        "4111 1111 1111 1111 12/04/1990 8.8.8.8"
    )
    values = [
        ("Rahul Mehta", PIIType.PERSON),
        ("rahul@example.org", PIIType.EMAIL),
        ("+91 98765 43210", PIIType.PHONE),
        ("Aurora Systems Private Limited", PIIType.COMPANY),
        ("10 Example Road, Pune - 411045, Maharashtra, India", PIIType.ADDRESS),
        ("123-45-6789", PIIType.SSN),
        ("4111 1111 1111 1111", PIIType.CREDIT_CARD),
        ("12/04/1990", PIIType.DOB),
        ("8.8.8.8", PIIType.IP_ADDRESS),
    ]
    entities = [entity(text, value, pii_type) for value, pii_type in values]

    plan = ReplacementManager(seed=42).plan(entities)

    assert len(plan) == 9
    assert {item.pii_type for item in plan} == set(PIIType)
    for item in plan:
        assert item.start == item.entity.start
        assert item.end == item.entity.end
        assert_different(item.entity, item.replacement)


def test_repeated_entities_share_replacements_across_manager_lifetime() -> None:
    manager = ReplacementManager(seed=42)

    for pii_type, value in [
        (PIIType.PERSON, "Rahul Mehta"),
        (PIIType.EMAIL, "rahul@example.org"),
        (PIIType.PHONE, "+91 98765 43210"),
        (PIIType.COMPANY, "Aurora Systems Private Limited"),
    ]:
        first = manager.get_replacement(standalone(value, pii_type))
        second = manager.get_replacement(standalone(value, pii_type))
        assert first == second


def test_planner_rejects_overlaps_and_accepts_adjacency() -> None:
    adjacent_text = "a@example.com+91 98765 43210"
    adjacent = [
        entity(adjacent_text, "a@example.com", PIIType.EMAIL),
        entity(adjacent_text, "+91 98765 43210", PIIType.PHONE),
    ]
    assert len(ReplacementManager(seed=42).plan(adjacent)) == 2

    overlap_text = "Rahul Mehta"
    overlapping = [
        standalone("Rahul Mehta", PIIType.PERSON),
        DetectedEntity(
            text="Mehta",
            start=6,
            end=11,
            pii_type=PIIType.COMPANY,
            confidence=0.9,
            source="test",
        ),
    ]
    with pytest.raises(ReplacementPlanError):
        ReplacementManager(seed=42).plan(overlapping)


def test_right_to_left_plan_order() -> None:
    text = "rahul@example.org +91 98765 43210"
    entities = [
        entity(text, "rahul@example.org", PIIType.EMAIL),
        entity(text, "+91 98765 43210", PIIType.PHONE),
    ]

    plan = ReplacementManager(seed=42).plan_right_to_left(entities)

    assert [item.start for item in plan] == sorted([item.start for item in plan], reverse=True)


def test_stats_are_count_only() -> None:
    manager = ReplacementManager(seed=42)
    manager.get_replacement(standalone("Rahul Mehta", PIIType.PERSON))
    manager.get_replacement(standalone("rahul@example.org", PIIType.EMAIL))

    stats = manager.stats()

    assert stats.total == 2
    assert stats.counts_by_type["PERSON"] == 1
    assert stats.counts_by_type["EMAIL"] == 1


def test_generation_does_not_log_original_values(caplog) -> None:
    caplog.set_level(logging.INFO)
    secret = "Rahul Mehta"

    ReplacementManager(seed=42).get_replacement(standalone(secret, PIIType.PERSON))

    assert secret not in caplog.text
