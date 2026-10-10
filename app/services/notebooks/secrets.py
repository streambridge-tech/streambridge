from __future__ import annotations

import re

from app.utils.vaults import TOKEN_RE, resolve_internal, vaults_map

_SECRET_KEY = re.compile(r"(password|secret|token|credentials)", re.I)


class SecretResolver:
    """Walk connector JSON and substitute `{vault.key}` from stored vaults."""

    def __init__(self, vault_rows):
        self._vaults = vaults_map(vault_rows)

    def resolve_config(self, config: dict) -> tuple[dict, list[str], int]:
        """Substitute tokens inside string values only, so a secret is never parsed as JSON."""
        config = config or {}
        if not isinstance(config, dict):
            raise ValueError("Connector config must be an object")
        missing: list[str] = []
        refs = 0

        def walk(value):
            nonlocal refs
            if isinstance(value, str):
                refs += len(TOKEN_RE.findall(value))
                text, gone = resolve_internal(value, self._vaults)
                missing.extend(gone)
                return text
            if isinstance(value, dict):
                return {key: walk(item) for key, item in value.items()}
            if isinstance(value, list):
                return [walk(item) for item in value]
            return value

        return walk(config), missing, refs

    def redact_config(self, config: dict) -> dict:
        out = {}
        for key, value in (config or {}).items():
            if _SECRET_KEY.search(str(key)):
                out[key] = "••••••••"
            else:
                out[key] = value
        return out
