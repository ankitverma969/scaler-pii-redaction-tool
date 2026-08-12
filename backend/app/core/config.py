import os
from dataclasses import dataclass
from pathlib import Path
from tempfile import gettempdir


def _get_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return int(raw_value)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "PII Redaction Tool API")
    api_prefix: str = os.getenv("API_PREFIX", "/api")
    environment: str = os.getenv("ENVIRONMENT", "development")
    frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
    max_upload_size_mb: int = _get_int("MAX_UPLOAD_SIZE_MB", 10)
    default_redaction_seed: int = _get_int("DEFAULT_REDACTION_SEED", 42)
    spacy_model: str = os.getenv("SPACY_MODEL", "en_core_web_sm")
    max_concurrent_jobs: int = max(1, _get_int("MAX_CONCURRENT_JOBS", 1))
    job_ttl_minutes: int = max(1, _get_int("JOB_TTL_MINUTES", 60))
    job_temp_root: Path = Path(
        os.getenv("JOB_TEMP_ROOT", str(Path(gettempdir()) / "pii-redactor-jobs"))
    )


settings = Settings()
