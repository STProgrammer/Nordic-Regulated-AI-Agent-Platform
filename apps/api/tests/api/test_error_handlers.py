import re

import pytest
from app.api.schemas.common import ErrorDetail
from app.core.config import AppSettings
from app.core.errors import ApiError
from app.main import create_api_app
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

_HEX_32 = re.compile(r"\A[0-9a-f]{32}\Z")

# A sentinel that simulates a secret/connection string leaking through an error.
SECRET_SENTINEL = "postgresql://user:super-secret-pw@db:5432/app"


class _Payload(BaseModel):
    name: str
    count: int


def _app_with_test_routes() -> FastAPI:
    app = create_api_app(AppSettings(environment="test"))

    @app.post("/__test__/validate")
    async def _validate(payload: _Payload) -> dict[str, bool]:
        return {"ok": True}

    @app.get("/__test__/api-error")
    async def _api_error() -> dict[str, bool]:
        raise ApiError(
            status_code=409,
            code="conflict",
            message="The resource is in a conflicting state.",
            details=[ErrorDetail(field="name", message="already taken")],
        )

    @app.get("/__test__/boom")
    async def _boom() -> dict[str, bool]:
        raise RuntimeError(SECRET_SENTINEL)

    return app


def test_api_error_uses_error_envelope() -> None:
    app = _app_with_test_routes()
    with TestClient(app) as client:
        response = client.get("/__test__/api-error")

    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "conflict"
    assert body["error"]["message"] == "The resource is in a conflicting state."
    assert body["error"]["details"] == [{"field": "name", "code": None, "message": "already taken"}]
    assert body["error"]["request_id"] == response.headers.get("X-Request-ID")


def test_validation_error_returns_safe_details() -> None:
    app = _app_with_test_routes()
    with TestClient(app) as client:
        response = client.post("/__test__/validate", json={"name": "ok", "count": SECRET_SENTINEL})

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["request_id"]
    fields = [detail["field"] for detail in body["error"]["details"]]
    assert "body.count" in fields
    # The submitted (potentially sensitive) input value must not be echoed back.
    assert SECRET_SENTINEL not in response.text


def test_unknown_route_returns_not_found_envelope() -> None:
    app = _app_with_test_routes()
    with TestClient(app) as client:
        response = client.get("/this/does/not/exist")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
    assert response.headers.get("X-Request-ID")


def test_method_not_allowed_returns_envelope() -> None:
    app = _app_with_test_routes()
    with TestClient(app) as client:
        response = client.post("/health/live")

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "method_not_allowed"


def test_unexpected_error_is_generic_and_safe() -> None:
    app = _app_with_test_routes()
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/__test__/boom")

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal_error"
    assert body["error"]["message"] == "An unexpected error occurred."

    request_id = response.headers.get("X-Request-ID")
    assert request_id is not None
    assert body["error"]["request_id"] == request_id
    assert _HEX_32.match(request_id)

    serialized = response.text
    assert SECRET_SENTINEL not in serialized
    assert "postgresql://" not in serialized
    assert "RuntimeError" not in serialized
    assert "Traceback" not in serialized


def test_request_logging_does_not_serialize_sensitive_input(
    capsys: pytest.CaptureFixture[str],
) -> None:
    app = _app_with_test_routes()
    with TestClient(app) as client:
        client.post("/__test__/validate", json={"name": SECRET_SENTINEL, "count": 1})

    captured = capsys.readouterr()
    assert SECRET_SENTINEL not in captured.out
    assert SECRET_SENTINEL not in captured.err
