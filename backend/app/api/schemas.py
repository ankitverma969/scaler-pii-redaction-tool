from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.jobs.models import JobState


class ErrorInfo(BaseModel):
    code: str
    message: str


class JobAcceptedResponse(BaseModel):
    job_id: str
    status: JobState
    status_url: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobState
    original_filename: str
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    processing_seconds: float | None = None
    total_entities: int | None = None
    counts: dict[str, int]
    download_available: bool
    error: ErrorInfo | None = None


class DeleteJobResponse(BaseModel):
    job_id: str
    deleted: bool
