"""Typed environment configuration. Secrets are never hardcoded."""

from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.constants import AppEnv


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "TradeBay"
    app_env: AppEnv = AppEnv.DEVELOPMENT
    app_debug: bool = False
    log_level: str = "INFO"

    secret_key: SecretStr = Field(min_length=16)
    jwt_secret_key: SecretStr = Field(min_length=16)
    jwt_algorithm: str = "HS256"

    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 14

    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_database: str = "tradebay"

    frontend_url: str = "http://localhost:3000"
    cors_origins: str = "http://localhost:3000"

    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    cookie_domain: str | None = None

    # Email — Elastic Email API (same pattern as WorkNest). Falls back to log-only when unset.
    elasticemail_api_key: SecretStr | None = None
    email_from: str = "TradeBay <fatimaghazzawi10@gmail.com>"
    email_timeout_seconds: int = 30

    rate_limit_enabled: bool = False
    rate_limit_per_minute: int = 60

    ai_provider: str = "stub"
    ai_api_key: SecretStr | None = None
    ai_timeout_seconds: int = 30
    ai_model: str | None = None

    sentry_dsn: str | None = None
    otel_exporter_otlp_endpoint: str | None = None

    @field_validator("cookie_samesite")
    @classmethod
    def validate_samesite(cls, value: str) -> str:
        allowed = {"lax", "strict", "none"}
        lowered = value.lower()
        if lowered not in allowed:
            raise ValueError(f"COOKIE_SAMESITE must be one of {allowed}")
        return lowered

    @property
    def is_production(self) -> bool:
        return self.app_env == AppEnv.PRODUCTION

    @property
    def is_test(self) -> bool:
        return self.app_env == AppEnv.TEST

    @property
    def cors_origin_list(self) -> list[str]:
        origins = [item.strip() for item in self.cors_origins.split(",") if item.strip()]
        if self.is_production and ("*" in origins or not origins):
            raise ValueError("Production CORS_ORIGINS must be an explicit allow-list")
        return origins

    @property
    def docs_url(self) -> str | None:
        return None if self.is_production else "/docs"

    @property
    def redoc_url(self) -> str | None:
        return None if self.is_production else "/redoc"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    get_settings.cache_clear()
