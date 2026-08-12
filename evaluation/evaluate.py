from __future__ import annotations

import argparse
import json
import platform
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import spacy  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.detectors import PIIDetector  # noqa: E402
from app.document import iter_text_blocks, load_docx  # noqa: E402
from evaluation.metrics import (  # noqa: E402
    HardNegative,
    SpanEntity,
    materialize_entities,
    materialize_hard_negatives,
    score_dataset,
    text_hash,
    validate_annotation_records,
)
from evaluation.sampling import select_evaluation_sample  # noqa: E402


DETECTOR_FINGERPRINT_FILES = [
    "backend/app/detectors/person.py",
    "backend/app/detectors/company.py",
    "backend/app/detectors/address.py",
    "backend/app/detectors/semantic_filters.py",
    "backend/app/detectors/structured.py",
    "backend/app/detectors/resolver.py",
    "backend/app/detectors/unified.py",
]


def load_jsonl(path: Path) -> list[dict]:
    records = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def load_blocks(input_path: Path):
    document = load_docx(input_path)
    return [block for block in iter_text_blocks(document) if block.text.strip()]


def export_annotation_worksheet(input_path: Path, output_path: Path, seed: int, target_size: int) -> None:
    blocks = load_blocks(input_path)
    block_by_id = {block.block_id: block for block in blocks}
    sample = select_evaluation_sample(blocks, seed=seed, target_size=target_size)
    records = []
    for block_id in sample.block_ids:
        block = block_by_id[block_id]
        records.append(
            {
                "block_id": block.block_id,
                "source_type": block.source_type.value,
                "text": block.text,
                "text_sha256": text_hash(block.text),
                "entities": [],
                "hard_negatives": [],
            }
        )
    write_jsonl(output_path, records)


def evaluate_real(input_path: Path, ground_truth_path: Path) -> dict:
    blocks = load_blocks(input_path)
    block_text_by_id = {block.block_id: block.text for block in blocks}
    block_by_id = {block.block_id: block for block in blocks}
    records = load_jsonl(ground_truth_path)
    validate_annotation_records(records, block_text_by_id)

    selected_blocks = [block_by_id[record["block_id"]] for record in records]
    predictions = PIIDetector().detect_many(block.text for block in selected_blocks)
    gold_by_block: dict[str, list[SpanEntity]] = {}
    predictions_by_block: dict[str, list[SpanEntity]] = {}
    negatives_by_block: dict[str, list[HardNegative]] = {}
    source_counts = Counter()
    blocks_with_positive = 0

    for record, block, predicted_entities in zip(records, selected_blocks, predictions, strict=True):
        gold = materialize_entities(record.get("entities", []), block.text)
        negatives = materialize_hard_negatives(record.get("hard_negatives", []), block.text)
        gold_by_block[block.block_id] = gold
        negatives_by_block[block.block_id] = negatives
        predictions_by_block[block.block_id] = [
            SpanEntity(entity.start, entity.end, entity.pii_type.value, entity.source)
            for entity in predicted_entities
        ]
        source_counts[block.source_type.value] += 1
        if gold:
            blocks_with_positive += 1

    scored = score_dataset(gold_by_block, predictions_by_block, negatives_by_block)
    return {
        "kind": "real_rhp",
        "metadata": evaluation_metadata(
            sample_size=len(records),
            sampling_seed=_common_seed(records),
            source_type_distribution=source_counts,
        ),
        "sample": {
            "total_blocks": len(records),
            "source_type_distribution": dict(sorted(source_counts.items())),
            "blocks_with_positive_pii": blocks_with_positive,
            "blocks_with_no_positive_pii": len(records) - blocks_with_positive,
            "positive_annotation_count": sum(len(items) for items in gold_by_block.values()),
            "hard_negative_candidate_count": sum(len(items) for items in negatives_by_block.values()),
        },
        "metrics": scored,
    }


def evaluate_synthetic(path: Path) -> dict:
    records = load_jsonl(path)
    block_text_by_id = {record["block_id"]: record["text"] for record in records}
    validate_annotation_records(records, block_text_by_id)

    predictions = PIIDetector().detect_many(record["text"] for record in records)
    gold_by_block: dict[str, list[SpanEntity]] = {}
    predictions_by_block: dict[str, list[SpanEntity]] = {}
    negatives_by_block: dict[str, list[HardNegative]] = {}
    for record, predicted_entities in zip(records, predictions, strict=True):
        block_id = record["block_id"]
        text = record["text"]
        gold_by_block[block_id] = materialize_entities(record.get("entities", []), text)
        negatives_by_block[block_id] = materialize_hard_negatives(
            record.get("hard_negatives", []), text
        )
        predictions_by_block[block_id] = [
            SpanEntity(entity.start, entity.end, entity.pii_type.value, entity.source)
            for entity in predicted_entities
        ]
    return {
        "kind": "synthetic_capability",
        "metadata": evaluation_metadata(sample_size=len(records), sampling_seed=None),
        "sample": {
            "total_cases": len(records),
            "positive_annotation_count": sum(len(items) for items in gold_by_block.values()),
            "hard_negative_candidate_count": sum(len(items) for items in negatives_by_block.values()),
        },
        "metrics": score_dataset(gold_by_block, predictions_by_block, negatives_by_block),
    }


def evaluation_metadata(
    sample_size: int,
    sampling_seed: int | None,
    source_type_distribution: Counter | None = None,
) -> dict:
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "python_version": platform.python_version(),
        "spacy_version": spacy.__version__,
        "spacy_model": settings.spacy_model,
        "sampling_seed": sampling_seed,
        "sample_size": sample_size,
        "matching_policy": "strict exact [start,end) span plus exact PII type",
        "source_type_distribution": dict(sorted((source_type_distribution or Counter()).items())),
        "detector_source_fingerprint_sha256": detector_fingerprint(),
    }


def detector_fingerprint() -> str:
    digest = __import__("hashlib").sha256()
    for relative in DETECTOR_FINGERPRINT_FILES:
        path = ROOT / relative
        digest.update(relative.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _common_seed(records: list[dict]) -> int | None:
    seeds = {record.get("sampling_seed") for record in records if "sampling_seed" in record}
    if len(seeds) == 1:
        return next(iter(seeds))
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate PII detector metrics.")
    parser.add_argument("--input", type=Path, help="Original RHP DOCX path")
    parser.add_argument("--ground-truth", type=Path, help="Private real ground truth JSONL")
    parser.add_argument("--synthetic", action="store_true", help="Run synthetic capability evaluation")
    parser.add_argument(
        "--synthetic-cases",
        type=Path,
        default=ROOT / "evaluation" / "synthetic_cases.jsonl",
    )
    parser.add_argument(
        "--metrics-output",
        type=Path,
        default=ROOT / "evaluation" / "metrics.json",
    )
    parser.add_argument("--export-worksheet", type=Path, help="Write private annotation worksheet")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--target-size", type=int, default=150)
    args = parser.parse_args()

    if args.export_worksheet:
        if not args.input:
            parser.error("--input is required with --export-worksheet")
        export_annotation_worksheet(args.input, args.export_worksheet, args.seed, args.target_size)
        return

    output: dict[str, object] = {}
    if args.ground_truth:
        if not args.input:
            parser.error("--input is required with --ground-truth")
        output["real_rhp_evaluation"] = evaluate_real(args.input, args.ground_truth)
    if args.synthetic:
        output["synthetic_capability_evaluation"] = evaluate_synthetic(args.synthetic_cases)
    if not output:
        parser.error("choose --ground-truth and/or --synthetic")
    write_json(args.metrics_output, output)


if __name__ == "__main__":
    main()
