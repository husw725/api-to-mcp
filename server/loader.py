"""Load API config and dynamically build MCP tools from verified endpoints."""

import json
from pathlib import Path

import yaml

from fastmcp.tools import Tool

from .http_client import make_request

CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"

TYPE_MAP = {
    "string": "str", "str": "str",
    "integer": "int", "int": "int",
    "number": "float", "float": "float",
    "boolean": "bool", "bool": "bool",
}

DEFAULT_MAP = {
    "str": '""',
    "int": "0",
    "float": "0.0",
    "bool": "False",
}


def load_config() -> dict:
    """Read config.yaml, return services list."""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return yaml.safe_load(f) or {"services": []}
    return {"services": []}


def save_config(config: dict):
    """Write config back to config.yaml."""
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def build_tools() -> list[Tool]:
    """Build MCP tools from verified endpoints only."""
    config = load_config()
    tools = []

    for service in config.get("services", []):
        for endpoint in service.get("endpoints", []):
            if not endpoint.get("verified", False):
                continue

            handler = _build_handler(endpoint, service)
            tool = Tool.from_function(
                handler,
                name=endpoint["name"],
                description=endpoint.get("description", ""),
                timeout=endpoint.get("timeout", 30.0),
            )
            tools.append(tool)

    return tools


def _build_handler(endpoint: dict, service: dict):
    """Build an async handler with proper type annotations via exec.

    FastMCP requires typed parameters — **kwargs is not supported.
    So we generate the function code dynamically.
    """
    params = endpoint.get("parameters", [])
    func_name = f"_h_{endpoint['name']}"

    if not params:
        code = f"""async def {func_name}():
    result = await __mr(__bu, __me, __pa, __he)
    return json.dumps(result, ensure_ascii=False)
"""
    else:
        # Build typed arguments
        args = []
        for p in params:
            ptype = TYPE_MAP.get(p.get("type", "string"), "str")
            if not p.get("required", False):
                default = DEFAULT_MAP.get(ptype, '""')
                args.append(f"{p['name']}: {ptype} = {default}")
            else:
                args.append(f"{p['name']}: {ptype}")

        code = f"""async def {func_name}({', '.join(args)}):
    body = {{}}
    qp = {{}}
    for _n, _l in __pl.items():
        v = locals()[_n]
        if _l == "body":
            body[_n] = v
        elif _l == "query":
            qp[_n] = v
        elif _l == "path":
            body[_n] = v
    result = await __mr(__bu, __me, __pa, __he, params=qp, body=body)
    return json.dumps(result, ensure_ascii=False)
"""

    namespace = {
        "json": json,
        "__mr": make_request,
        "__bu": service["base_url"],
        "__me": endpoint["method"],
        "__pa": endpoint["path"],
        "__he": service.get("headers", {}),
        "__pl": {p["name"]: p.get("location", "body") for p in params},
    }

    exec(code, namespace)
    handler = namespace[func_name]
    handler.__doc__ = endpoint.get(
        "description", f"{endpoint['method']} {endpoint['path']}"
    )
    # Keep closure alive
    handler._mcp_closure = namespace

    return handler
