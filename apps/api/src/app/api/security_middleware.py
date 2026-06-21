"""Transport-level security controls shared by the FastAPI application."""

from __future__ import annotations

import http

from fastapi import Request
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import error_response
from app.services.errors import PayloadTooLargeError

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), geolocation=(), microphone=(), payment=(), usb=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
}
_API_CONTENT_SECURITY_POLICY = (
    "default-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
)
_HSTS_VALUE = "max-age=63072000; includeSubDomains"


class SecurityHeadersMiddleware:
    """Attach conservative headers to normal, error, and preflight responses."""

    def __init__(self, app: ASGIApp, *, environment: str, api_prefix: str) -> None:
        self.app = app
        self.environment = environment
        self.api_prefix = api_prefix

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")

        async def send_with_security_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in _SECURITY_HEADERS.items():
                    headers.setdefault(name, value)
                if path.startswith(self.api_prefix):
                    headers.setdefault("Cache-Control", "no-store")
                    headers.setdefault("Content-Security-Policy", _API_CONTENT_SECURITY_POLICY)
                if self.environment in {"staging", "production"}:
                    headers.setdefault("Strict-Transport-Security", _HSTS_VALUE)
            await send(message)

        await self.app(scope, receive, send_with_security_headers)


class CsrfOriginMiddleware:
    """Require an exact configured Origin for unsafe cookie-authenticated API calls."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        api_prefix: str,
        cookie_name: str,
        trusted_origins: tuple[str, ...],
    ) -> None:
        self.app = app
        self.api_prefix = api_prefix
        self.cookie_name = cookie_name
        self.trusted_origins = frozenset(trusted_origins)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or not self.trusted_origins
            or scope.get("method") in _SAFE_METHODS
            or not scope.get("path", "").startswith(self.api_prefix)
        ):
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        if (
            self.cookie_name not in request.cookies
            or request.url.path == f"{self.api_prefix}/auth/login"
        ):
            await self.app(scope, receive, send)
            return

        origin = request.headers.get("origin")
        if origin not in self.trusted_origins:
            response = error_response(
                request=request,
                status_code=http.HTTPStatus.FORBIDDEN,
                code="csrf_origin_invalid",
                message="The request origin is not allowed.",
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


class UploadRequestBodyLimitMiddleware:
    """Reject oversized upload bodies before multipart parsing reaches application services."""

    def __init__(self, app: ASGIApp, *, path: str, maximum_bytes: int) -> None:
        self.app = app
        self.path = path
        self.maximum_bytes = maximum_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope.get("method") != "POST"
            or scope.get("path") != self.path
        ):
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > self.maximum_bytes:
                    await self._send_too_large(request, scope, receive, send)
                    return
            except ValueError:
                # Let Starlette retain ownership of malformed transport handling.
                pass

        received_bytes = 0

        async def limited_receive() -> Message:
            nonlocal received_bytes
            message = await receive()
            if message["type"] == "http.request":
                body = message.get("body", b"")
                if isinstance(body, bytes):
                    received_bytes += len(body)
                if received_bytes > self.maximum_bytes:
                    raise PayloadTooLargeError()
            return message

        await self.app(scope, limited_receive, send)

    @staticmethod
    async def _send_too_large(
        request: Request,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        response = error_response(
            request=request,
            status_code=http.HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            code="payload_too_large",
            message="The document payload is too large.",
        )
        await response(scope, receive, send)
