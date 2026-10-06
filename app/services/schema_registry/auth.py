"""Resolve Schema Registry HTTP auth from a connection config."""

AUTH_NONE = "none"
AUTH_BASIC = "basic"
AUTH_BEARER = "bearer"
AUTH_TYPES = (AUTH_NONE, AUTH_BASIC, AUTH_BEARER)
AUTH_CREDENTIAL_KEYS = ("username", "password", "token", "bearer_token")


def resolve_auth_type(config: dict | None) -> str:
    cfg = config or {}
    raw = str(cfg.get("auth_type") or "").strip().lower()
    if raw in AUTH_TYPES:
        return raw
    if cfg.get("token") or cfg.get("bearer_token"):
        return AUTH_BEARER
    if cfg.get("username") and cfg.get("password"):
        return AUTH_BASIC
    return AUTH_NONE


def apply_auth_type(config: dict) -> dict:
    """Keep credentials for the selected auth type only."""
    out = dict(config or {})
    auth = resolve_auth_type(out)
    out["auth_type"] = auth
    if auth == AUTH_NONE:
        for key in AUTH_CREDENTIAL_KEYS:
            out.pop(key, None)
    elif auth == AUTH_BASIC:
        out.pop("token", None)
        out.pop("bearer_token", None)
    elif auth == AUTH_BEARER:
        out.pop("username", None)
        out.pop("password", None)
    return out
