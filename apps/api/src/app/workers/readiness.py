"""Phase 2 worker process: readiness endpoints only, with no task execution."""

from fastapi import FastAPI

from app.health import create_health_router


def create_worker_app() -> FastAPI:
    """Create the worker's equivalent health contract without defining any jobs."""

    app = FastAPI(title="Phase 2 worker readiness")
    app.include_router(create_health_router())
    return app


app = create_worker_app()
