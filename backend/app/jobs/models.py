from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from app.models import PIIType


class JobState(str, Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class JobError:
    code: str
    message: str


def empty_counts() -> dict[str, int]:
    return {pii_type.value: 0 for pii_type in PIIType}


@dataclass
class RedactionJob:
    job_id: str
    status: JobState
    original_filename: str
    download_filename: str
    seed: int
    temp_dir: Path = field(repr=False)
    input_path: Path = field(repr=False)
    output_path: Path = field(repr=False)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    processing_seconds: float | None = None
    total_entities: int | None = None
    counts_by_type: dict[str, int] = field(default_factory=empty_counts)
    error: JobError | None = None

    @property
    def download_available(self) -> bool:
        return self.status == JobState.COMPLETED and self.output_path.exists()
