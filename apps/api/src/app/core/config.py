"""Typed, injectable application settings for the API process.

Settings are read from the real process environment using the ``NORDIC_API_``
prefix. A database URL is intentionally represented as a secret value and is
never rendered by the application. Local Compose variables remain supported as a
convenience fallback for explicit migrations, seeds, and later session use.
"""

import os
from decimal import Decimal
from functools import lru_cache
from typing import Literal
from urllib.parse import quote, urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "test", "staging", "production"]
LogLevel = Literal["debug", "info", "warning", "error", "critical"]
LogFormat = Literal["console", "json"]
CookieSameSite = Literal["lax", "strict", "none"]
EmbeddingProviderName = Literal["openai", "azure_openai", "deterministic"]
RagCompletionProviderName = Literal["openai", "azure_openai", "deterministic"]


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

    # Metrics are intentionally opt-in: production ingress must expose this
    # unauthenticated operational endpoint only to an internal scraper.  The
    # local Compose stack opts in explicitly for developer inspection.
    metrics_enabled: bool = False
    otlp_endpoint: str | None = None
    otlp_export_timeout_seconds: float = Field(default=5.0, gt=0, le=30)

    api_prefix: str = "/api"
    # Documentation is useful in local development and tests, but must not be
    # published by default from a deployed service. Operators may still opt in
    # deliberately for a protected environment.
    enable_docs: bool | None = None

    # Browser origins are exact scheme/host/port values. Empty CORS origins
    # means CORS is disabled rather than permissive. CSRF origins are required
    # for deployed cookie-authenticated browser traffic.
    cors_allowed_origins: tuple[str, ...] = ()
    csrf_trusted_origins: tuple[str, ...] = ()

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

    upload_rate_limit_window_seconds: int = Field(default=900, ge=30, le=86_400)
    upload_rate_limit_user_attempts: int = Field(default=10, ge=1, le=1_000)
    upload_rate_limit_origin_attempts: int = Field(default=40, ge=1, le=5_000)
    retrieval_rate_limit_window_seconds: int = Field(default=900, ge=30, le=86_400)
    retrieval_rate_limit_user_attempts: int = Field(default=60, ge=1, le=10_000)
    retrieval_rate_limit_origin_attempts: int = Field(default=240, ge=1, le=20_000)
    workflow_rate_limit_window_seconds: int = Field(default=900, ge=30, le=86_400)
    workflow_rate_limit_user_attempts: int = Field(default=10, ge=1, le=1_000)
    workflow_rate_limit_origin_attempts: int = Field(default=40, ge=1, le=5_000)

    # Raw document objects stay in a private Azure Blob-compatible container.
    # An explicit connection string is always represented as a secret. Local
    # Compose derives the well-known Azurite development connection only when
    # a document upload actually needs it.
    document_upload_max_bytes: int = Field(default=25 * 1024 * 1024, ge=1, le=100 * 1024 * 1024)
    document_upload_multipart_overhead_bytes: int = Field(
        default=1 * 1024 * 1024, ge=1_024, le=10 * 1024 * 1024
    )
    object_storage_connection_string: SecretStr | None = None
    object_storage_container: str = "nordic-local"
    # A non-secret endpoint used only by readiness probes. Local/test may
    # derive Azurite's endpoint; deployed environments must provide the
    # concrete private-storage service endpoint explicitly.
    object_storage_health_url: str | None = None

    # Parsing happens only in the worker. These independent bounds prevent a
    # valid upload from becoming an unbounded worker workload later.
    document_parser_max_input_bytes: int = Field(
        default=25 * 1024 * 1024, ge=1, le=100 * 1024 * 1024
    )
    document_parser_max_extracted_characters: int = Field(
        default=2_000_000, ge=1_000, le=10_000_000
    )
    document_parser_max_sections: int = Field(default=10_000, ge=1, le=100_000)
    document_parser_task_timeout_seconds: int = Field(default=120, ge=5, le=900)
    document_parser_task_max_retries: int = Field(default=3, ge=0, le=10)
    document_parser_worker_concurrency: int = Field(default=1, ge=1, le=8)
    document_parser_reconciliation_interval_seconds: int = Field(default=60, ge=10, le=3600)
    document_parser_processing_lease_seconds: int = Field(default=300, ge=30, le=3600)
    document_language_confidence_threshold: float = Field(default=0.80, ge=0.5, le=1.0)
    document_language_minimum_characters: int = Field(default=40, ge=1, le=10_000)

    # Embedding calls are worker-only. ``deterministic`` exists solely for
    # explicit local/test plumbing checks; it never claims semantic quality and
    # is rejected by settings validation outside those environments.
    embedding_provider: EmbeddingProviderName = "openai"
    embedding_api_key: SecretStr | None = None
    embedding_azure_endpoint: SecretStr | None = None
    embedding_azure_api_version: str = "2024-02-01"
    embedding_model: str = "text-embedding-3-small"
    embedding_tokenizer_encoding: str = "cl100k_base"
    embedding_configuration_version: str = "v1"
    document_chunk_max_tokens: int = Field(default=512, ge=8, le=8_192)
    document_chunk_overlap_tokens: int = Field(default=64, ge=0, le=2_048)
    document_chunk_maximum_count: int = Field(default=10_000, ge=1, le=100_000)
    embedding_batch_size: int = Field(default=32, ge=1, le=128)
    embedding_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    document_indexer_task_timeout_seconds: int = Field(default=300, ge=10, le=1_800)
    document_indexer_task_max_retries: int = Field(default=3, ge=0, le=10)
    document_indexer_reconciliation_interval_seconds: int = Field(default=60, ge=10, le=3_600)
    document_indexer_processing_lease_seconds: int = Field(default=600, ge=30, le=7_200)

    # Retrieval consumes only the current Phase 12 index.  These limits cap
    # public result exposure and each independent candidate query; callers may
    # select a smaller public result count but never a larger candidate pool.
    retrieval_default_result_limit: int = Field(default=10, ge=1, le=50)
    retrieval_max_result_limit: int = Field(default=20, ge=1, le=100)
    retrieval_semantic_candidate_limit: int = Field(default=50, ge=1, le=500)
    retrieval_keyword_candidate_limit: int = Field(default=50, ge=1, le=500)
    retrieval_rank_fusion_constant: float = Field(default=60.0, gt=0, le=1_000)
    retrieval_max_query_characters: int = Field(default=2_000, ge=1, le=10_000)
    retrieval_max_document_selections: int = Field(default=20, ge=1, le=100)
    retrieval_max_excerpt_characters: int = Field(default=1_200, ge=16, le=5_000)
    # Context is intentionally a separate, server-owned limit: evidence cards
    # and an explicit source-context view have different exposure purposes.
    document_context_max_characters: int = Field(default=1_200, ge=64, le=5_000)

    # Direct RAG answering is deliberately a separate bounded completion
    # configuration. Provider secrets remain absent from repr/error output and
    # clients are constructed only on a real answer attempt.
    rag_completion_provider: RagCompletionProviderName = "openai"
    rag_completion_api_key: SecretStr | None = None
    rag_completion_azure_endpoint: SecretStr | None = None
    rag_completion_azure_api_version: str = "2024-02-01"
    rag_completion_model: str = "gpt-4.1-mini"
    rag_completion_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    rag_completion_max_output_tokens: int = Field(default=800, ge=1, le=8_192)
    rag_max_answer_characters: int = Field(default=8_000, ge=64, le=20_000)
    rag_max_evidence_sources: int = Field(default=5, ge=1, le=20)
    rag_max_evidence_characters: int = Field(default=5_000, ge=64, le=20_000)
    rag_min_evidence_sources: int = Field(default=1, ge=1, le=20)
    rag_min_evidence_characters: int = Field(default=200, ge=1, le=20_000)
    rag_input_price_per_million: Decimal | None = Field(default=None, ge=0)
    rag_output_price_per_million: Decimal | None = Field(default=None, ge=0)

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

    @field_validator(
        "service_name",
        "api_title",
        "release",
        "request_id_header",
        "embedding_model",
        "embedding_tokenizer_encoding",
        "embedding_configuration_version",
        "rag_completion_model",
    )
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

    @field_validator("otlp_endpoint")
    @classmethod
    def _validate_otlp_endpoint(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip().rstrip("/")
        if not trimmed:
            return None
        if not trimmed.startswith(("http://", "https://")):
            raise ValueError("otlp_endpoint must use http or https")
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

    @field_validator("cors_allowed_origins", "csrf_trusted_origins")
    @classmethod
    def _validate_browser_origins(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(_normalize_browser_origin(value) for value in values)
        if len(set(normalized)) != len(normalized):
            raise ValueError("browser origins must be unique")
        return normalized

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

    @field_validator("object_storage_connection_string", mode="before")
    @classmethod
    def _validate_object_storage_connection_string(cls, value: object) -> object:
        if value is None:
            return value
        raw_value = value.get_secret_value() if isinstance(value, SecretStr) else value
        if not isinstance(raw_value, str) or not raw_value.strip():
            raise ValueError("object_storage_connection_string must not be empty")
        if "AccountName=" not in raw_value or "AccountKey=" not in raw_value:
            raise ValueError("object_storage_connection_string is invalid")
        return value

    @field_validator("object_storage_health_url")
    @classmethod
    def _validate_object_storage_health_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        candidate = value.strip().rstrip("/")
        if not candidate:
            return None
        parsed = urlsplit(candidate)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("object_storage_health_url must be a non-secret http or https URL")
        return candidate

    @field_validator(
        "embedding_api_key",
        "embedding_azure_endpoint",
        "rag_completion_api_key",
        "rag_completion_azure_endpoint",
        mode="before",
    )
    @classmethod
    def _normalize_optional_embedding_secret(cls, value: object) -> object:
        if value is None:
            return None
        raw_value = value.get_secret_value() if isinstance(value, SecretStr) else value
        if not isinstance(raw_value, str):
            raise ValueError("embedding credential configuration is invalid")
        return raw_value if raw_value.strip() else None

    @field_validator("object_storage_container")
    @classmethod
    def _validate_object_storage_container(cls, value: str) -> str:
        container = value.strip().lower()
        if (
            len(container) < 3
            or len(container) > 63
            or container[0] == "-"
            or container[-1] == "-"
            or any(
                character not in "abcdefghijklmnopqrstuvwxyz0123456789-" for character in container
            )
            or "--" in container
        ):
            raise ValueError("object_storage_container must be a valid private blob container name")
        return container

    @model_validator(mode="after")
    def _validate_auth_configuration(self) -> "AppSettings":
        if self.password_min_length > self.password_max_length:
            raise ValueError("password_min_length must not exceed password_max_length")
        secure_cookie = self.session_cookie_secure_value
        if self.environment in {"staging", "production"} and not secure_cookie:
            raise ValueError("secure session cookies are required outside local and test")
        if self.session_cookie_samesite == "none" and not secure_cookie:
            raise ValueError("SameSite=None cookies require the Secure flag")
        if self.environment in {"staging", "production"} and not self.csrf_trusted_origins:
            raise ValueError("CSRF trusted origins are required outside local and test")
        if self.document_parser_max_input_bytes > self.document_upload_max_bytes:
            raise ValueError(
                "document_parser_max_input_bytes must not exceed document_upload_max_bytes"
            )
        if self.document_chunk_overlap_tokens >= self.document_chunk_max_tokens:
            raise ValueError(
                "document_chunk_overlap_tokens must be below document_chunk_max_tokens"
            )
        if self.embedding_provider == "deterministic" and self.environment not in {"local", "test"}:
            raise ValueError("deterministic embeddings are permitted only in local or test")
        if self.rag_completion_provider == "deterministic" and self.environment not in {
            "local",
            "test",
        }:
            raise ValueError("deterministic RAG completion is permitted only in local or test")
        if self.retrieval_default_result_limit > self.retrieval_max_result_limit:
            raise ValueError(
                "retrieval_default_result_limit must not exceed retrieval_max_result_limit"
            )
        if self.retrieval_max_result_limit > self.retrieval_semantic_candidate_limit:
            raise ValueError(
                "retrieval_max_result_limit must not exceed retrieval_semantic_candidate_limit"
            )
        if self.retrieval_max_result_limit > self.retrieval_keyword_candidate_limit:
            raise ValueError(
                "retrieval_max_result_limit must not exceed retrieval_keyword_candidate_limit"
            )
        if self.rag_min_evidence_sources > self.rag_max_evidence_sources:
            raise ValueError("rag_min_evidence_sources must not exceed rag_max_evidence_sources")
        if self.rag_min_evidence_characters > self.rag_max_evidence_characters:
            raise ValueError(
                "rag_min_evidence_characters must not exceed rag_max_evidence_characters"
            )
        if (self.rag_input_price_per_million is None) != (
            self.rag_output_price_per_million is None
        ):
            raise ValueError("RAG input and output price rates must be configured together")
        if self.environment in {"staging", "production"}:
            if self.database_url is None:
                raise ValueError("database_url is required outside local and test")
            if self.redis_url is None:
                raise ValueError("redis_url is required outside local and test")
            if self.object_storage_connection_string is None:
                raise ValueError(
                    "object_storage_connection_string is required outside local and test"
                )
            if self.object_storage_health_url is None:
                raise ValueError("object_storage_health_url is required outside local and test")
            if self.rate_limit_key_secret is None:
                raise ValueError("rate_limit_key_secret is required outside local and test")
            if self.embedding_api_key is None:
                raise ValueError("embedding credentials are required outside local and test")
            if self.embedding_provider == "azure_openai" and self.embedding_azure_endpoint is None:
                raise ValueError("Azure embedding endpoint is required for azure_openai")
            if self.rag_completion_api_key is None:
                raise ValueError("RAG completion credentials are required outside local and test")
            if (
                self.rag_completion_provider == "azure_openai"
                and self.rag_completion_azure_endpoint is None
            ):
                raise ValueError("Azure RAG completion endpoint is required for azure_openai")
            if self.rag_input_price_per_million is None:
                raise ValueError("RAG price rates are required outside local and test")
        return self

    @property
    def openapi_url(self) -> str | None:
        """Return the OpenAPI schema path, or ``None`` when docs are disabled."""

        return "/openapi.json" if self.enable_docs_value else None

    @property
    def docs_url(self) -> str | None:
        """Return the Swagger UI path, or ``None`` when docs are disabled."""

        return "/docs" if self.enable_docs_value else None

    @property
    def redoc_url(self) -> str | None:
        """Return the ReDoc path, or ``None`` when docs are disabled."""

        return "/redoc" if self.enable_docs_value else None

    @property
    def enable_docs_value(self) -> bool:
        """Return the effective docs policy without exposing deployed docs by default."""

        if self.enable_docs is not None:
            return self.enable_docs
        return self.environment in {"local", "test"}

    @property
    def document_upload_max_request_bytes(self) -> int:
        """Bound the whole multipart request, including trusted transport overhead."""

        return self.document_upload_max_bytes + self.document_upload_multipart_overhead_bytes

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

    def langgraph_store_url(self) -> str:
        """Return the private Postgres URL consumed by LangGraph's async store.

        This conversion is intentionally performed only at adapter construction;
        callers must never serialize, log, or return its value.
        """

        return self.database_sync_url().replace("postgresql+psycopg://", "postgresql://", 1)

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

    def object_storage_connection_string_value(self) -> str:
        """Return the private Azure Blob connection string only at adapter construction.

        Local/test processes may derive Azurite's public development account from
        Compose variables. Deployments must inject an explicit secret connection
        string; no production endpoint or account key is embedded in code.
        """

        if self.object_storage_connection_string is not None:
            return self.object_storage_connection_string.get_secret_value()
        if self.environment not in {"local", "test"}:
            raise RuntimeError("Private object storage is not configured")
        account_name = os.getenv("AZURITE_ACCOUNT_NAME", "devstoreaccount1")
        account_key = os.getenv(
            "AZURITE_ACCOUNT_KEY",
            "Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/"
            "K1SZFPTOtr/KBHBeksoGMGw==",
        )
        host = os.getenv("AZURITE_HOST", "azurite")
        port = os.getenv("AZURITE_BLOB_PORT", "10000")
        return (
            "DefaultEndpointsProtocol=http;"
            f"AccountName={account_name};AccountKey={account_key};"
            f"BlobEndpoint=http://{host}:{port}/{account_name};"
        )

    def object_storage_health_url_value(self) -> str:
        """Return the private-storage liveness URL without deriving deployed defaults."""

        if self.object_storage_health_url is not None:
            return self.object_storage_health_url
        if self.environment not in {"local", "test"}:
            raise RuntimeError("Object storage health configuration is unavailable")
        account_name = os.getenv("AZURITE_ACCOUNT_NAME", "devstoreaccount1")
        host = os.getenv("AZURITE_HOST", "azurite")
        port = os.getenv("AZURITE_BLOB_PORT", "10000")
        return f"http://{host}:{port}/{account_name}"

    def rate_limit_hmac_key(self) -> bytes:
        """Return the private key used solely to derive non-sensitive Redis keys."""

        if self.rate_limit_key_secret is not None:
            return self.rate_limit_key_secret.get_secret_value().encode("utf-8")
        if self.environment not in {"local", "test"}:
            raise RuntimeError("Rate-limit key configuration is unavailable")
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


def _normalize_browser_origin(value: str) -> str:
    """Normalize one exact browser origin and reject wildcard-like configuration."""

    candidate = value.strip()
    parsed = urlsplit(candidate)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("browser origins must be exact http or https origins")
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"
