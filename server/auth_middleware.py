"""ASGI middleware that validates Bearer tokens on /mcp paths."""

from starlette.requests import Request
from starlette.responses import JSONResponse

from .tokens import validate_token


class AuthMiddleware:
    """Starlette ASGI middleware that protects /mcp paths with Bearer token auth."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if not path.startswith("/mcp"):
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        auth_header = request.headers.get("authorization", "")

        if not auth_header.startswith("Bearer "):
            response = JSONResponse(
                {"error": "Invalid or missing token"}, status_code=401
            )
            await response(scope, receive, send)
            return

        token_str = auth_header[len("Bearer "):]
        if not validate_token(token_str):
            response = JSONResponse(
                {"error": "Invalid or missing token"}, status_code=401
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
