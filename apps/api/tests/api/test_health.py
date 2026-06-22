from collections.abc import Callable

import pytest
from app.health import get_health_probes
from app.main import create_api_app
from app.workers.readiness import create_worker_app
from fastapi import FastAPI
from fastapi.testclient import TestClient

AppFactory = Callable[[], FastAPI]


class FixedProbes:
    def __init__(
        self, postgres: bool = True, redis: bool = True, object_storage: bool = True
    ) -> None:
        self._postgres = postgres
        self._redis = redis
        self._object_storage = object_storage

    async def postgres(self) -> bool:
        return self._postgres

    async def redis(self) -> bool:
        return self._redis

    async def object_storage(self) -> bool:
        return self._object_storage


class FailingPostgresProbes(FixedProbes):
    async def postgres(self) -> bool:
        raise RuntimeError(
            "postgresql://nordic_local:local-postgres-password-not-for-production@postgres"
        )


@pytest.mark.parametrize(
    "app_factory",
    [create_api_app, create_worker_app],
    ids=["api", "worker"],
)
def test_liveness_is_dependency_free(app_factory: AppFactory) -> None:
    app = app_factory()

    with TestClient(app) as client:
        response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


@pytest.mark.parametrize(
    "app_factory",
    [create_api_app, create_worker_app],
    ids=["api", "worker"],
)
def test_readiness_reports_all_available_dependencies(app_factory: AppFactory) -> None:
    app = app_factory()
    app.dependency_overrides[get_health_probes] = lambda: FixedProbes()

    with TestClient(app) as client:
        response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "dependencies": [
            {"name": "postgres", "status": "ready"},
            {"name": "redis", "status": "ready"},
            {"name": "object_storage", "status": "ready"},
        ],
    }


def test_readiness_uses_503_and_safe_failure_summary() -> None:
    app = create_api_app()
    app.dependency_overrides[get_health_probes] = lambda: FailingPostgresProbes()

    with TestClient(app) as client:
        response = client.get("/health/ready")

    body = response.json()
    serialized_body = response.text
    assert response.status_code == 503
    assert body == {
        "status": "unavailable",
        "dependencies": [
            {"name": "postgres", "status": "unavailable"},
            {"name": "redis", "status": "ready"},
            {"name": "object_storage", "status": "ready"},
        ],
    }
    assert "local-postgres-password-not-for-production" not in serialized_body
    assert "postgresql://" not in serialized_body
    assert "RuntimeError" not in serialized_body


def test_readiness_marks_each_unavailable_dependency_without_error_details() -> None:
    app = create_worker_app()
    app.dependency_overrides[get_health_probes] = lambda: FixedProbes(
        redis=False, object_storage=False
    )

    with TestClient(app) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["dependencies"] == [
        {"name": "postgres", "status": "ready"},
        {"name": "redis", "status": "unavailable"},
        {"name": "object_storage", "status": "unavailable"},
    ]
