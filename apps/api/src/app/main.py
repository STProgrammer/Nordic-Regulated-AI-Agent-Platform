"""Phase 3 backend API skeleton.

This module builds the durable FastAPI application: structured configuration,
safe structured logging, request correlation, a consistent error contract, local
OpenAPI documentation, and the stable product route boundaries. It deliberately
implements no persistence, authentication, business operations, or AI workflows;
those arrive in later roadmap phases. Only the health endpoints are functional.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.middleware import RequestContextMiddleware
from app.api.router import create_api_router, openapi_tags
from app.core.config import AppSettings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.health import create_health_router

API_DESCRIPTION = (
    "Backend API skeleton for the Nordic Regulated AI Agent Platform (Phase 3). "
    "Only the health endpoints are functional. The product route groups are stable "
    "API boundaries whose operations are delivered by later roadmap phases. No "
    "authentication, persistence, or AI capabilities are implemented yet."
)


def create_api_app(settings: AppSettings | None = None) -> FastAPI:
    """Create the configurable API application.

    Tests may inject an :class:`AppSettings` instance to exercise alternative
    configuration without mutating process environment variables. Production
    construction reads configuration lazily from the environment.
    """

    resolved_settings = settings if settings is not None else get_settings()
    configure_logging(resolved_settings)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        logger = get_logger("api.lifespan")
        logger.info("api.startup", environment=resolved_settings.environment)
        try:
            yield
        finally:
            logger.info("api.shutdown", environment=resolved_settings.environment)

    app = FastAPI(
        title=resolved_settings.api_title,
        version=resolved_settings.release,
        description=API_DESCRIPTION,
        lifespan=lifespan,
        openapi_url=resolved_settings.openapi_url,
        docs_url=resolved_settings.docs_url,
        redoc_url=resolved_settings.redoc_url,
        openapi_tags=openapi_tags(),
    )
    app.state.request_id_header = resolved_settings.request_id_header

    # When settings are injected, route-handler dependencies must see the same
    # configuration rather than re-reading the environment.
    if settings is not None:
        app.dependency_overrides[get_settings] = lambda: resolved_settings

    app.add_middleware(
        RequestContextMiddleware,
        header_name=resolved_settings.request_id_header,
        max_request_id_length=resolved_settings.request_id_max_length,
    )
    register_exception_handlers(app)

    app.include_router(create_health_router())
    app.include_router(create_api_router(resolved_settings.api_prefix))

    return app


app = create_api_app()
