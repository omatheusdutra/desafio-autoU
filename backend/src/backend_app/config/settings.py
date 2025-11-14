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
    enable_transformers: bool = Field(
        default=True, validation_alias="ENABLE_TRANSFORMERS"
    )
    openai_api_key: Optional[str] = Field(
        default=None, validation_alias="OPENAI_API_KEY"
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
    max_batch_items: int = Field(
        default=200, validation_alias="MAX_BATCH_ITEMS"
    )

    @field_validator("audit_log_path", "reports_dir", mode="before")
    @classmethod
    def _expand_path(cls, value):
        if isinstance(value, (str, Path)):
            return Path(value).expanduser()
        return value


@lru_cache()
def get_settings() -> Settings:
    return Settings()
