"""Typed environment configuration. Secrets are never hardcoded."""

from functools import lru_cache

from pydantic import Field, SecretStr, field_validator, model_validator
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
    cors_origins: str = (
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:3001,http://127.0.0.1:3001"
    )

    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    cookie_domain: str | None = None

    # Email — Elastic Email API. Falls back to log-only when unset.
    elasticemail_api_key: SecretStr | None = None
    email_from: str = "TradeBay <noreply@localhost>"
    email_timeout_seconds: int = 30

    rate_limit_enabled: bool = False
    rate_limit_per_minute: int = 60

    ai_provider: str = "stub"
    ai_api_key: SecretStr | None = None
    ai_timeout_seconds: int = 30
    ai_model: str | None = None
    # RAG for AI sourcing — advisory catalog context only (default off).
    ai_rag_enabled: bool = False
    ai_rag_mode: str = "lexical"  # lexical | embedding
    ai_rag_top_k: int = 8
    ai_rag_product_limit: int = 400
    ai_embedding_model: str | None = None

    tracking_webhook_secret: SecretStr | None = None
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

    @model_validator(mode="after")
    def harden_production_defaults(self) -> "Settings":
        if self.cookie_samesite == "none" and not self.cookie_secure:
            object.__setattr__(self, "cookie_secure", True)
        if self.app_env == AppEnv.PRODUCTION:
            # Secure cookies and rate limiting are mandatory in production.
            object.__setattr__(self, "cookie_secure", True)
            object.__setattr__(self, "rate_limit_enabled", True)
            object.__setattr__(self, "app_debug", False)
            weak_markers = ("change-me", "changeme", "your-secret", "replace-me")
            for label, secret in (
                ("SECRET_KEY", self.secret_key.get_secret_value()),
                ("JWT_SECRET_KEY", self.jwt_secret_key.get_secret_value()),
            ):
                lowered = secret.strip().lower()
                if len(secret) < 32 or any(token in lowered for token in weak_markers):
                    raise ValueError(
                        f"{label} must be a unique random string of at least 32 characters "
                        "before running with APP_ENV=production"
                    )
        return self

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
