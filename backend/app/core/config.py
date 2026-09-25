
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

                                                                   
    elasticemail_api_key: SecretStr | None = None
    email_from: str = "TradeBay <noreply@localhost>"
    email_timeout_seconds: int = 30

    rate_limit_enabled: bool = False
    rate_limit_per_minute: int = 60

    ai_provider: str = "openai"
    ai_base_url: str = "https://api.openai.com/v1"
    ai_api_key: SecretStr | None = None
    ai_timeout_seconds: int = 30
                                                                                  
                                                                            
    ai_max_retries: int = 1
    ai_structured_retries: int = 1
                                                                        
    ai_model: str | None = None
    ai_chat_model: str | None = None
    ai_embedding_model: str | None = None
    ai_max_candidates: int = 80
    ai_top_k: int = 24
                                                                        
    ai_vector_search_enabled: bool = False
    ai_vector_index_name: str = "catalog_embeddings_vector"
    ai_embedding_sync_batch: int = 32
                                                                               
    ai_category_cache_seconds: int = 60
                                                                          
    ai_daily_request_quota: int = 200

    tracking_webhook_secret: SecretStr | None = None

                                                                                  
                                                                                               
    stripe_secret_key: SecretStr | None = None
    stripe_publishable_key: str | None = None
    stripe_webhook_secret: SecretStr | None = None
    stripe_api_base: str = "https://api.stripe.com"
    stripe_timeout_seconds: int = 20
    sentry_dsn: str | None = None
    otel_exporter_otlp_endpoint: str | None = None

    @field_validator(
        "sentry_dsn",
        "otel_exporter_otlp_endpoint",
        "stripe_secret_key",
        "stripe_publishable_key",
        "stripe_webhook_secret",
        mode="before",
    )
    @classmethod
    def empty_str_to_none(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str) and not value.strip().strip("\"'"):
            return None
        return value

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
