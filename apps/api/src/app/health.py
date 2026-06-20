"""Small, safe health contracts for the local Phase 2 runtime."""

import asyncio
import os
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

DependencyName = Literal["postgres", "redis", "azurite"]
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

    async def azurite(self) -> bool: ...


@dataclass(frozen=True)
class RuntimeHealthProbes:
    """Short-timeout local probes configured only through individual environment values."""

    postgres_host: str
    postgres_port: int
    postgres_database: str
    postgres_user: str
    postgres_password: str
    redis_host: str
    redis_port: int
    azurite_blob_url: str

    @classmethod
    def from_environment(cls) -> "RuntimeHealthProbes":
        return cls(
            postgres_host=os.getenv("POSTGRES_HOST", "postgres"),
            postgres_port=_environment_port("POSTGRES_PORT", 5432),
            postgres_database=os.getenv("POSTGRES_DB", "nordic_local"),
            postgres_user=os.getenv("POSTGRES_USER", "nordic_local"),
            postgres_password=os.getenv(
                "POSTGRES_PASSWORD", "local-postgres-password-not-for-production"
            ),
            redis_host=os.getenv("REDIS_HOST", "redis"),
            redis_port=_environment_port("REDIS_PORT", 6379),
            azurite_blob_url=os.getenv(
                "AZURITE_BLOB_HEALTH_URL", "http://azurite:10000/devstoreaccount1"
            ),
        )

    async def postgres(self) -> bool:
        connection = await asyncpg.connect(
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_database,
            user=self.postgres_user,
            password=self.postgres_password,
            timeout=PROBE_TIMEOUT_SECONDS,
        )
        try:
            value: object = await connection.fetchval("SELECT 1")
            return value == 1
        finally:
            await connection.close()

    async def redis(self) -> bool:
        client = Redis(
            host=self.redis_host,
            port=self.redis_port,
            socket_connect_timeout=PROBE_TIMEOUT_SECONDS,
            socket_timeout=PROBE_TIMEOUT_SECONDS,
        )
        try:
            return bool(await client.ping())
        finally:
            await client.aclose()

    async def azurite(self) -> bool:
        async with httpx2.AsyncClient(timeout=PROBE_TIMEOUT_SECONDS) as client:
            response = await client.get(self.azurite_blob_url)
        # Azurite exposes no unauthenticated health endpoint; any HTTP response below 500
        # (typically 400/403 for an unauthenticated blob request) confirms it is serving.
        return response.status_code < status.HTTP_500_INTERNAL_SERVER_ERROR


def get_health_probes() -> HealthProbes:
    """Build local probes at request time so tests can replace this dependency cleanly."""

    return RuntimeHealthProbes.from_environment()


def create_health_router() -> APIRouter:
    """Create only the Phase 2 liveness and readiness endpoints."""

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
            _probe_dependency("azurite", probes.azurite),
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


def _environment_port(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        port = int(value)
    except ValueError:
        return default
    return port if 1 <= port <= 65535 else default
