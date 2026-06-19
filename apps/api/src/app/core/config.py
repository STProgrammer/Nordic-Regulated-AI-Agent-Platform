"""Typed, injectable application settings for the API process.

Settings are read from the real process environment using the ``NORDIC_API_``
prefix. Defaults are deliberately safe local-development values and never contain
secrets. Database, Redis, MinIO, model-provider, authentication, CORS, and
security-policy configuration are intentionally excluded here; the existing health
probes read their own connection values directly, and the remaining concerns are
owned by later roadmap phases.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "test", "staging", "production"]
LogLevel = Literal["debug", "info", "warning", "error", "critical"]
LogFormat = Literal["console", "json"]


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
