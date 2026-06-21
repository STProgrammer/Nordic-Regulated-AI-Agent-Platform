import os
from asyncio import run
from collections.abc import Iterator
from decimal import Decimal
from typing import cast

import pytest
from app.core.config import AppSettings, Environment, get_settings, reset_settings_cache
from app.db.session import dispose_database_engines, get_async_engine
from pydantic import SecretStr, ValidationError


@pytest.fixture(autouse=True)
def _clean_settings_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for key in list(os.environ):
        if key.startswith("NORDIC_API_"):
            monkeypatch.delenv(key, raising=False)
    reset_settings_cache()
    yield
    reset_settings_cache()


def test_defaults_are_safe_local_values() -> None:
    settings = AppSettings()

    assert settings.environment == "local"
    assert settings.service_name == "nordic-regulated-ai-api"
    assert settings.api_prefix == "/api"
    assert settings.enable_docs is None
    assert settings.enable_docs_value is True
    assert settings.log_level == "info"
    assert settings.log_format == "console"
    assert settings.request_id_header == "X-Request-ID"
    assert settings.request_id_max_length == 128
    assert settings.session_cookie_name == "nordic_session"
    assert settings.session_cookie_secure_value is False
    assert settings.session_ttl_seconds == 28_800
    assert settings.document_upload_max_bytes == 25 * 1024 * 1024
    assert settings.document_parser_max_input_bytes == 25 * 1024 * 1024
    assert settings.document_parser_task_max_retries == 3
    assert settings.document_parser_worker_concurrency == 1
    assert settings.object_storage_container == "nordic-local"
    assert settings.retrieval_default_result_limit == 10
    assert settings.retrieval_max_result_limit == 20
    assert settings.retrieval_rank_fusion_constant == 60
    assert settings.document_context_max_characters == 1_200


def test_documentation_urls_follow_enable_docs() -> None:
    enabled = AppSettings(enable_docs=True)
    assert enabled.openapi_url == "/openapi.json"
    assert enabled.docs_url == "/docs"
    assert enabled.redoc_url == "/redoc"

    disabled = AppSettings(enable_docs=False)
    assert disabled.openapi_url is None
    assert disabled.docs_url is None
    assert disabled.redoc_url is None


def test_browser_origins_are_exact_and_deployed_csrf_configuration_is_required() -> None:
    settings = AppSettings(
        cors_allowed_origins=("HTTPS://App.Example.Invalid/",),
        csrf_trusted_origins=("https://app.example.invalid",),
    )
    assert settings.cors_allowed_origins == ("https://app.example.invalid",)
    assert settings.csrf_trusted_origins == ("https://app.example.invalid",)

    with pytest.raises(ValidationError):
        AppSettings(cors_allowed_origins=("*",))
    with pytest.raises(ValidationError):
        AppSettings(
            environment="production",
            rag_completion_api_key=SecretStr("synthetic-rag-key"),
            rag_input_price_per_million=Decimal("1"),
            rag_output_price_per_million=Decimal("2"),
        )

    deployed = AppSettings(
        environment="staging",
        csrf_trusted_origins=("https://app.example.invalid",),
        rag_completion_api_key=SecretStr("synthetic-rag-key"),
        rag_input_price_per_million=Decimal("1"),
        rag_output_price_per_million=Decimal("2"),
    )
    assert deployed.enable_docs_value is False


@pytest.mark.parametrize("environment", ["local", "test", "staging", "production"])
def test_allowed_environments(environment: str) -> None:
    if environment in {"staging", "production"}:
        settings = AppSettings(
            environment=cast(Environment, environment),
            rag_completion_api_key=SecretStr("synthetic-rag-key"),
            rag_input_price_per_million=Decimal("1"),
            rag_output_price_per_million=Decimal("2"),
            csrf_trusted_origins=("https://app.example.invalid",),
        )
    else:
        settings = AppSettings(environment=cast(Environment, environment))
    assert settings.environment == environment


def test_invalid_environment_is_rejected() -> None:
    with pytest.raises(ValidationError):
        AppSettings(environment="prod")  # type: ignore[arg-type]


def test_invalid_log_level_is_rejected() -> None:
    with pytest.raises(ValidationError):
        AppSettings(log_level="trace")  # type: ignore[arg-type]


def test_api_prefix_is_normalized() -> None:
    assert AppSettings(api_prefix="/api/").api_prefix == "/api"
    assert AppSettings(api_prefix="/v1/api").api_prefix == "/v1/api"


@pytest.mark.parametrize("invalid_prefix", ["api", "", "/"])
def test_invalid_api_prefix_is_rejected(invalid_prefix: str) -> None:
    with pytest.raises(ValidationError):
        AppSettings(api_prefix=invalid_prefix)


@pytest.mark.parametrize("invalid_length", [4, 300])
def test_request_id_length_bounds_are_enforced(invalid_length: int) -> None:
    with pytest.raises(ValidationError):
        AppSettings(request_id_max_length=invalid_length)


def test_empty_required_strings_are_rejected() -> None:
    with pytest.raises(ValidationError):
        AppSettings(service_name="   ")


def test_settings_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NORDIC_API_ENVIRONMENT", "staging")
    monkeypatch.setenv("NORDIC_API_LOG_FORMAT", "json")
    monkeypatch.setenv("NORDIC_API_RAG_COMPLETION_API_KEY", "synthetic-rag-key")
    monkeypatch.setenv("NORDIC_API_RAG_INPUT_PRICE_PER_MILLION", "1")
    monkeypatch.setenv("NORDIC_API_RAG_OUTPUT_PRICE_PER_MILLION", "2")
    monkeypatch.setenv("NORDIC_API_CSRF_TRUSTED_ORIGINS", '["https://app.example.invalid"]')

    settings = AppSettings()

    assert settings.environment == "staging"
    assert settings.log_format == "json"


