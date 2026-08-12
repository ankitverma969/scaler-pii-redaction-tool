from __future__ import annotations

from collections.abc import Iterable

from app.document.models import TextBlock
from app.replacement.models import PlannedReplacement


class DocumentMutationError(RuntimeError):
    """Raised when run-aware text mutation cannot be applied safely."""


def apply_replacements_to_text(
    original_text: str, plans: Iterable[PlannedReplacement]
) -> str:
    """Apply planned replacements to plain text using right-to-left offsets."""
    plan_list = _validated_plans(original_text, plans)
    transformed = original_text
    for plan in sorted(plan_list, key=lambda item: item.start, reverse=True):
        transformed = (
            transformed[: plan.start] + plan.replacement + transformed[plan.end :]
        )
    return transformed


def apply_replacements_to_block(
    block: TextBlock, plans: Iterable[PlannedReplacement]
) -> int:
    """Mutate a TextBlock's existing DOCX runs without replacing the paragraph."""
    plan_list = _validated_plans(block.text, plans)
    expected_text = apply_replacements_to_text(block.text, plan_list)

    for plan in sorted(plan_list, key=lambda item: item.start, reverse=True):
        slices = block.runs_for_span(plan.start, plan.end)
        if not slices:
            raise DocumentMutationError(
                f"No DOCX runs found for replacement span in block {block.block_id}"
            )

        if len(slices) == 1:
            run_slice = slices[0]
            current = run_slice.run.text
            run_slice.run.text = (
                current[: run_slice.start_in_run]
                + plan.replacement
                + current[run_slice.end_in_run :]
            )
            continue

        first = slices[0]
        last = slices[-1]
        first_text = first.run.text
        last_text = last.run.text

        first.run.text = first_text[: first.start_in_run] + plan.replacement
        for run_slice in slices[1:-1]:
            run_slice.run.text = ""
        last.run.text = last_text[last.end_in_run :]

    actual_text = "".join(run.text for run in block.paragraph.runs)
    if actual_text != expected_text:
        raise DocumentMutationError(
            f"Run mutation validation failed for block {block.block_id}"
        )

    return len(plan_list)


def _validated_plans(
    original_text: str, plans: Iterable[PlannedReplacement]
) -> list[PlannedReplacement]:
    plan_list = list(plans)
    text_length = len(original_text)
    for plan in plan_list:
        if plan.start < 0 or plan.end > text_length or plan.start >= plan.end:
            raise DocumentMutationError("Invalid replacement span")
        if original_text[plan.start : plan.end] != plan.entity.text:
            raise DocumentMutationError("Replacement plan does not match source text")

    ordered = sorted(plan_list, key=lambda item: (item.start, item.end))
    previous: PlannedReplacement | None = None
    for plan in ordered:
        if previous is not None and previous.end > plan.start:
            raise DocumentMutationError("Replacement plans must not overlap")
        previous = plan

    return plan_list
