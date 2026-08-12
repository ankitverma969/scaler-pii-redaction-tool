from __future__ import annotations

import re
import shutil
import uuid
import zipfile
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from threading import Lock
from typing import Any

from fastapi import UploadFile

from app.core.config import settings
from app.document.loader import load_docx
from app.jobs.models import JobError, JobState, RedactionJob, empty_counts
from app.redaction import RedactionEngine


class UploadValidationError(ValueError):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


class JobNotFoundError(KeyError):
    pass


class JobConflictError(RuntimeError):
    pass


class JobManager:
    def __init__(
        self,
        *,
        max_workers: int = settings.max_concurrent_jobs,
        max_upload_size_mb: int = settings.max_upload_size_mb,
        ttl_minutes: int = settings.job_ttl_minutes,
        temp_root: str | Path = settings.job_temp_root,
        engine_factory: Callable[[], Any] = RedactionEngine,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.max_workers = max(1, max_workers)
        self.max_upload_size_bytes = max_upload_size_mb * 1024 * 1024
        self.ttl = timedelta(minutes=max(1, ttl_minutes))
        self.temp_root = Path(temp_root)
        self.engine_factory = engine_factory
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._jobs: dict[str, RedactionJob] = {}
        self._lock = Lock()
        self._executor = ThreadPoolExecutor(
            max_workers=self.max_workers, thread_name_prefix="redaction-job"
        )

    def startup(self) -> None:
        self.temp_root.mkdir(parents=True, exist_ok=True)
        self.cleanup_stale_temp_root()

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    async def create_job(self, upload: UploadFile, seed: int) -> RedactionJob:
        self.cleanup_expired_jobs()
        original_filename = sanitize_filename(upload.filename or "")
        if not original_filename:
            raise UploadValidationError(400, "INVALID_FILENAME", "Filename is required.")
        if Path(original_filename).suffix.lower() != ".docx":
            raise UploadValidationError(400, "UNSUPPORTED_FILE_TYPE", "Upload must be a .docx file.")

        job_id = uuid.uuid4().hex
        temp_dir = self.temp_root / job_id
        temp_dir.mkdir(parents=True, exist_ok=False)
        input_path = temp_dir / "input.docx"
        output_path = temp_dir / "redacted.docx"

        try:
            await self._copy_upload(upload, input_path)
            self._validate_docx_upload(input_path)
            job = RedactionJob(
                job_id=job_id,
                status=JobState.QUEUED,
                original_filename=original_filename,
                download_filename=redacted_filename(original_filename),
                seed=seed,
                temp_dir=temp_dir,
                input_path=input_path,
                output_path=output_path,
                counts_by_type=empty_counts(),
            )
            with self._lock:
                self._jobs[job_id] = job
            self._executor.submit(self._run_job, job_id)
            return self.get_job(job_id)
        except Exception:
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
            raise

    def get_job(self, job_id: str) -> RedactionJob:
        self.cleanup_expired_jobs()
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise JobNotFoundError(job_id)
            return deepcopy(job)

    def delete_job(self, job_id: str) -> None:
        self.cleanup_expired_jobs()
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise JobNotFoundError(job_id)
            if job.status in {JobState.QUEUED, JobState.PROCESSING}:
                raise JobConflictError("Active jobs cannot be deleted.")
            self._jobs.pop(job_id)
        shutil.rmtree(job.temp_dir, ignore_errors=True)

    def download_path(self, job_id: str) -> tuple[Path, str]:
        job = self.get_job(job_id)
        if job.status in {JobState.QUEUED, JobState.PROCESSING}:
            raise JobConflictError("Redaction output is not ready.")
        if job.status == JobState.FAILED or not job.download_available:
            raise JobConflictError("Redaction output is not available.")
        return job.output_path, job.download_filename

    def cleanup_expired_jobs(self) -> None:
        cutoff = self._now() - self.ttl
        expired: list[RedactionJob] = []
        with self._lock:
            for job_id, job in list(self._jobs.items()):
                if job.status in {JobState.QUEUED, JobState.PROCESSING}:
                    continue
                finished_at = job.completed_at or job.created_at
                if finished_at <= cutoff:
                    expired.append(self._jobs.pop(job_id))
        for job in expired:
            shutil.rmtree(job.temp_dir, ignore_errors=True)

    def cleanup_stale_temp_root(self) -> None:
        self.temp_root.mkdir(parents=True, exist_ok=True)
        for child in self.temp_root.iterdir():
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)

    async def _copy_upload(self, upload: UploadFile, input_path: Path) -> None:
        total = 0
        with input_path.open("wb") as handle:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > self.max_upload_size_bytes:
                    raise UploadValidationError(
                        413,
                        "UPLOAD_TOO_LARGE",
                        "Uploaded file exceeds the configured size limit.",
                    )
                handle.write(chunk)
        if total == 0:
            raise UploadValidationError(400, "EMPTY_FILE", "Uploaded file is empty.")

    def _validate_docx_upload(self, input_path: Path) -> None:
        if not zipfile.is_zipfile(input_path):
            raise UploadValidationError(400, "INVALID_DOCX", "Uploaded file is not a valid DOCX package.")
        self._validate_zip_safety(input_path)
        try:
            load_docx(input_path)
        except Exception as exc:
            raise UploadValidationError(400, "INVALID_DOCX", "Uploaded DOCX could not be opened.") from exc

    def _validate_zip_safety(self, input_path: Path) -> None:
        with zipfile.ZipFile(input_path) as package:
            infos = package.infolist()
            if len(infos) > 10_000:
                raise UploadValidationError(400, "SUSPICIOUS_DOCX", "DOCX package has too many entries.")
            uncompressed = sum(info.file_size for info in infos)
            compressed = max(sum(info.compress_size for info in infos), 1)
            if uncompressed > self.max_upload_size_bytes * 100:
                raise UploadValidationError(400, "SUSPICIOUS_DOCX", "DOCX package is too large after decompression.")
            if uncompressed > 50 * 1024 * 1024 and uncompressed / compressed > 1000:
                raise UploadValidationError(400, "SUSPICIOUS_DOCX", "DOCX package compression ratio is suspicious.")

    def _run_job(self, job_id: str) -> None:
        self._mark_processing(job_id)
        try:
            result = self.engine_factory().redact(
                input_path=self._internal_job(job_id).input_path,
                output_path=self._internal_job(job_id).output_path,
                seed=self._internal_job(job_id).seed,
            )
            self._mark_completed(
                job_id,
                total_entities=result.total_entities,
                counts_by_type=result.counts_by_type,
                processing_seconds=result.duration_seconds,
            )
        except Exception:
            self._mark_failed(
                job_id,
                JobError(
                    code="REDACTION_FAILED",
                    message="The document could not be processed.",
                ),
            )
        finally:
            job = self._internal_job_or_none(job_id)
            if job is not None:
                job.input_path.unlink(missing_ok=True)
                if job.status == JobState.FAILED:
                    job.output_path.unlink(missing_ok=True)

    def _internal_job(self, job_id: str) -> RedactionJob:
        job = self._internal_job_or_none(job_id)
        if job is None:
            raise JobNotFoundError(job_id)
        return job

    def _internal_job_or_none(self, job_id: str) -> RedactionJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def _mark_processing(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.status = JobState.PROCESSING
            job.started_at = self._now()

    def _mark_completed(
        self,
        job_id: str,
        *,
        total_entities: int,
        counts_by_type: dict[str, int],
        processing_seconds: float,
    ) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.status = JobState.COMPLETED
            job.completed_at = self._now()
            job.processing_seconds = processing_seconds
            job.total_entities = total_entities
            job.counts_by_type = {**empty_counts(), **counts_by_type}
            job.error = None

    def _mark_failed(self, job_id: str, error: JobError) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.status = JobState.FAILED
            job.completed_at = self._now()
            if job.started_at is not None:
                job.processing_seconds = (job.completed_at - job.started_at).total_seconds()
            job.error = error


def sanitize_filename(filename: str) -> str:
    normalized = filename.replace("\\", "/")
    name = PurePosixPath(normalized).name
    name = re.sub(r"[^A-Za-z0-9._ -]+", "_", name).strip(" .")
    return name


def redacted_filename(filename: str) -> str:
    safe = sanitize_filename(filename) or "document.docx"
    path = Path(safe)
    stem = re.sub(r"[^A-Za-z0-9._ -]+", "_", path.stem).strip(" .") or "document"
    return f"{stem}_Redacted.docx"
