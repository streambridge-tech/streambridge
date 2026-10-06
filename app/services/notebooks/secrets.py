from __future__ import annotations

import json
import re

from app.utils.vaults import TOKEN_RE, resolve_internal, vaults_map

_SECRET_KEY = re.compile(r"(password|secret|token|credentials)", re.I)


class SecretResolver:
    """Walk connector JSON and substitute `{vault.key}` from stored vaults."""

    def __init__(self, vault_rows):
        self._vaults = vaults_map(vault_rows)

    def resolve_config(self, config: dict) -> tuple[dict, list[str], int]:
        raw = json.dumps(config or {})
        resolved_text, missing = resolve_internal(raw, self._vaults)
        refs = TOKEN_RE.findall(raw)
        try:
            resolved = json.loads(resolved_text)
        except json.JSONDecodeError:
            raise ValueError("Resolved secrets produced invalid JSON") from None
        if not isinstance(resolved, dict):
            raise ValueError("Connector config must be an object")
        return resolved, missing, len(refs)

    def redact_config(self, config: dict) -> dict:
        out = {}
        for key, value in (config or {}).items():
            if _SECRET_KEY.search(str(key)):
                out[key] = "••••••••"
            else:
                out[key] = value
        return out
