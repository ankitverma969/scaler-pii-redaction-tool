from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.metrics import (  # noqa: E402
    AnnotationValidationError,
    HardNegative,
    SpanEntity,
    f1_score,
    materialize_entities,
    metric_value,
    score_dataset,
    text_hash,
    validate_annotation_records,
)


def test_metric_denominators_and_f1() -> None:
    assert metric_value(1, 2) == 0.5
    assert metric_value(1, 0) is None
    assert f1_score(1.0, 1.0) == 1.0
    assert f1_score(0.0, 0.0) == 0.0
    assert f1_score(None, 1.0) is None


def test_perfect_match_scores_tp_and_candidate_accuracy() -> None:
    gold = {"b1": [SpanEntity(0, 10, "EMAIL")]}
    predictions = {"b1": [SpanEntity(0, 10, "EMAIL", "regex_email")]}
    negatives = {"b1": [HardNegative(11, 20, "ORDINARY_DATE")]}

    result = score_dataset(gold, predictions, negatives)

    assert result["per_type"]["EMAIL"]["tp"] == 1
    assert result["micro"]["precision"] == 1.0
    assert result["micro"]["recall"] == 1.0
    assert result["candidate_accuracy"]["tp"] == 1
    assert result["candidate_accuracy"]["tn"] == 1
    assert result["candidate_accuracy"]["accuracy"] == 1.0


def test_false_positive_false_negative_wrong_type_and_boundary_mismatch() -> None:
    gold = {
        "b1": [
            SpanEntity(0, 5, "PERSON"),
            SpanEntity(10, 20, "COMPANY"),
        ]
    }
    predictions = {
        "b1": [
            SpanEntity(0, 5, "COMPANY", "spacy_company"),
            SpanEntity(11, 20, "COMPANY", "legal_suffix_company"),
            SpanEntity(30, 40, "ADDRESS", "address_heuristic"),
        ]
    }

    result = score_dataset(gold, predictions, {"b1": []})

    assert result["micro"]["tp"] == 0
    assert result["micro"]["fp"] == 3
    assert result["micro"]["fn"] == 2
    assert result["error_summary"]["wrong_type_errors"] == 1
    assert result["error_summary"]["boundary_errors"] == 1
    assert result["error_summary"]["semantic_false_positives"] == 1


def test_zero_predictions_and_zero_gold_return_na_where_undefined() -> None:
    result = score_dataset({"b1": []}, {"b1": []}, {"b1": []})

    assert result["micro"]["precision"] is None
    assert result["micro"]["recall"] is None
    assert result["per_type"]["DOB"]["recall"] is None


def test_candidate_accuracy_counts_negative_overlap_once() -> None:
    result = score_dataset(
        {"b1": [SpanEntity(0, 4, "PERSON")]},
        {"b1": [SpanEntity(10, 20, "COMPANY", "spacy_company")]},
        {"b1": [HardNegative(12, 14, "COMMITTEE"), HardNegative(30, 40, "PIN_ONLY")]},
    )

    assert result["candidate_accuracy"]["fn"] == 1
    assert result["candidate_accuracy"]["fp"] == 1
    assert result["candidate_accuracy"]["tn"] == 1
    assert result["candidate_accuracy"]["accuracy"] == 1 / 3


def test_materialize_entities_from_text_occurrence() -> None:
    entities = materialize_entities(
        [{"text": "alice@example.com", "pii_type": "EMAIL", "occurrence": 1}],
        "alice@example.com and alice@example.com",
    )

    assert entities == [SpanEntity(22, 39, "EMAIL")]


def test_annotation_validator_accepts_valid_record() -> None:
    text = "Contact: Rahul Mehta, dated December 9, 2025"
    records = [
        {
            "block_id": "b1",
            "text": text,
            "text_sha256": text_hash(text),
            "entities": [{"start": 9, "end": 21, "pii_type": "PERSON"}],
            "hard_negatives": [
                {"text": "December 9, 2025", "negative_type": "ORDINARY_DATE"}
            ],
        }
    ]

    validate_annotation_records(records, {"b1": text})


@pytest.mark.parametrize(
    "record,error",
    [
        ({"block_id": "missing", "entities": []}, "unknown block_id"),
        (
            {"block_id": "b1", "entities": [{"start": -1, "end": 2, "pii_type": "EMAIL"}]},
            "invalid span",
        ),
        (
            {"block_id": "b1", "entities": [{"start": 0, "end": 4, "pii_type": "BAD"}]},
            "unknown PII type",
        ),
        (
            {
                "block_id": "b1",
                "entities": [
                    {"start": 0, "end": 4, "pii_type": "EMAIL"},
                    {"start": 0, "end": 4, "pii_type": "EMAIL"},
                ],
            },
            "duplicate positive",
        ),
        (
            {
                "block_id": "b1",
                "entities": [
                    {"start": 0, "end": 4, "pii_type": "EMAIL"},
                    {"start": 2, "end": 5, "pii_type": "PERSON"},
                ],
            },
            "overlapping positives",
        ),
        ({"block_id": "b1", "text_sha256": "bad", "entities": []}, "source hash mismatch"),
    ],
)
def test_annotation_validator_rejects_invalid_records(record, error) -> None:
    with pytest.raises(AnnotationValidationError, match=error):
        validate_annotation_records([record], {"b1": "abcdef"})
