from app.api.router import ROUTE_GROUPS
from app.core.config import AppSettings
from app.main import create_api_app
from fastapi.testclient import TestClient


def _client() -> TestClient:
    return TestClient(create_api_app(AppSettings(environment="test")))


def test_openapi_schema_is_valid_and_honest() -> None:
    with _client() as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    assert schema["openapi"].startswith("3.")
    assert schema["info"]["title"] == "Nordic Regulated AI Agent Platform API"
    assert schema["info"]["version"] == "0.0.0"
    assert "authentication" in schema["info"]["description"].lower()


def test_openapi_documents_health_paths() -> None:
    with _client() as client:
        schema = client.get("/openapi.json").json()

    assert "/health/live" in schema["paths"]
    assert "/health/ready" in schema["paths"]


def test_openapi_declares_only_phase_six_product_endpoints() -> None:
    with _client() as client:
        schema = client.get("/openapi.json").json()

    product_paths = {path for path in schema["paths"] if path.startswith("/api/")}
    assert product_paths == {
        "/api/auth/login",
        "/api/auth/logout",
        "/api/auth/me",
        "/api/users",
        "/api/users/{user_id}",
        "/api/users/{user_id}/roles",
        "/api/roles",
    }


def test_openapi_lists_every_route_group_tag() -> None:
    with _client() as client:
        schema = client.get("/openapi.json").json()

    tag_names = {tag["name"] for tag in schema["tags"]}
    assert tag_names == {group.tag for group in ROUTE_GROUPS}


def test_openapi_declares_cookie_security_for_protected_operations() -> None:
    with _client() as client:
        schema = client.get("/openapi.json").json()

    components = schema.get("components", {})
    assert components["securitySchemes"]["SessionCookie"] == {
        "type": "apiKey",
        "in": "cookie",
        "name": "nordic_session",
        "description": "Opaque HTTP-only server-side session cookie.",
    }
    assert schema["paths"]["/api/auth/login"]["post"].get("security") is None
    assert schema["paths"]["/api/auth/me"]["get"]["security"] == [{"SessionCookie": []}]
    assert schema["paths"]["/api/users"]["get"]["security"] == [{"SessionCookie": []}]


def test_docs_and_redoc_render_locally() -> None:
    with _client() as client:
        docs = client.get("/docs")
        redoc = client.get("/redoc")

    assert docs.status_code == 200
    assert "text/html" in docs.headers["content-type"]
    assert redoc.status_code == 200
    assert "text/html" in redoc.headers["content-type"]
