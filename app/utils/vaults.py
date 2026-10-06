"""Vault variables: GitLab-style mask, `{vault.key}` tokens."""
import re

VAULT_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
VAR_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
TOKEN_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_-]*)\.([A-Za-z_][A-Za-z0-9_]*)\}")


def valid_vault_name(name: str) -> bool:
    return bool(name and VAULT_NAME_RE.match(name))


def valid_var_key(key: str) -> bool:
    return bool(key and VAR_KEY_RE.match(key))


def public_var(row: dict) -> dict:
    key = str(row.get("key") or "").strip()
    masked = bool(row.get("masked"))
    value = row.get("value") or ""
    out = {"key": key, "masked": masked, "hasValue": bool(value)}
    if not masked:
        out["value"] = value
    return out


def merge_vars(stored: list, incoming: list) -> tuple[list, str | None]:
    """Apply an editor payload onto stored rows. Masked values are write-only.

    Incoming row may send `value` to set/replace, or omit/blank it to keep the
    stored secret. Once `masked` is true it stays true.
    """
    by_key = {str(r.get("key") or ""): r for r in (stored or []) if r.get("key")}
    out = []
    seen = set()
    for raw in incoming or []:
        key = str(raw.get("key") or "").strip()
        if not key:
            continue
        if not valid_var_key(key):
            return [], f"Invalid variable key '{key}'"
        if key in seen:
            return [], f"Duplicate variable key '{key}'"
        seen.add(key)
        masked = bool(raw.get("masked") if "masked" in raw else raw.get("secret"))
        old = by_key.get(key) or {}
        if old.get("masked"):
            masked = True
        incoming_value = raw.get("value")
        if incoming_value is None or incoming_value == "":
            value = old.get("value") or ""
        else:
            value = str(incoming_value)
        if masked:
            if not value:
                if old.get("masked") and old.get("value"):
                    value = old["value"]
                else:
                    masked = False
        out.append({"key": key, "value": value, "masked": masked})
    return out, None


def lookup(vaults: dict[str, list], parent: str, key: str) -> tuple[str | None, bool]:
    """Return (value, masked) or (None, False) if missing."""
    for row in vaults.get(parent) or []:
        if row.get("key") == key:
            return row.get("value") or "", bool(row.get("masked"))
    return None, False


def collect_tokens(text: str) -> list[dict]:
    refs = []
    for m in TOKEN_RE.finditer(text or ""):
        refs.append({"parent": m.group(1), "key": m.group(2), "ref": m.group(0)})
    return refs


def resolve_public(text: str, vaults: dict[str, list]) -> dict:
    """Substitute unmasked vars only. Masked tokens stay as `{vault.key}`."""
    missing = []
    redacted = []

    def repl(match: re.Match) -> str:
        parent, key = match.group(1), match.group(2)
        value, masked = lookup(vaults, parent, key)
        if value is None:
            missing.append(f"{parent}.{key}")
            return match.group(0)
        if masked:
            redacted.append(f"{parent}.{key}")
            return match.group(0)
        return value

    resolved = TOKEN_RE.sub(repl, text or "")
    return {"text": resolved, "missing": missing, "redacted": redacted}


def resolve_internal(text: str, vaults: dict[str, list]) -> tuple[str, list[str]]:
    """Full substitute including masked values. For apply/deploy only — never HTTP."""
    missing = []

    def repl(match: re.Match) -> str:
        parent, key = match.group(1), match.group(2)
        value, _masked = lookup(vaults, parent, key)
        if value is None:
            missing.append(f"{parent}.{key}")
            return match.group(0)
        return value

    return TOKEN_RE.sub(repl, text or ""), missing


def vaults_map(rows) -> dict[str, list]:
    return {v.name: list(v.vars or []) for v in rows}
