import os
from dataclasses import dataclass


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


settings = Settings()
