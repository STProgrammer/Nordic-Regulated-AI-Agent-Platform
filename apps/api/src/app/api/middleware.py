"""Request-correlation middleware for the API application.

This pure-ASGI middleware assigns a safe correlation id to every HTTP request,
binds it to the structured-logging context, exposes it on ``request.state`` for
dependencies and error handlers, returns it on a response header, and emits one
safe request-completion log event. It deliberately logs only allowlisted metadata
(method, route template, status, duration) and never request bodies, headers,
query values, or exception text.
"""

from time import perf_counter

from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging import (
    bind_request_context,
    clear_request_context,
    get_logger,
    normalize_request_id,
)

_INCOMPLETE_RESPONSE_STATUS = 500


class RequestContextMiddleware:
    """Bind a correlation id to each request and log its safe completion summary."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        header_name: str,
        max_request_id_length: int,
    ) -> None:
        self.app = app
        self.header_name = header_name
        self.max_request_id_length = max_request_id_length
        self._logger = get_logger("api.request")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        request_id = normalize_request_id(
            request.headers.get(self.header_name),
            max_length=self.max_request_id_length,
        )
        scope.setdefault("state", {})["request_id"] = request_id

        clear_request_context()
        bind_request_context(request_id=request_id)

        status_code = _INCOMPLETE_RESPONSE_STATUS
        started_at = perf_counter()

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                headers = MutableHeaders(scope=message)
                headers[self.header_name] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            duration_ms = round((perf_counter() - started_at) * 1000, 3)
            route = scope.get("route")
            path = getattr(route, "path", request.url.path)
            self._logger.info(
                "request.completed",
                method=request.method,
                path=path,
                status=status_code,
                duration_ms=duration_ms,
            )
            clear_request_context()
