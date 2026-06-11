"""ASGI middleware: three-tier auth for API-to-MCP."""

from starlette.requests import Request
from starlette.responses import JSONResponse

from .tokens import validate_token, is_valid_session

# Completely public — no auth at all
PUBLIC_PATHS = ("/cfg", "/api/tokens/login")

# Admin endpoints — protected by session (set via /api/tokens/login)
ADMIN_PREFIX = "/api/tokens/"

# Admin-managed paths — also protected by session
ADMIN_PATHS = ("/ui", "/api/config", "/api/test", "/api/tools", "/api/health")


class AuthMiddleware:
    """Three-tier auth:

    - /cfg, /api/tokens/login → open (login entry point)
    - /api/tokens/* → admin session (X-Session header)
    - /ui, /api/config, /api/test, /api/tools, /api/health → admin session (X-Session header)
    - /mcp → Bearer token
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")

        # Public paths
        if path in PUBLIC_PATHS:
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)

        # MCP — Bearer token
        if path.startswith("/mcp"):
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
            return

        # Admin managed — check session
        if path in ADMIN_PATHS or path.startswith(ADMIN_PREFIX):
            session_id = request.headers.get("x-session", "")
            if not session_id or not is_valid_session(session_id):
                response = JSONResponse(
                    {"error": "Admin session required"}, status_code=401
                )
                await response(scope, receive, send)
                return
            await self.app(scope, receive, send)
            return

        # Fallback — reject
        response = JSONResponse(
            {"error": "Unauthorized"}, status_code=401
        )
        await response(scope, receive, send)
