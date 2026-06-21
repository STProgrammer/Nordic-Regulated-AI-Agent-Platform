"""Backend API application factory.

This module builds the durable FastAPI application: structured configuration,
safe structured logging, request correlation, a consistent error contract, local
OpenAPI documentation, and stable product route boundaries. Authentication,
organization-scoped user administration, and Case Management operations are
implemented; later product groups remain future-phase boundaries.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from starlette.middleware.cors import CORSMiddleware

from app.api.middleware import RequestContextMiddleware
from app.api.router import create_api_router, openapi_tags
from app.api.security_middleware import (
    CsrfOriginMiddleware,
    SecurityHeadersMiddleware,
    UploadRequestBodyLimitMiddleware,
)
from app.core.config import AppSettings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.observability import configure_observability, metrics_payload
from app.core.session_store import dispose_redis_clients
from app.db.session import dispose_database_engines
from app.health import create_health_router

API_DESCRIPTION = (
    "Backend API for the Nordic Regulated AI Agent Platform. Local password authentication, "
    "opaque server-side sessions, and organization-scoped administrator user/role management "
    "are available, along with protected case submission, lifecycle, archive, governed search, "
    "and direct source-grounded answer operations. Other product route groups remain stable "
    "future-phase boundaries."
)


def create_api_app(settings: AppSettings | None = None) -> FastAPI:
    """Create the configurable API application.

    Tests may inject an :class:`AppSettings` instance to exercise alternative
    configuration without mutating process environment variables. Production
    construction reads configuration lazily from the environment.
    """

    resolved_settings = settings if settings is not None else get_settings()
    configure_logging(resolved_settings)
    configure_observability(resolved_settings)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        logger = get_logger("api.lifespan")
        logger.info("api.startup", environment=resolved_settings.environment)
        try:
            yield
        finally:
            await dispose_redis_clients()
            await dispose_database_engines()
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
    app.state.environment = resolved_settings.environment
    app.state.api_prefix = resolved_settings.api_prefix

    # When settings are injected, route-handler dependencies must see the same
    # configuration rather than re-reading the environment.
    if settings is not None:
        app.dependency_overrides[get_settings] = lambda: resolved_settings

    register_exception_handlers(app)

    # Middleware is added inside-out. RequestContext is deliberately last so a
    # correlation id is available even when CSRF or body-size guards reject a
    # request before the router is reached.
    if resolved_settings.cors_allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(resolved_settings.cors_allowed_origins),
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Accept", "Accept-Language", "Content-Type", "X-Request-ID"],
            max_age=600,
        )
    app.add_middleware(
        UploadRequestBodyLimitMiddleware,
        path=f"{resolved_settings.api_prefix}/documents/upload",
        maximum_bytes=resolved_settings.document_upload_max_request_bytes,
    )
    app.add_middleware(
        CsrfOriginMiddleware,
        api_prefix=resolved_settings.api_prefix,
        cookie_name=resolved_settings.session_cookie_name,
        trusted_origins=resolved_settings.csrf_trusted_origins,
    )
    app.add_middleware(
        SecurityHeadersMiddleware,
        environment=resolved_settings.environment,
        api_prefix=resolved_settings.api_prefix,
    )
    app.add_middleware(
        RequestContextMiddleware,
        header_name=resolved_settings.request_id_header,
        max_request_id_length=resolved_settings.request_id_max_length,
    )

    if resolved_settings.metrics_enabled:

        @app.get("/metrics", include_in_schema=False)
        def metrics() -> Response:
            return Response(
                content=metrics_payload(),
                media_type="text/plain; version=0.0.4; charset=utf-8",
            )

    app.include_router(create_health_router())
    app.include_router(create_api_router(resolved_settings.api_prefix))

    return app


app = create_api_app()
