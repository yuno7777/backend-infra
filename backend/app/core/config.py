from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+psycopg://backend_infra:backend_infra@127.0.0.1:54329/backend_infra"
    test_database_url: str = "postgresql+psycopg://backend_infra:backend_infra@127.0.0.1:54329/backend_infra_test"
    db_pool_size: int = Field(default=10, ge=1, le=100)
    db_max_overflow: int = Field(default=10, ge=0, le=100)

    # Tokens / webhooks (server-side peppers for hashing)
    token_hash_pepper: str = "dev-only-pepper-change-me"

    # Logging / runtime
    log_format: str = "console"  # console | json
    log_level: str = "INFO"
    api_port: int = 8080

    # Rate limiting (in-process per user)
    rate_limit_default_per_min: int = 120
    rate_limit_login_per_min: int = 10

    # Jobs
    job_default_timeout_seconds: int = Field(default=300, ge=1, le=3600)
    job_default_max_attempts: int = Field(default=3, ge=1, le=10)

    # Idempotency
    idempotency_key_ttl_hours: int = 24
    idempotency_replay: bool = True

    # Data directory for report artifacts
    data_dir: str = "data"

    # Environment name surfaced in responses ("local" here; deployment may set "prod")
    environment: str = "local"


@lru_cache
def get_settings() -> Settings:
    return Settings()
