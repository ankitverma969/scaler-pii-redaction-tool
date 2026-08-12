from typing import Any

from docx.text.paragraph import Paragraph

from app.document.models import RunSpan


def build_text_and_run_spans(paragraph: Paragraph) -> tuple[str, tuple[RunSpan, ...]]:
    """Concatenate paragraph runs and map each run to [start, end) offsets."""
    text_parts: list[str] = []
    run_spans: list[RunSpan] = []
    offset = 0

    for run_index, run in enumerate(paragraph.runs):
        run_text = run.text
        start = offset
        offset += len(run_text)
        run_spans.append(
            RunSpan(run_index=run_index, start=start, end=offset, run=run)
        )
        text_parts.append(run_text)

    return "".join(text_parts), tuple(run_spans)


def run_span_offsets(run_spans: tuple[RunSpan, ...]) -> list[tuple[int, int, int]]:
    return [(span.run_index, span.start, span.end) for span in run_spans]
