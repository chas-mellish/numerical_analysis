"""ASGI middleware: request-body size limit and security headers."""

import json

from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from gerald_na.web.api import error_body

__all__ = ["MAX_BODY_BYTES", "BodySizeLimitMiddleware", "SecurityHeadersMiddleware"]

MAX_BODY_BYTES = 64 * 1024
"""Largest accepted request body. A run form or API request is a few hundred bytes."""

CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        # Plotly injects <style> elements and inline style attributes while drawing.
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data:",
        "object-src 'self'",
        "frame-src 'self'",
        "frame-ancestors 'self'",
        "base-uri 'self'",
        "form-action 'self'",
    ]
)


TOO_LARGE_MESSAGE = "request body too large"


class BodySizeLimitMiddleware:
    """Reject request bodies above ``max_bytes`` with 413 (Content-Length or streamed size).

    A declared Content-Length is rejected here, before the app runs; ``/api`` paths get the
    JSON error body (code ``TOO_LARGE``). A streamed body that grows past the limit raises
    :class:`HTTPException` (413) from ``receive``, which FastAPI re-raises so the app's own
    handler renders it like any other HTTP error.
    """

    def __init__(self, app: ASGIApp, max_bytes: int = MAX_BODY_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        for name, value in scope.get("headers", []):
            if name == b"content-length":
                try:
                    declared = int(value)
                except ValueError:
                    declared = self.max_bytes + 1
                if declared > self.max_bytes:
                    await self._reject(scope, send)
                    return
        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise HTTPException(413, TOO_LARGE_MESSAGE)
            return message

        await self.app(scope, limited_receive, send)

    async def _reject(self, scope: Scope, send: Send) -> None:
        path = scope.get("path", "")
        if path == "/api" or path.startswith("/api/"):
            body = json.dumps(error_body("TOO_LARGE", TOO_LARGE_MESSAGE)).encode()
            content_type = b"application/json"
        else:
            body = TOO_LARGE_MESSAGE.encode()
            content_type = b"text/plain; charset=utf-8"
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", content_type),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


class SecurityHeadersMiddleware:
    """Add ``nosniff``, a referrer policy, frame protection and a strict CSP to responses."""

    HEADERS: tuple[tuple[bytes, bytes], ...] = (
        (b"x-content-type-options", b"nosniff"),
        (b"referrer-policy", b"same-origin"),
        (b"x-frame-options", b"SAMEORIGIN"),
        (b"content-security-policy", CONTENT_SECURITY_POLICY.encode()),
    )

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                present = {name.lower() for name, _ in headers}
                headers.extend(item for item in self.HEADERS if item[0] not in present)
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)
