from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.core.config import AppSettings
from app.main import create_api_app
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

_TRUSTED_ORIGIN = "https://app.example.invalid"


def _app(**overrides: object) -> FastAPI:
    params: dict[str, object] = {
        "environment": "test",
        "csrf_trusted_origins": (_TRUSTED_ORIGIN,),
    }
    params.update(overrides)
    app = create_api_app(AppSettings(**params))  # type: ignore[arg-type]

    @app.post("/api/__test__/mutate")
    async def mutate() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/api/__test__/boom")
    async def boom() -> dict[str, bool]:
        raise RuntimeError("synthetic failure")

    return app


def _assert_security_headers(response: Any) -> None:
    headers = response.headers
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["Referrer-Policy"] == "no-referrer"
    assert headers["Cache-Control"] == "no-store"
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]


def test_headers_apply_to_normal_and_error_api_responses() -> None:
    with TestClient(_app(), raise_server_exceptions=False) as client:
        normal = client.get("/api/__test__/boom")

    assert normal.status_code == 500
    assert normal.headers["X-Request-ID"] == normal.json()["error"]["request_id"]
    _assert_security_headers(normal)


def test_csrf_rejects_missing_or_untrusted_origin_and_allows_exact_origin() -> None:
    with TestClient(_app()) as client:
        client.cookies.set("nordic_session", "synthetic-session")
        missing = client.post("/api/__test__/mutate")
        blocked = client.post("/api/__test__/mutate", headers={"Origin": "https://evil.invalid"})
        accepted = client.post("/api/__test__/mutate", headers={"Origin": _TRUSTED_ORIGIN})

    assert missing.status_code == 403
    assert blocked.status_code == 403
    assert missing.json()["error"]["code"] == "csrf_origin_invalid"
    assert blocked.json()["error"]["request_id"] == blocked.headers["X-Request-ID"]
    _assert_security_headers(blocked)
    assert accepted.status_code == 200


def test_login_is_exempt_from_ambient_session_csrf_check() -> None:
    with TestClient(_app()) as client:
        client.cookies.set("nordic_session", "synthetic-session")
        response = client.post(
            "/api/auth/login",
            json={"email": "user@demo.invalid", "password": "synthetic password"},
        )

    assert response.status_code != 403
    assert response.json()["error"]["code"] == "authentication_unavailable"


def test_cors_preflight_uses_only_configured_origin_and_keeps_security_headers() -> None:
    app = _app(cors_allowed_origins=(_TRUSTED_ORIGIN,))
    with TestClient(app) as client:
        allowed = client.options(
            "/api/__test__/mutate",
            headers={
                "Origin": _TRUSTED_ORIGIN,
                "Access-Control-Request-Method": "POST",
            },
        )
        blocked = client.options(
            "/api/__test__/mutate",
            headers={
                "Origin": "https://evil.invalid",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == _TRUSTED_ORIGIN
    _assert_security_headers(allowed)
    assert blocked.status_code == 400
    assert "access-control-allow-origin" not in blocked.headers


def test_deployed_apps_disable_docs_by_default_and_emit_hsts() -> None:
    settings = AppSettings(
        environment="production",
        csrf_trusted_origins=(_TRUSTED_ORIGIN,),
        rag_completion_api_key=SecretStr("synthetic-rag-key"),
        rag_input_price_per_million=Decimal("1"),
        rag_output_price_per_million=Decimal("2"),
    )
    app = create_api_app(settings)
    with TestClient(app) as client:
        health = client.get("/health/live")
        docs = client.get("/docs")

    assert health.headers["Strict-Transport-Security"].startswith("max-age=")
    assert docs.status_code == 404


def test_oversized_upload_is_rejected_before_route_dependencies() -> None:
    app = _app(
        document_upload_max_bytes=1,
        document_parser_max_input_bytes=1,
        document_upload_multipart_overhead_bytes=1_024,
    )
    with TestClient(app) as client:
        response = client.post("/api/documents/upload", content=b"x" * 1_026)

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"
    _assert_security_headers(response)
