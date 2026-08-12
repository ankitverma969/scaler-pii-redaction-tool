from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse

from app.api.schemas import DeleteJobResponse, JobAcceptedResponse, JobStatusResponse
from app.core.config import settings
from app.jobs.manager import (
    JobConflictError,
    JobManager,
    JobNotFoundError,
    UploadValidationError,
)
from app.jobs.models import RedactionJob

router = APIRouter()


@router.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "pii-redaction-api",
    }


@router.post(
    "/redactions",
    response_model=JobAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create a DOCX redaction job",
)
async def create_redaction(
    request: Request,
    file: UploadFile = File(...),
    seed: int = Form(settings.default_redaction_seed),
) -> JobAcceptedResponse:
    manager = _job_manager(request)
    try:
        job = await manager.create_job(file, seed)
    except UploadValidationError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    return JobAcceptedResponse(
        job_id=job.job_id,
        status=job.status,
        status_url=f"{settings.api_prefix}/redactions/{job.job_id}",
    )


@router.get(
    "/redactions/{job_id}",
    response_model=JobStatusResponse,
    summary="Get redaction job status",
)
def get_redaction_status(request: Request, job_id: str) -> JobStatusResponse:
    try:
        job = _job_manager(request).get_job(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Job not found.") from exc
    return _status_response(job)


@router.get(
    "/redactions/{job_id}/download",
    summary="Download a completed redacted DOCX",
)
def download_redaction(request: Request, job_id: str) -> FileResponse:
    try:
        path, filename = _job_manager(request).download_path(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Job not found.") from exc
    except JobConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return FileResponse(
        path=path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@router.delete(
    "/redactions/{job_id}",
    response_model=DeleteJobResponse,
    summary="Delete a completed or failed redaction job",
)
def delete_redaction(request: Request, job_id: str) -> DeleteJobResponse:
    try:
        _job_manager(request).delete_job(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Job not found.") from exc
    except JobConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return DeleteJobResponse(job_id=job_id, deleted=True)


def _job_manager(request: Request) -> JobManager:
    return request.app.state.job_manager


def _status_response(job: RedactionJob) -> JobStatusResponse:
    error = None
    if job.error is not None:
        error = {"code": job.error.code, "message": job.error.message}
    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        original_filename=job.original_filename,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        processing_seconds=job.processing_seconds,
        total_entities=job.total_entities,
        counts=job.counts_by_type,
        download_available=job.download_available,
        error=error,
    )