def test_get_settings_is_cached_and_resettable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = get_settings()
    assert get_settings() is first

    monkeypatch.setenv("NORDIC_API_ENVIRONMENT", "production")
    monkeypatch.setenv("NORDIC_API_RAG_COMPLETION_API_KEY", "synthetic-rag-key")
    monkeypatch.setenv("NORDIC_API_RAG_INPUT_PRICE_PER_MILLION", "1")
    monkeypatch.setenv("NORDIC_API_RAG_OUTPUT_PRICE_PER_MILLION", "2")
    monkeypatch.setenv("NORDIC_API_CSRF_TRUSTED_ORIGINS", '["https://app.example.invalid"]')
    assert get_settings() is first  # still cached

    reset_settings_cache()
    refreshed = get_settings()
    assert refreshed is not first
    assert refreshed.environment == "production"


def test_settings_are_immutable() -> None:
    settings = AppSettings()
    with pytest.raises(ValidationError):
        settings.environment = "production"


def test_production_requires_secure_cookie_but_derives_it_by_default() -> None:
    production_settings = AppSettings(
        environment="production",
        rag_completion_api_key=SecretStr("synthetic-rag-key"),
        rag_input_price_per_million=Decimal("1"),
        rag_output_price_per_million=Decimal("2"),
        csrf_trusted_origins=("https://app.example.invalid",),
    )
    assert production_settings.session_cookie_secure_value is True
    with pytest.raises(ValidationError):
        AppSettings(
            environment="production",
            session_cookie_secure=False,
            rag_completion_api_key=SecretStr("synthetic-rag-key"),
            rag_input_price_per_million=Decimal("1"),
            rag_output_price_per_million=Decimal("2"),
            csrf_trusted_origins=("https://app.example.invalid",),
        )


def test_password_bounds_and_redis_urls_are_validated_without_leaking_values() -> None:
    with pytest.raises(ValidationError):
        AppSettings(password_min_length=129, password_max_length=64)
    with pytest.raises(ValidationError) as error:
        AppSettings(redis_url=SecretStr("not-a-redis-url-with-a-secret"))
    assert "not-a-redis-url-with-a-secret" not in str(error.value)


def test_database_urls_are_secret_safe_and_convert_for_alembic() -> None:
    async_url = "postgresql+asyncpg://fixture-user:fixture-password@localhost:5432/fixture"
    settings = AppSettings(database_url=SecretStr(async_url))

    assert settings.database_async_url() == async_url
    assert settings.database_sync_url() == (
        "postgresql+psycopg://fixture-user:fixture-password@localhost:5432/fixture"
    )
    assert "fixture-password" not in repr(settings)


def test_database_url_validation_hides_sensitive_input() -> None:
    unsafe_url = "postgresql://fixture-user:fixture-password@localhost:5432/fixture"

    with pytest.raises(ValidationError) as error:
        AppSettings(database_url=SecretStr(unsafe_url))

    assert "fixture-password" not in str(error.value)


def test_object_storage_configuration_is_secret_safe_and_requires_valid_container() -> None:
    connection_string = "DefaultEndpointsProtocol=https;AccountName=fixture;AccountKey=fixture-key;"
    settings = AppSettings(object_storage_connection_string=SecretStr(connection_string))

    assert settings.object_storage_connection_string_value() == connection_string
    assert "fixture-key" not in repr(settings)
    with pytest.raises(ValidationError):
        AppSettings(object_storage_container="bad--container")


def test_parser_bounds_are_validated_as_one_worker_contract() -> None:
    with pytest.raises(ValidationError):
        AppSettings(document_parser_max_input_bytes=25 * 1024 * 1024 + 1)
    with pytest.raises(ValidationError):
        AppSettings(document_parser_worker_concurrency=0)
    with pytest.raises(ValidationError):
        AppSettings(document_language_confidence_threshold=0.49)


def test_retrieval_limits_form_one_safe_server_owned_contract() -> None:
    with pytest.raises(ValidationError):
        AppSettings(retrieval_default_result_limit=21, retrieval_max_result_limit=20)
    with pytest.raises(ValidationError):
        AppSettings(retrieval_max_result_limit=51, retrieval_semantic_candidate_limit=50)
    with pytest.raises(ValidationError):
        AppSettings(retrieval_max_result_limit=51, retrieval_keyword_candidate_limit=50)
    with pytest.raises(ValidationError):
        AppSettings(document_context_max_characters=63)


def test_rag_limits_pricing_and_production_credentials_are_validated() -> None:
    with pytest.raises(ValidationError):
        AppSettings(rag_min_evidence_sources=6, rag_max_evidence_sources=5)
    with pytest.raises(ValidationError):
        AppSettings(rag_min_evidence_characters=501, rag_max_evidence_characters=500)
    with pytest.raises(ValidationError):
        AppSettings(rag_input_price_per_million=Decimal("1"))
    with pytest.raises(ValidationError):
        AppSettings(environment="production")


def test_engine_construction_is_lazy() -> None:
    settings = AppSettings(
        database_url=SecretStr(
            "postgresql+asyncpg://fixture-user:fixture-password@localhost:5432/fixture"
        )
    )

    engine = get_async_engine(settings)

    assert str(engine.url).startswith("postgresql+asyncpg://")
    run(dispose_database_engines())
