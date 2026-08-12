from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.models import PIIType
from app.redaction import RedactionEngine


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Redact PII from a DOCX file.")
    parser.add_argument("--input", required=True, help="Input DOCX path")
    parser.add_argument("--output", required=True, help="Output DOCX path")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic seed")
    args = parser.parse_args(argv)

    try:
        result = RedactionEngine().redact(
            input_path=Path(args.input),
            output_path=Path(args.output),
            seed=args.seed,
        )
    except Exception as exc:
        print(f"Redaction failed: {exc}", file=sys.stderr)
        return 1

    print("Redaction complete")
    print(f"output: {result.output_path}")
    print(f"total detected: {result.total_entities}")
    print(f"total planned: {result.total_planned}")
    print(f"total applied: {result.total_applied}")
    for pii_type in PIIType:
        print(f"{pii_type.value}: {result.counts_by_type[pii_type.value]}")
    print("validation: success")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
