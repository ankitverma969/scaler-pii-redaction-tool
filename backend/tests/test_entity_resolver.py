import random

from app.detectors.resolver import EntityResolver, TYPE_PRIORITY
from app.models import DetectedEntity, PIIType


def entity(text: str, value: str, pii_type: PIIType, source: str, confidence: float = 0.8):
    start = text.index(value)
    return DetectedEntity(
        text=value,
        start=start,
        end=start + len(value),
        pii_type=pii_type,
        confidence=confidence,
        source=source,
    )


def manual(text: str, start: int, end: int, pii_type: PIIType, source: str, confidence: float = 0.8):
    return DetectedEntity(
        text=text[start:end],
        start=start,
        end=end,
        pii_type=pii_type,
        confidence=confidence,
        source=source,
    )


def assert_no_overlaps(entities):
    for previous, current in zip(entities, entities[1:]):
        assert previous.end <= current.start


def test_type_priority_is_explicit() -> None:
    assert list(TYPE_PRIORITY) == [
        PIIType.EMAIL,
        PIIType.SSN,
        PIIType.CREDIT_CARD,
        PIIType.IP_ADDRESS,
        PIIType.PHONE,
        PIIType.DOB,
        PIIType.ADDRESS,
        PIIType.COMPANY,
        PIIType.PERSON,
    ]


def test_exact_duplicate_keeps_highest_confidence() -> None:
    text = "Contact Person: Rahul Mehta"
    low = entity(text, "Rahul Mehta", PIIType.PERSON, "spacy_person", 0.88)
    high = entity(text, "Rahul Mehta", PIIType.PERSON, "context_person", 0.94)

    result = EntityResolver().resolve(text, [low, high])

    assert result.entities == [high]
    assert result.rejected_by_reason == {"exact_duplicate": 1}


def test_same_type_nested_prefers_complete_company_span() -> None:
    text = "Northstar Securities Limited"
    short = manual(text, 0, len("Northstar Securities"), PIIType.COMPANY, "spacy_company", 0.9)
    long = entity(text, text, PIIType.COMPANY, "legal_suffix_company", 0.95)

    result = EntityResolver().resolve(text, [short, long])

    assert result.entities == [long]
    assert result.rejected_by_reason == {"same_type_overlap": 1}


def test_same_type_nested_prefers_complete_address_span() -> None:
    text = "10 Example Road, Pune - 411001, Maharashtra, India"
    short = entity(text, "10 Example Road", PIIType.ADDRESS, "address_heuristic", 0.88)
    long = entity(text, text, PIIType.ADDRESS, "address_context", 0.93)

    result = EntityResolver().resolve(text, [short, long])

    assert result.entities == [long]


def test_email_wins_over_semantic_overlap() -> None:
    text = "alice.smith@example.com"
    email = entity(text, text, PIIType.EMAIL, "regex_email", 0.98)
    person = manual(text, 0, len("alice.smith"), PIIType.PERSON, "spacy_person", 0.9)

    result = EntityResolver().resolve(text, [person, email])

    assert result.entities == [email]
    assert result.rejected_by_reason == {"semantic_inside_email": 1}


def test_company_containing_person_wins() -> None:
    text = "John Example Limited"
    person = entity(text, "John Example", PIIType.PERSON, "spacy_person", 0.9)
    company = entity(text, text, PIIType.COMPANY, "legal_suffix_company", 0.95)

    result = EntityResolver().resolve(text, [person, company])

    assert result.entities == [company]
    assert result.rejected_by_reason == {"person_inside_company": 1}


def test_address_containing_weak_person_wins() -> None:
    text = "Mehta Road, Pune - 411001, Maharashtra, India"
    person = entity(text, "Mehta Road", PIIType.PERSON, "spacy_person", 0.7)
    address = entity(text, text, PIIType.ADDRESS, "address_heuristic", 0.88)

    result = EntityResolver().resolve(text, [person, address])

    assert result.entities == [address]
    assert result.rejected_by_reason == {"semantic_inside_address": 1}


def test_phone_context_wins_over_overlapping_card_candidate() -> None:
    text = "Telephone: +91 98765 43210"
    phone = entity(text, "+91 98765 43210", PIIType.PHONE, "regex_phone", 0.94)
    card = manual(text, phone.start, phone.end, PIIType.CREDIT_CARD, "luhn_credit_card", 0.97)

    result = EntityResolver().resolve(text, [card, phone])

    assert result.entities == [phone]


def test_credit_card_wins_without_phone_context() -> None:
    text = "Card 4111 1111 1111 1111"
    card = entity(text, "4111 1111 1111 1111", PIIType.CREDIT_CARD, "luhn_credit_card", 0.97)
    phone_like = manual(text, card.start, card.end, PIIType.PHONE, "regex_phone", 0.88)

    result = EntityResolver().resolve(text, [phone_like, card])

    assert result.entities == [card]


def test_non_overlapping_and_adjacent_entities_survive() -> None:
    text = "jane@example.com+91 98765 43210"
    email = entity(text, "jane@example.com", PIIType.EMAIL, "regex_email", 0.98)
    phone = entity(text, "+91 98765 43210", PIIType.PHONE, "regex_phone", 0.94)

    result = EntityResolver().resolve(text, [phone, email])

    assert result.entities == [email, phone]
    assert_no_overlaps(result.entities)


def test_partial_overlap_is_deterministic() -> None:
    text = "abcdefghijABCDEFGHIJKLMNOQRSTUVWXYZ"
    person = manual(text, 10, 25, PIIType.PERSON, "spacy_person", 0.9)
    company = manual(text, 20, 35, PIIType.COMPANY, "legal_suffix_company", 0.9)

    result = EntityResolver().resolve(text, [person, company])

    assert result.entities == [company]
    assert_no_overlaps(result.entities)


def test_input_order_independence() -> None:
    text = "John Example Limited jane@example.com"
    candidates = [
        entity(text, "John Example", PIIType.PERSON, "spacy_person", 0.9),
        entity(text, "John Example Limited", PIIType.COMPANY, "legal_suffix_company", 0.95),
        entity(text, "jane@example.com", PIIType.EMAIL, "regex_email", 0.98),
    ]
    expected = EntityResolver().resolve(text, candidates).entities

    reversed_result = EntityResolver().resolve(text, list(reversed(candidates))).entities
    shuffled = candidates[:]
    random.Random(42).shuffle(shuffled)
    shuffled_result = EntityResolver().resolve(text, shuffled).entities

    assert reversed_result == expected
    assert shuffled_result == expected
