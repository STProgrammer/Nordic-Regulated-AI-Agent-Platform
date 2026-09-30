"""Small, safe health contracts for the local Phase 2 runtime."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated, Literal, Protocol

import asyncpg  # type: ignore[import-untyped]
import httpx2
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from redis.asyncio import Redis
from starlette import status

from app.core.config import AppSettings, get_settings

DependencyName = Literal["postgres", "redis", "object_storage"]
DependencyState = Literal["ready", "unavailable"]
ReadinessState = Literal["ready", "unavailable"]
Probe = Callable[[], Awaitable[bool]]

PROBE_TIMEOUT_SECONDS = 2.0


class LivenessResponse(BaseModel):
    """A dependency-free indication that the HTTP process is running."""

    status: Literal["alive"]


class DependencyStatus(BaseModel):
    """A deliberately non-sensitive readiness status for one local dependency."""

    name: DependencyName
    status: DependencyState


class ReadinessResponse(BaseModel):
    """The stable public readiness response shared by API and worker processes."""

    status: ReadinessState
    dependencies: list[DependencyStatus]


class HealthProbes(Protocol):
    """The narrow dependency boundary that makes health behavior testable without Docker."""

    async def postgres(self) -> bool: ...

    async def redis(self) -> bool: ...

    async def object_storage(self) -> bool: ...


@dataclass(frozen=True)
class RuntimeHealthProbes:
    """Short-timeout probes configured through validated application settings."""

    postgres_dsn: str
    redis_dsn: str
    object_storage_health_url: str

    @classmethod
    def from_settings(cls, settings: AppSettings) -> "RuntimeHealthProbes":
        return cls(
            postgres_dsn=settings.database_async_url().replace(
                "postgresql+asyncpg://", "postgresql://", 1
            ),
            redis_dsn=settings.redis_async_url(),
            object_storage_health_url=settings.object_storage_health_url_value(),
        )

    async def postgres(self) -> bool:
        connection = await asyncpg.connect(self.postgres_dsn, timeout=PROBE_TIMEOUT_SECONDS)
        try:
            value: object = await connection.fetchval("SELECT 1")
            return value == 1
        finally:
            await connection.close()

    async def redis(self) -> bool:
        client = Redis.from_url(
            self.redis_dsn,
            socket_connect_timeout=PROBE_TIMEOUT_SECONDS,
            socket_timeout=PROBE_TIMEOUT_SECONDS,
        )
        try:
            return bool(await client.ping())
        finally:
            await client.aclose()

    async def object_storage(self) -> bool:
        async with httpx2.AsyncClient(timeout=PROBE_TIMEOUT_SECONDS) as client:
            response = await client.get(self.object_storage_health_url)
        # Blob services commonly return 400/403 to an unauthenticated root probe; any
        # response below 500 confirms that the configured private-storage endpoint is serving.
        return response.status_code < status.HTTP_500_INTERNAL_SERVER_ERROR


def get_health_probes(
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> HealthProbes:
    """Build probes at request time so tests can replace this dependency cleanly."""

    return RuntimeHealthProbes.from_settings(settings)


def build_health_router() -> APIRouter:
    """Build only the Phase 2 liveness and readiness endpoints."""

    router = APIRouter(prefix="/health", tags=["health"])

    @router.get("/live", response_model=LivenessResponse)
    async def liveness() -> LivenessResponse:
        return LivenessResponse(status="alive")

    @router.get(
        "/ready",
        response_model=ReadinessResponse,
        responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessResponse}},
    )
    async def readiness(
        probes: Annotated[HealthProbes, Depends(get_health_probes)],
    ) -> ReadinessResponse | JSONResponse:
        response = await collect_readiness(probes)
        if response.status == "ready":
            return response
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=response.model_dump(mode="json"),
        )

    return router


async def collect_readiness(probes: HealthProbes) -> ReadinessResponse:
    """Probe all dependencies concurrently and expose only stable dependency identifiers."""

    dependencies = list(
        await asyncio.gather(
            _probe_dependency("postgres", probes.postgres),
            _probe_dependency("redis", probes.redis),
            _probe_dependency("object_storage", probes.object_storage),
        )
    )
    readiness_status: ReadinessState = (
        "ready"
        if all(dependency.status == "ready" for dependency in dependencies)
        else "unavailable"
    )
    return ReadinessResponse(status=readiness_status, dependencies=dependencies)


async def _probe_dependency(name: DependencyName, probe: Probe) -> DependencyStatus:
    try:
        ready = await asyncio.wait_for(probe(), timeout=PROBE_TIMEOUT_SECONDS)
    except Exception:
        ready = False
    return DependencyStatus(name=name, status="ready" if ready else "unavailable")
