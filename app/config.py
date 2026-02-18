from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables with validation."""

    model_config = SettingsConfigDict(
        env_file=(str(Path(__file__).resolve().parents[1] / ".env"), ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    app_name: str = Field(default="Summit Voice AI API", alias="APP_NAME")
    app_env: Literal["development", "staging", "production", "test"] = Field(
        default="production",
        alias="APP_ENV",
    )
    app_debug: bool = Field(default=False, alias="APP_DEBUG")
    api_v1_prefix: str = Field(default="/api/v1", alias="API_V1_PREFIX")
    secret_key: SecretStr = Field(
        default=SecretStr("change-me-in-production"),
        alias="SECRET_KEY",
    )
    admin_email: str = Field(default="dan@summitvoiceai.com", alias="ADMIN_EMAIL")
    admin_name: str = Field(default="Dan Gill", alias="ADMIN_NAME")
    admin_password_hash: SecretStr = Field(
        default=SecretStr(
            "pbkdf2_sha256$210000$a9419468634dcc737dd5c2a3b19fd3f3$"
            "b8b9226408ea3c456eb89a571ec04c9cac71546c009e4d031b2e855570ad89a8"
        ),
        alias="ADMIN_PASSWORD_HASH",
    )

    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"],
        alias="CORS_ORIGINS",
    )

    supabase_url: AnyHttpUrl = Field(
        default="https://ehgaliwonozomcvflleg.supabase.co",
        alias="SUPABASE_URL",
    )
    supabase_anon_key: SecretStr = Field(
        default=SecretStr(
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImVoZ2FsaXdvbm96b21jdmZsbGVnIiwicm9sZSI6"
            "ImFub24iLCJpYXQiOjE3NzEyNTg0NzMsImV4cCI6MjA4NjgzNDQ3M30."
            "O67BSMOPpMeY8NalI3IHdqj6qe9d84llRY1yaL1Dk0s"
        ),
        alias="SUPABASE_ANON_KEY",
    )
    supabase_service_key: SecretStr = Field(
        default=SecretStr(
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImVoZ2FsaXdvbm96b21jdmZsbGVnIiwicm9sZSI6"
            "InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MTI1ODQ3MywiZXhwIjoyMDg2ODM0NDczfQ."
            "pMtsLsbdBRwQ3N8BMavObwrwIsHkbg4yrxPOovnUIEg"
        ),
        alias="SUPABASE_SERVICE_KEY",
    )

    database_url: str = Field(
        default=(
            "postgresql://postgres.ehgaliwonozomcvflleg:1Timothy3:16!!!!"
            "@aws-0-us-east-1.pooler.supabase.com:6543/postgres"
        ),
        alias="DATABASE_URL",
    )

    db_pool_size: int = Field(default=10, ge=1, le=100, alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=20, ge=0, le=200, alias="DB_MAX_OVERFLOW")
    db_pool_timeout: int = Field(default=30, ge=1, le=300, alias="DB_POOL_TIMEOUT")
    db_pool_recycle: int = Field(default=1800, ge=60, alias="DB_POOL_RECYCLE")
    db_connect_timeout: int = Field(default=10, ge=1, le=60, alias="DB_CONNECT_TIMEOUT")

    anthropic_api_key: SecretStr = Field(
        default=SecretStr(
            "sk-ant-api03-X5FQJUYAMAxXdPqDG8KhcT3q7cNySw0MonnNiN6yOXOnfeyFJykse1txsC4hV9H"
            "XzWIxc54soGdsjXBEIxSRpQ-6RzZVAAA"
        ),
        alias="ANTHROPIC_API_KEY",
    )

    @field_validator("api_v1_prefix")
    @classmethod
    def validate_api_prefix(cls, value: str) -> str:
        """Ensure the API prefix starts with a slash and has no trailing slash."""
        normalized = value.strip()
        if not normalized.startswith("/"):
            raise ValueError("API_V1_PREFIX must start with '/'.")
        if len(normalized) > 1 and normalized.endswith("/"):
            normalized = normalized.rstrip("/")
        return normalized

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        """Support comma-separated CORS origins from environment variables."""
        if isinstance(value, str):
            if not value.strip():
                return []
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        """Validate database URL is a PostgreSQL SQLAlchemy-compatible connection string."""
        lowered = value.lower()
        if not (lowered.startswith("postgresql://") or lowered.startswith("postgresql+psycopg2://")):
            raise ValueError("DATABASE_URL must start with postgresql:// or postgresql+psycopg2://")
        return value


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance."""
    return Settings()


settings: Settings = get_settings()

# Revenue sprint profile for first-revenue mode.
REVENUE_SPRINT_MODE = {
    "enabled": True,
    "daily_lead_target": 100,
    "daily_outreach_target": 50,
    "daily_meeting_target": 3,
    "max_daily_spend": 5.00,
    "apollo_daily_limit": 160,
    "hunter_daily_limit": 1,
    "sendgrid_daily_limit": 100,
    "anthropic_daily_budget": 1.50,
}
