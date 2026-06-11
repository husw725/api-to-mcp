"""Token management: generation, validation, usage tracking."""

import json
import uuid
from pathlib import Path
from datetime import datetime, timezone

TOKENS_PATH=Path(__file__).parent.parent / "tokens.json"

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD="alta_2025"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load() -> dict:
    if TOKENS_PATH.exists():
        try:
            return json.loads(TOKENS_PATH.read_text())
        except Exception:
            pass
    return {"tokens": []}


def _save(data: dict):
    TOKENS_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def verify_admin(username: str, password: str) -> bool:
    """Check admin credentials."""
    return (username == ADMIN_USERNAME and password == ADMIN_PASSWORD)


def validate_token(token_str: str) -> bool:
    """Check if token is valid and active. Records usage."""
    data = _load()
    for t in data["tokens"]:
        if t["token"] == token_str:
            if not t.get("active", True):
                return False
            t["last_used_at"] = _now()
            t["usage_count"] = t.get("usage_count", 0) + 1
            _save(data)
            return True
    return False


def list_tokens() -> list[dict]:
    """Return all tokens with stats."""
    data = _load()
    return data.get("tokens", [])


def create_token(name: str = "") -> dict:
    """Create new token, returns token info including the secret."""
    data = _load()
    token_value = f"sk-{uuid.uuid4().hex}"
    count = len(data["tokens"])
    token_info = {
        "id": uuid.uuid4().hex[:12],
        "token": token_value,
        "name": name or f"token-{count + 1}",
        "created_at": _now(),
        "last_used_at": None,
        "usage_count": 0,
        "active": True,
    }
    data["tokens"].append(token_info)
    _save(data)
    return token_info


def delete_token(token_id: str) -> bool:
    """Delete token by ID. Returns True if found."""
    data = _load()
    old = len(data["tokens"])
    data["tokens"] = [t for t in data["tokens"] if t["id"] != token_id]
    if len(data["tokens"]) < old:
        _save(data)
        return True
    return False


def toggle_token(token_id: str, active: bool) -> bool:
    """Toggle token active/inactive. Returns True if found."""
    data = _load()
    for t in data["tokens"]:
        if t["id"] == token_id:
            t["active"] = active
            _save(data)
            return True
    return False


def get_token(token_id: str) -> dict | None:
    """Get single token by ID."""
    for t in list_tokens():
        if t["id"] == token_id:
            return t
    return None
