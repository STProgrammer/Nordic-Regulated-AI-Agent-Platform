"""Typed, injectable application settings for the API process.

Settings are read from the real process environment using the ``NORDIC_API_``
prefix. A database URL is intentionally represented as a secret value and is
never rendered by the application. Local Compose variables remain supported as a
convenience fallback for explicit migrations, seeds, and later session use.
"""

import os
from functools import lru_cache
from typing import Literal
from urllib.parse import quote

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "test", "staging", "production"]
LogLevel = Literal["debug", "info", "warning", "error", "critical"]
LogFormat = Literal["console", "json"]
CookieSameSite = Literal["lax", "strict", "none"]


class AppSettings(BaseSettings):
    """Validated, immutable runtime configuration for the API application.

    The model only loads values from the real environment (no ``.env`` file is
    read automatically) so tests and operators get deterministic behavior. The
    instance is frozen so it can be cached and shared safely across requests.
    """

    model_config = SettingsConfigDict(
        env_prefix="NORDIC_API_",
        case_sensitive=False,
        extra="ignore",
        frozen=True,
        hide_input_in_errors=True,
    )

    environment: Environment = "local"
    service_name: str = "nordic-regulated-ai-api"
    api_title: str = "Nordic Regulated AI Agent Platform API"
    release: str = "0.0.0"

    log_level: LogLevel = "info"
    log_format: LogFormat = "console"

    api_prefix: str = "/api"
    enable_docs: bool = True

    request_id_header: str = "X-Request-ID"
    request_id_max_length: int = Field(default=128, ge=8, le=256)

    # An explicit async SQLAlchemy URL is preferred outside Compose. It is optional
    # so importing the API, running health checks, and constructing settings never
    # require database configuration or make a network connection.
    database_url: SecretStr | None = None
    database_pool_size: int = Field(default=5, ge=1, le=50)
    database_max_overflow: int = Field(default=10, ge=0, le=100)

    # Authentication state is intentionally volatile. Redis credentials remain
    # secret values, and the fallback only targets the local Compose service.
    redis_url: SecretStr | None = None
    redis_socket_timeout_seconds: float = Field(default=2.0, gt=0, le=10)

    session_cookie_name: str = "nordic_session"
    session_cookie_path: str = "/"
    session_cookie_domain: str | None = None
    session_cookie_samesite: CookieSameSite = "lax"
    # ``None`` selects the safe environment default: only explicit local/test
    # applications may use a non-secure cookie.
    session_cookie_secure: bool | None = None
    session_ttl_seconds: int = Field(default=28_800, ge=300, le=604_800)

    password_min_length: int = Field(default=12, ge=8, le=128)
    password_max_length: int = Field(default=512, ge=64, le=1024)

    login_rate_limit_window_seconds: int = Field(default=900, ge=30, le=86_400)
    login_rate_limit_email_attempts: int = Field(default=5, ge=1, le=100)
    login_rate_limit_origin_attempts: int = Field(default=20, ge=1, le=500)
    # A keyed digest prevents Redis keys from containing raw email/IP values.
    # Deployments should provide an injected secret; the fallback keeps local
    # configuration credential-free while still avoiding raw identifier keys.
    rate_limit_key_secret: SecretStr | None = None

    @field_validator("api_prefix")
    @classmethod
    def _normalize_api_prefix(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed.startswith("/"):
            raise ValueError("api_prefix must start with '/'")
        normalized = trimmed.rstrip("/")
        if not normalized:
            raise ValueError("api_prefix must not be the root path")
        return normalized

    @field_validator("service_name", "api_title", "release", "request_id_header")
    @classmethod
    def _require_non_empty(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("value must not be empty")
        return trimmed

    @field_validator("session_cookie_name")
    @classmethod
    def _validate_cookie_name(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed or any(character.isspace() for character in trimmed):
            raise ValueError("session_cookie_name must be a non-empty token")
        return trimmed

    @field_validator("session_cookie_path")
    @classmethod
    def _validate_cookie_path(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed.startswith("/"):
            raise ValueError("session_cookie_path must start with '/'")
        return trimmed

    @field_validator("session_cookie_domain")
    @classmethod
    def _normalize_cookie_domain(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None

    @field_validator("database_url", mode="before")
    @classmethod
    def _validate_database_url(cls, value: object) -> object:
        if value is None:
            return value
        raw_value = value.get_secret_value() if isinstance(value, SecretStr) else value
        if not isinstance(raw_value, str):
            raise ValueError("database_url must be a PostgreSQL async URL")
        if not raw_value.startswith("postgresql+asyncpg://"):
            raise ValueError("database_url must use the postgresql+asyncpg scheme")
        return value

    @field_validator("redis_url", mode="before")
    @classmethod
    def _validate_redis_url(cls, value: object) -> object:
        if value is None:
            return value
        raw_value = value.get_secret_value() if isinstance(value, SecretStr) else value
        if not isinstance(raw_value, str) or not raw_value.startswith(("redis://", "rediss://")):
            raise ValueError("redis_url must use a Redis URL scheme")
        return value

    @model_validator(mode="after")
    def _validate_auth_configuration(self) -> "AppSettings":
        if self.password_min_length > self.password_max_length:
            raise ValueError("password_min_length must not exceed password_max_length")
        secure_cookie = self.session_cookie_secure_value
        if self.environment in {"staging", "production"} and not secure_cookie:
            raise ValueError("secure session cookies are required outside local and test")
        if self.session_cookie_samesite == "none" and not secure_cookie:
            raise ValueError("SameSite=None cookies require the Secure flag")
        return self

    @property
    def openapi_url(self) -> str | None:
        """Return the OpenAPI schema path, or ``None`` when docs are disabled."""

        return "/openapi.json" if self.enable_docs else None

    @property
    def docs_url(self) -> str | None:
        """Return the Swagger UI path, or ``None`` when docs are disabled."""

        return "/docs" if self.enable_docs else None

    @property
    def redoc_url(self) -> str | None:
        """Return the ReDoc path, or ``None`` when docs are disabled."""

        return "/redoc" if self.enable_docs else None

    def database_async_url(self) -> str:
        """Return the runtime async URL without exposing it through model reprs.

        Compose supplies the individual ``POSTGRES_*`` values already used by the
        Phase 2 health probe. The fallback deliberately exists only at use time;
        constructing settings remains side-effect free and no URL is logged.
        """

        if self.database_url is not None:
            return self.database_url.get_secret_value()

        host = os.getenv("POSTGRES_HOST", "postgres")
        port = os.getenv("POSTGRES_PORT", "5432")
        database = os.getenv("POSTGRES_DB", "nordic_local")
        user = os.getenv("POSTGRES_USER", "nordic_local")
        password = os.getenv("POSTGRES_PASSWORD", "local-postgres-password-not-for-production")
        return (
            "postgresql+asyncpg://"
            f"{quote(user, safe='')}:{quote(password, safe='')}@{host}:{port}/{database}"
        )

    def database_sync_url(self) -> str:
        """Return the private Alembic-only psycopg URL derived from async config."""

        async_url = self.database_async_url()
        prefix = "postgresql+asyncpg://"
        if not async_url.startswith(prefix):
            # The validation above protects normal settings construction. Keep this
            # error neutral as settings can be supplied directly in tests.
            raise RuntimeError("Database configuration is invalid")
        return "postgresql+psycopg://" + async_url.removeprefix(prefix)

    @property
    def session_cookie_secure_value(self) -> bool:
        """Return the effective secure-cookie policy without exposing secrets."""

        if self.session_cookie_secure is not None:
            return self.session_cookie_secure
        return self.environment not in {"local", "test"}

    def redis_async_url(self) -> str:
        """Return the private Redis URL only at the point a client is needed."""

        if self.redis_url is not None:
            return self.redis_url.get_secret_value()
        host = os.getenv("REDIS_HOST", "redis")
        port = os.getenv("REDIS_PORT", "6379")
        return f"redis://{host}:{port}/0"

    def rate_limit_hmac_key(self) -> bytes:
        """Return the private key used solely to derive non-sensitive Redis keys."""

        if self.rate_limit_key_secret is not None:
            return self.rate_limit_key_secret.get_secret_value().encode("utf-8")
        return b"nordic-local-development-rate-limit-key"


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Return the cached application settings built from the environment.

    Tests reset the cache with :func:`reset_settings_cache` or override the
    FastAPI dependency so configuration never leaks between application factories.
    """

    return AppSettings()


def reset_settings_cache() -> None:
    """Clear the cached settings so the next call re-reads the environment."""

    get_settings.cache_clear()
