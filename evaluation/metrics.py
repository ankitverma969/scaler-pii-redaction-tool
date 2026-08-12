from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Iterable, Mapping


PII_TYPES = [
    "PERSON",
    "EMAIL",
    "PHONE",
    "COMPANY",
    "ADDRESS",
    "SSN",
    "CREDIT_CARD",
    "DOB",
    "IP_ADDRESS",
]

STRUCTURED_TYPES = {"EMAIL", "PHONE", "SSN", "CREDIT_CARD", "DOB", "IP_ADDRESS"}


@dataclass(frozen=True)
class SpanEntity:
    start: int
    end: int
    pii_type: str
    source: str = "gold"

    @property
    def key(self) -> tuple[int, int, str]:
        return (self.start, self.end, self.pii_type)


@dataclass(frozen=True)
class HardNegative:
    start: int
    end: int
    negative_type: str


class AnnotationValidationError(ValueError):
    pass


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def metric_value(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def f1_score(precision: float | None, recall: float | None) -> float | None:
    if precision is None or recall is None:
        return None
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def overlaps(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return a_start < b_end and b_start < a_end


def materialize_entities(entries: Iterable[Mapping], text: str) -> list[SpanEntity]:
    entities: list[SpanEntity] = []
    for entry in entries:
        pii_type = str(entry["pii_type"])
        if "start" in entry and "end" in entry:
            start = int(entry["start"])
            end = int(entry["end"])
        else:
            value = str(entry["text"])
            occurrence = int(entry.get("occurrence", 0))
            cursor = 0
            start = -1
            for _ in range(occurrence + 1):
                start = text.index(value, cursor)
                cursor = start + len(value)
            end = start + len(value)
        entities.append(SpanEntity(start, end, pii_type, str(entry.get("source", "gold"))))
    return entities


def materialize_hard_negatives(entries: Iterable[Mapping], text: str) -> list[HardNegative]:
    negatives: list[HardNegative] = []
    for entry in entries:
        negative_type = str(entry["negative_type"])
        if "start" in entry and "end" in entry:
            start = int(entry["start"])
            end = int(entry["end"])
        else:
            value = str(entry["text"])
            occurrence = int(entry.get("occurrence", 0))
            cursor = 0
            start = -1
            for _ in range(occurrence + 1):
                start = text.index(value, cursor)
                cursor = start + len(value)
            end = start + len(value)
        negatives.append(HardNegative(start, end, negative_type))
    return negatives


def validate_annotation_records(records: list[Mapping], block_text_by_id: Mapping[str, str]) -> None:
    seen_blocks: set[str] = set()
    for index, record in enumerate(records):
        block_id = str(record.get("block_id", ""))
        if not block_id or block_id not in block_text_by_id:
            raise AnnotationValidationError(f"record {index}: unknown block_id")
        if block_id in seen_blocks:
            raise AnnotationValidationError(f"record {index}: duplicate block_id")
        seen_blocks.add(block_id)

        source_text = block_text_by_id[block_id]
        stored_text = record.get("text")
        if stored_text is not None and stored_text != source_text:
            raise AnnotationValidationError(f"record {index}: stored text mismatch")
        if record.get("text_sha256") and record["text_sha256"] != text_hash(source_text):
            raise AnnotationValidationError(f"record {index}: source hash mismatch")

        positives = materialize_entities(record.get("entities", []), source_text)
        negatives = materialize_hard_negatives(record.get("hard_negatives", []), source_text)
        seen_positive_keys: set[tuple[int, int, str]] = set()
        for entity in positives:
            _validate_span(index, source_text, entity.start, entity.end)
            if entity.pii_type not in PII_TYPES:
                raise AnnotationValidationError(f"record {index}: unknown PII type")
            if entity.key in seen_positive_keys:
                raise AnnotationValidationError(f"record {index}: duplicate positive span")
            seen_positive_keys.add(entity.key)

        for left_index, left in enumerate(positives):
            for right in positives[left_index + 1 :]:
                if overlaps(left.start, left.end, right.start, right.end):
                    raise AnnotationValidationError(f"record {index}: overlapping positives")

        seen_negative_keys: set[tuple[int, int, str]] = set()
        for negative in negatives:
            _validate_span(index, source_text, negative.start, negative.end)
            key = (negative.start, negative.end, negative.negative_type)
            if key in seen_negative_keys:
                raise AnnotationValidationError(f"record {index}: duplicate hard negative")
            seen_negative_keys.add(key)


def _validate_span(record_index: int, text: str, start: int, end: int) -> None:
    if start < 0 or end <= start or end > len(text):
        raise AnnotationValidationError(f"record {record_index}: invalid span")


def score_dataset(
    gold_by_block: Mapping[str, list[SpanEntity]],
    predictions_by_block: Mapping[str, list[SpanEntity]],
    negatives_by_block: Mapping[str, list[HardNegative]],
) -> dict:
    per_type_counts = {
        pii_type: {"gold": 0, "predicted": 0, "tp": 0, "fp": 0, "fn": 0}
        for pii_type in PII_TYPES
    }
    candidate_counts = {"tp": 0, "tn": 0, "fp": 0, "fn": 0}
    hard_negative_counts = Counter()
    error_summary = Counter()

    block_ids = set(gold_by_block) | set(predictions_by_block) | set(negatives_by_block)
    for block_id in block_ids:
        gold = list(gold_by_block.get(block_id, []))
        predictions = list(predictions_by_block.get(block_id, []))
        negatives = list(negatives_by_block.get(block_id, []))
        matched_gold: set[int] = set()
        matched_predictions: set[int] = set()

        for gold_index, gold_entity in enumerate(gold):
            per_type_counts[gold_entity.pii_type]["gold"] += 1
            for pred_index, predicted in enumerate(predictions):
                if pred_index in matched_predictions:
                    continue
                if predicted.key == gold_entity.key:
                    matched_gold.add(gold_index)
                    matched_predictions.add(pred_index)
                    per_type_counts[gold_entity.pii_type]["tp"] += 1
                    candidate_counts["tp"] += 1
                    break

        for pred_index, predicted in enumerate(predictions):
            per_type_counts[predicted.pii_type]["predicted"] += 1
            if pred_index not in matched_predictions:
                per_type_counts[predicted.pii_type]["fp"] += 1
                _classify_unmatched_prediction(error_summary, predicted, gold)

        for gold_index, gold_entity in enumerate(gold):
            if gold_index not in matched_gold:
                per_type_counts[gold_entity.pii_type]["fn"] += 1
                candidate_counts["fn"] += 1
                if gold_entity.pii_type in STRUCTURED_TYPES:
                    error_summary["missed_structured_entities"] += 1
                else:
                    error_summary["missed_semantic_entities"] += 1

        for negative in negatives:
            hard_negative_counts[negative.negative_type] += 1
            if any(overlaps(negative.start, negative.end, p.start, p.end) for p in predictions):
                candidate_counts["fp"] += 1
            else:
                candidate_counts["tn"] += 1

    per_type = _finalize_per_type(per_type_counts)
    micro = _micro_metrics(per_type_counts)
    candidate_total = sum(candidate_counts.values())
    candidate_accuracy = metric_value(
        candidate_counts["tp"] + candidate_counts["tn"], candidate_total
    )
    return {
        "per_type": per_type,
        "micro": micro,
        "candidate_accuracy": {
            **candidate_counts,
            "positive_candidates": candidate_counts["tp"] + candidate_counts["fn"],
            "hard_negative_candidates": candidate_counts["tn"] + candidate_counts["fp"],
            "accuracy": candidate_accuracy,
        },
        "hard_negative_counts": dict(sorted(hard_negative_counts.items())),
        "error_summary": _normalize_error_summary(error_summary),
    }


def _classify_unmatched_prediction(
    error_summary: Counter, predicted: SpanEntity, gold: list[SpanEntity]
) -> None:
    overlapping = [g for g in gold if overlaps(predicted.start, predicted.end, g.start, g.end)]
    if any(g.start == predicted.start and g.end == predicted.end and g.pii_type != predicted.pii_type for g in overlapping):
        error_summary["wrong_type_errors"] += 1
    elif any(g.pii_type == predicted.pii_type for g in overlapping):
        error_summary["boundary_errors"] += 1
    elif predicted.pii_type in STRUCTURED_TYPES:
        error_summary["structured_false_positives"] += 1
    else:
        error_summary["semantic_false_positives"] += 1


def _finalize_per_type(per_type_counts: Mapping[str, Mapping[str, int]]) -> dict:
    output: dict[str, dict] = {}
    for pii_type in PII_TYPES:
        counts = dict(per_type_counts[pii_type])
        precision = metric_value(counts["tp"], counts["tp"] + counts["fp"])
        recall = metric_value(counts["tp"], counts["tp"] + counts["fn"])
        output[pii_type] = {
            **counts,
            "precision": precision,
            "recall": recall,
            "f1": f1_score(precision, recall),
        }
    return output


def _micro_metrics(per_type_counts: Mapping[str, Mapping[str, int]]) -> dict:
    totals = defaultdict(int)
    for counts in per_type_counts.values():
        for key in ("tp", "fp", "fn"):
            totals[key] += int(counts[key])
    precision = metric_value(totals["tp"], totals["tp"] + totals["fp"])
    recall = metric_value(totals["tp"], totals["tp"] + totals["fn"])
    return {
        "tp": totals["tp"],
        "fp": totals["fp"],
        "fn": totals["fn"],
        "precision": precision,
        "recall": recall,
        "f1": f1_score(precision, recall),
    }


def _normalize_error_summary(error_summary: Counter) -> dict[str, int]:
    keys = [
        "boundary_errors",
        "wrong_type_errors",
        "semantic_false_positives",
        "structured_false_positives",
        "missed_semantic_entities",
        "missed_structured_entities",
    ]
    return {key: error_summary.get(key, 0) for key in keys}
