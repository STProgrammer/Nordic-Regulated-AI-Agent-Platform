import re

from app.api.dependencies import SettingsDependency
from app.core.config import AppSettings
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

_HEX_32 = re.compile(r"\A[0-9a-f]{32}\Z")


def _make_app(**overrides: object) -> FastAPI:
    from app.main import create_api_app

    params: dict[str, object] = {"environment": "test"}
    params.update(overrides)
    if params["environment"] in {"staging", "production"}:
        params.setdefault("rag_completion_api_key", SecretStr("synthetic-rag-key"))
        params.setdefault("rag_input_price_per_million", "1")
        params.setdefault("rag_output_price_per_million", "2")
        params.setdefault("csrf_trusted_origins", ("https://app.example.invalid",))
    settings = AppSettings(**params)  # type: ignore[arg-type]
    return create_api_app(settings)


def test_factory_applies_injected_metadata() -> None:
    app = _make_app()

    assert app.title == "Nordic Regulated AI Agent Platform API"
    assert app.version == "0.0.0"
    assert app.description
    assert app.state.request_id_header == "X-Request-ID"


def test_docs_can_be_disabled_per_application() -> None:
    enabled = _make_app(enable_docs=True)
    disabled = _make_app(enable_docs=False)

    assert enabled.openapi_url == "/openapi.json"
    assert disabled.openapi_url is None

    with TestClient(disabled) as client:
        assert client.get("/openapi.json").status_code == 404
        assert client.get("/docs").status_code == 404
        assert client.get("/redoc").status_code == 404


def test_injected_settings_do_not_leak_between_apps() -> None:
    app_a = _make_app(environment="staging")
    app_b = _make_app(environment="production")

    settings_value = {"a": "", "b": ""}

    @app_a.get("/__test__/env")
    async def _env_a(settings: SettingsDependency) -> dict[str, str]:
        settings_value["a"] = settings.environment
        return {"environment": settings.environment}

    @app_b.get("/__test__/env")
    async def _env_b(settings: SettingsDependency) -> dict[str, str]:
        settings_value["b"] = settings.environment
        return {"environment": settings.environment}

    with TestClient(app_a) as client_a:
        assert client_a.get("/__test__/env").json() == {"environment": "staging"}
    with TestClient(app_b) as client_b:
        assert client_b.get("/__test__/env").json() == {"environment": "production"}


def test_request_id_is_generated_when_absent() -> None:
    app = _make_app()
    with TestClient(app) as client:
        response = client.get("/health/live")

    request_id = response.headers.get("X-Request-ID")
    assert request_id is not None
    assert _HEX_32.match(request_id)


def test_valid_request_id_is_propagated() -> None:
    app = _make_app()
    with TestClient(app) as client:
        response = client.get("/health/live", headers={"X-Request-ID": "trace-001"})

    assert response.headers.get("X-Request-ID") == "trace-001"


def test_malformed_request_id_is_replaced() -> None:
    app = _make_app()
    with TestClient(app) as client:
        response = client.get("/health/live", headers={"X-Request-ID": "bad id with spaces"})

    returned = response.headers.get("X-Request-ID")
    assert returned is not None
    assert returned != "bad id with spaces"
    assert _HEX_32.match(returned)


def test_request_id_header_name_is_configurable() -> None:
    app = _make_app(request_id_header="X-Correlation-ID")
    with TestClient(app) as client:
        response = client.get("/health/live")

    assert response.headers.get("X-Correlation-ID") is not None
    assert "X-Request-ID" not in response.headers
