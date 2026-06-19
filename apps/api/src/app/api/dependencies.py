"""Typed FastAPI dependency providers shared across the API boundary.

These providers expose the application settings and the per-request correlation
context to route handlers in a way that tests can override cleanly. They perform
no database I/O, create no clients, and enforce no authentication; those concerns
are introduced by their owning roadmap phases.
"""

from typing import Annotated

from fastapi import Depends, Request

from app.core.config import AppSettings, get_settings


def get_request_id(request: Request) -> str | None:
    """Return the correlation id bound to the request by the context middleware."""

    request_id = getattr(request.state, "request_id", None)
    return request_id if isinstance(request_id, str) else None


SettingsDependency = Annotated[AppSettings, Depends(get_settings)]
RequestIdDependency = Annotated[str | None, Depends(get_request_id)]
