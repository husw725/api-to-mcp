"""Generic HTTP client for making requests to configured API endpoints."""

import httpx


async def make_request(
    base_url: str,
    method: str,
    path: str,
    headers: dict | None = None,
    params: dict | None = None,
    body: dict | None = None,
    timeout: float = 30.0,
) -> dict:
    """Make an HTTP request and return structured result.

    Returns dict with keys: status_code, body, error (if any).
    """
    # Resolve path parameters from body (e.g. {user_id} in path)
    url = base_url.rstrip("/") + path
    path_keys = [k for k in _extract_path_keys(path)]
    path_values = {}
    if body:
        for k in path_keys:
            if k in body:
                path_values[k] = body.pop(k)
    for k, v in path_values.items():
        url = url.replace(f"{{{k}}}", str(v))

    extra_headers = {"Content-Type": "application/json"} if body else {}
    all_headers = {**extra_headers}
    if headers:
        all_headers.update(headers)

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        try:
            if method.upper() == "GET":
                resp = await client.get(url, headers=all_headers, params=params or {})
            elif method.upper() == "POST":
                resp = await client.post(
                    url, headers=all_headers, json=body or {}, params=params or {}
                )
            elif method.upper() == "PUT":
                resp = await client.put(
                    url, headers=all_headers, json=body or {}, params=params or {}
                )
            elif method.upper() == "DELETE":
                resp = await client.delete(
                    url, headers=all_headers, params=params or {}
                )
            elif method.upper() == "PATCH":
                resp = await client.patch(
                    url, headers=all_headers, json=body or {}, params=params or {}
                )
            else:
                return {"error": f"Unsupported method: {method}"}

            # Try JSON, fallback to text
            try:
                body_content = resp.json()
            except Exception:
                body_content = resp.text

            return {
                "status_code": resp.status_code,
                "body": body_content,
                "headers": dict(resp.headers),
            }
        except httpx.TimeoutException:
            return {"error": f"Request timeout after {timeout}s"}
        except httpx.ConnectError as e:
            return {"error": f"Connection failed: {e}"}
        except httpx.HTTPStatusError as e:
            return {
                "status_code": e.response.status_code,
                "body": e.response.text,
                "error": f"HTTP {e.response.status_code}",
            }
        except Exception as e:
            return {"error": str(e)}


def _extract_path_keys(path: str) -> list[str]:
    """Extract {key} path parameters from a URL path."""
    import re
    return re.findall(r"\{(\w+)\}", path)
