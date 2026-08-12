from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class SourceType(str, Enum):
    BODY = "BODY"
    TABLE = "TABLE"
    HEADER = "HEADER"
    FOOTER = "FOOTER"


@dataclass(frozen=True)
class RunSpan:
    """A DOCX run's logical text range using half-open [start, end) offsets."""

    run_index: int
    start: int
    end: int
    run: Any = field(repr=False, compare=False)


@dataclass(frozen=True)
class RunSlice:
    """The part of a run affected by a logical text span."""

    run_index: int
    start: int
    end: int
    start_in_run: int
    end_in_run: int
    run: Any = field(repr=False, compare=False)


@dataclass(frozen=True)
class TextBlock:
    block_id: str
    text: str
    paragraph: Any = field(repr=False, compare=False)
    source_type: SourceType
    part_id: str
    run_spans: tuple[RunSpan, ...]
    location: Mapping[str, Any]

    def runs_for_span(self, start: int, end: int) -> list[RunSlice]:
        """Return run slices touched by logical half-open range [start, end)."""
        if start < 0 or end < start or end > len(self.text):
            raise ValueError(
                f"Invalid span [{start}, {end}) for text length {len(self.text)}"
            )
        if start == end:
            return []

        affected: list[RunSlice] = []
        for run_span in self.run_spans:
            overlap_start = max(start, run_span.start)
            overlap_end = min(end, run_span.end)
            if overlap_start < overlap_end:
                affected.append(
                    RunSlice(
                        run_index=run_span.run_index,
                        start=overlap_start,
                        end=overlap_end,
                        start_in_run=overlap_start - run_span.start,
                        end_in_run=overlap_end - run_span.start,
                        run=run_span.run,
                    )
                )
        return affected


@dataclass(frozen=True)
class DocumentStatistics:
    section_count: int
    paragraph_count: int
    table_count: int
    text_block_count: int
    body_block_count: int
    table_block_count: int
    header_block_count: int
    footer_block_count: int
    header_part_count: int
    footer_part_count: int
    nested_table_count: int
    embedded_media_count: int
