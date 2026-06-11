"""
API to MCP — Turn REST API endpoints into MCP tools.

Web UI: /ui (configure & test endpoints)
MCP:    /mcp (Streamable HTTP transport)
"""

import json
import sys
import asyncio
from pathlib import Path

import yaml
from starlette.requests import Request
from starlette.responses import JSONResponse, FileResponse

from fastmcp import FastMCP

from server.loader import load_config, save_config, build_tools
from server.http_client import make_request
from server.tokens import verify_admin, validate_token, list_tokens, create_token, delete_token, toggle_token, register_session
from server.auth_middleware import AuthMiddleware

# ── Globals ────────────────────────────────────────────────────────

# MCP server (module-level so we can hot-reload tools)
_mcp = FastMCP(
    name="API-to-MCP",
    instructions="Dynamically exposes REST API endpoints as MCP tools. Configure via /ui.",
    version="0.1.0",
)


async def _reload_tools():
    """Replace all current tools with freshly built ones from config."""
    existing = await _mcp.list_tools()
    for t in existing:
        try:
            await _mcp.remove_tool(t.name)
        except Exception:
            pass
    new_tools = build_tools()
    for t in new_tools:
        _mcp.add_tool(t)


# ── Web UI ─────────────────────────────────────────────────────────

UI_DIR = Path(__file__).parent / "ui"


@_mcp.custom_route("/ui", methods=["GET"])
async def serve_ui(request: Request):
    return FileResponse(UI_DIR / "index.html")


@_mcp.custom_route("/ui/<path:path>", methods=["GET"])
async def serve_ui_static(request: Request):
    path = request.path_params["path"]
    file_path = UI_DIR / path
    if file_path.is_file():
        return FileResponse(file_path)
    return FileResponse(UI_DIR / "index.html")


# ── /cfg — Token management page ───────────────────────────────────

@_mcp.custom_route("/cfg", methods=["GET"])
async def serve_cfg(request: Request):
    return FileResponse(UI_DIR / "cfg.html")


# ── Token API (for /cfg page) ──────────────────────────────────────

@_mcp.custom_route("/api/tokens/login", methods=["POST"])
async def token_login(request: Request):
    data = await request.json()
    if verify_admin(data.get("username", ""), data.get("password", "")):
        import secrets
        session_id = secrets.token_hex(16)
        register_session(session_id)
        return JSONResponse({"status": "ok", "session_id": session_id})
    return JSONResponse({"error": "Invalid credentials"}, status_code=401)


@_mcp.custom_route("/api/tokens/list", methods=["GET"])
async def token_list(request: Request):
    # Mask token values for list view
    tokens = list_tokens()
    for t in tokens:
        t["masked_token"] = (
            t["token"][:8] + "..." + t["token"][-4:]
        )
    return JSONResponse({"tokens": tokens})


@_mcp.custom_route("/api/tokens/create", methods=["POST"])
async def token_create(request: Request):
    data = await request.json()
    token_info = create_token(data.get("name", ""))
    return JSONResponse(token_info)


@_mcp.custom_route("/api/tokens/delete", methods=["POST"])
async def token_delete(request: Request):
    data = await request.json()
    found = delete_token(data.get("token_id", ""))
    if found:
        return JSONResponse({"status": "ok"})
    return JSONResponse({"error": "Token not found"}, status_code=404)


@_mcp.custom_route("/api/tokens/toggle", methods=["POST"])
async def token_toggle(request: Request):
    data = await request.json()
    found = toggle_token(data.get("token_id", ""), data.get("active", True))
    if found:
        return JSONResponse({"status": "ok"})
    return JSONResponse({"error": "Token not found"}, status_code=404)


# ── Admin API (for Web UI) ─────────────────────────────────────────


@_mcp.custom_route("/api/config", methods=["GET"])
async def get_config(request: Request):
    config = load_config()
    return JSONResponse(config)


@_mcp.custom_route("/api/config", methods=["POST"])
async def set_config(request: Request):
    body = await request.json()
    save_config(body)
    await _reload_tools()
    return JSONResponse({"status": "ok", "message": "Config saved & tools reloaded"})


@_mcp.custom_route("/api/test", methods=["POST"])
async def test_endpoint(request: Request):
    """Test an API endpoint without saving it."""
    data = await request.json()
    result = await make_request(
        base_url=data.get("base_url", ""),
        method=data.get("method", "GET"),
        path=data.get("path", "/"),
        headers=data.get("headers"),
        body=data.get("body"),
        timeout=float(data.get("timeout", 30)),
    )
    return JSONResponse(result)


@_mcp.custom_route("/api/tools", methods=["GET"])
async def list_tools(request: Request):
    """List currently registered MCP tools."""
    tools = await _mcp.list_tools()
    out = []
    for t in tools:
        out.append({
            "name": t.name,
            "description": t.description or "",
        })
    return JSONResponse({"tools": out, "count": len(out)})


@_mcp.custom_route("/api/health", methods=["GET"])
async def health(request: Request):
    tools = await _mcp.list_tools()
    host = request.headers.get("host", "localhost:9999")
    scheme = request.headers.get("x-forwarded-proto", "http")
    base = f"{scheme}://{host}"
    return JSONResponse({
        "status": "ok",
        "tools_count": len(tools),
        "mcp_endpoint": f"{base}/mcp",
        "server_url": base,
    })


# ── Entrypoint ─────────────────────────────────────────────────────


async def _main():
    host = "0.0.0.0"
    port = 8000

    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--port" and i + 1 < len(sys.argv):
            port = int(sys.argv[i + 1]); i += 1
        elif arg.startswith("--port="):
            port = int(arg.split("=")[1])
        elif arg == "--host" and i + 1 < len(sys.argv):
            host = sys.argv[i + 1]; i += 1
        elif arg.startswith("--host="):
            host = arg.split("=")[1]
        i += 1

    # Initial tool load
    await _reload_tools()

    print(f"  Web UI : http://localhost:{port}/ui")
    print(f"  MCP    : http://localhost:{port}/mcp (requires Bearer token)")
    print(f"  Config : http://localhost:{port}/cfg (admin: admin / alta_2025)")
    print(f"  Health : http://localhost:{port}/api/health")
    print(f"  Tools  : {len(await _mcp.list_tools())} registered")
    print()

    # Wrap with auth middleware — protects /mcp with Bearer token validation
    from starlette.middleware import Middleware
    await _mcp.run_async(
        transport="streamable-http",
        host=host,
        port=port,
        middleware=[Middleware(AuthMiddleware)],
    )


def main():
    asyncio.run(_main())


if __name__ == "__main__":
    main()
