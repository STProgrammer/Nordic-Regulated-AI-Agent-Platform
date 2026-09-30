"""API-only metrics endpoint coverage with explicit observation generation."""

from app.core.config import AppSettings
from app.main import create_api_app
from fastapi.testclient import TestClient


def test_metrics_route_is_absent_when_not_enabled() -> None:
    with TestClient(create_api_app(AppSettings(environment="test"))) as client:
        assert client.get("/metrics").status_code == 404


def test_metrics_route_reports_a_triggered_api_observation() -> None:
    with TestClient(
        create_api_app(AppSettings(environment="test", metrics_enabled=True))
    ) as client:
        # The health call is the explicit trigger; startup alone must not be
        # expected to record a request observation.
        assert client.get("/health/live").status_code == 200
        response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "nordic_api_http_requests_total" in response.text
    assert 'route="/health/live"' in response.text
    assert 'status_class="2xx"' in response.text
    assert 'route="/metrics"' not in response.text
