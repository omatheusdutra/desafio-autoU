from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    app_name: str = "Email Smart Reply"
    app_version: str = "2.1.0"
    audit_log_path: Path = Field(
        default=Path("logs") / "email_events.jsonl",
        validation_alias="AUDIT_LOG_PATH",
    )
    reports_dir: Path = Field(
        default=Path("reports"),
        validation_alias="REPORTS_DIR",
    )
    reports_storage: str = Field(
        default="local", validation_alias="REPORTS_STORAGE"
    )
    s3_bucket: Optional[str] = Field(default=None, validation_alias="S3_BUCKET")
    s3_region: Optional[str] = Field(default=None, validation_alias="S3_REGION")
    s3_prefix: str = Field(default="reports", validation_alias="S3_PREFIX")
    s3_public_base_url: Optional[str] = Field(
        default=None, validation_alias="S3_PUBLIC_BASE_URL"
    )
    enable_transformers: bool = Field(
        default=True, validation_alias="ENABLE_TRANSFORMERS"
    )
    openai_api_key: Optional[str] = Field(
        default=None, validation_alias="OPENAI_API_KEY"
    )
    keyword_overrides_path: Optional[Path] = Field(
        default=None, validation_alias="KEYWORD_OVERRIDES_PATH"
    )
    redis_url: Optional[str] = Field(default=None, validation_alias="REDIS_URL")
    enable_redis_cache: bool = Field(
        default=False, validation_alias="ENABLE_REDIS_CACHE"
    )
    cache_ttl_seconds: int = Field(
        default=3600, validation_alias="CACHE_TTL_SECONDS"
    )
    cache_max_items: int = Field(
        default=2000, validation_alias="CACHE_MAX_ITEMS"
    )
    enable_rate_limit: bool = Field(
        default=True, validation_alias="ENABLE_RATE_LIMIT"
    )
    rate_limit_default: str = Field(
        default="60/minute", validation_alias="RATE_LIMIT_DEFAULT"
    )
    enable_warmup: bool = Field(
        default=True, validation_alias="ENABLE_WARMUP"
    )
    enable_job_queue: bool = Field(
        default=False, validation_alias="ENABLE_JOB_QUEUE"
    )
    port: int = Field(default=7860, validation_alias="PORT")
    max_upload_mb: int = Field(
        default=8, validation_alias="MAX_UPLOAD_MB"
    )
    batch_preview_limit: int = Field(
        default=50, validation_alias="BATCH_PREVIEW_LIMIT"
    )
    classification_workers: int = Field(
        default=4, validation_alias="CLASSIFICATION_WORKERS"
    )
    pdf_parse_workers: int = Field(
        default=2, validation_alias="PDF_PARSE_WORKERS"
    )
    max_batch_items: int = Field(
        default=200, validation_alias="MAX_BATCH_ITEMS"
    )

    @field_validator("audit_log_path", "reports_dir", "keyword_overrides_path", mode="before")
    @classmethod
    def _expand_path(cls, value):
        if isinstance(value, (str, Path)):
            return Path(value).expanduser()
        return value


@lru_cache()
def get_settings() -> Settings:
    return Settings()
