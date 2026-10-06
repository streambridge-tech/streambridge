"""Shared schema primitives for connector Connections.

A `Schema` is a per-subtype declaration of what fields the Connections form
accepts, plus for each field the two downstream mappings we need:

  • `kc_key`    — the Kafka Connect / Debezium config key it becomes on save
  • `test_key`  — the native-library kwarg it becomes at test_connection time
                  (e.g. `psycopg2.connect(host=…)`, `boto3.client('s3', region_name=…)`)

Storage stays canonical: `Connection.config` is a flat `{kc_key: value}` dict.
Design C ("dual-view API") is implemented by `build_test_kwargs()` which the
API layer calls to expose a computed `test_kwargs` view on read.

Keeping storage single-shape avoids drift; the schema is the single source of
truth for the mapping in either direction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

# Placeholder returned to clients instead of a stored secret value. Writing this
# value back is treated as "unchanged" so a read→save round-trip never clobbers
# the real secret.
SECRET_MASK = "\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022"


@dataclass(frozen=True)
class FieldDef:
    """One connection form field."""

    id: str                                     # form field id (frontend uses this)
    label: str                                  # UI display label
    kc_key: str | None = None                   # → Kafka Connect / Debezium config key
    test_key: str | None = None                 # → native-lib kwarg (psycopg2 / boto3 / etc.)

    type: str = "text"                          # text | password | number | boolean | enum | json
    importance: str = "required"                # required | recommended | advanced
    secret: bool = False                        # renders type=password + masked on read
    default: Any = None                         # form pre-fill and DEFAULT config value
    placeholder: str = ""
    doc: str = ""                               # tooltip in the UI

    options: tuple[str, ...] = ()               # for `type == "enum"`
    group: str = "connection"                   # logical form section (Connection, TLS, Tuning, …)
    order: int = 100                            # display order within group
    # Optional UI gate: {"field": "auth_type", "in": ["basic"]}
    visible_when: dict | None = None

    # Type coercion applied when writing to config (form → kc_config).
    # str is the safe default because Kafka Connect stores every value as a string.
    cast: Callable[[Any], Any] = str

    # Optional value transform when computing test_kwargs (kc value → test-lib value).
    # Useful when Debezium uses milliseconds but psycopg2 wants seconds, etc.
    test_transform: Callable[[Any], Any] | None = None

    # ── JSON view for the schema API (drops Callables) ────────────────────────
    def to_json(self) -> dict:
        return {
            "id":          self.id,
            "label":       self.label,
            "kcKey":       self.kc_key,
            "testKey":     self.test_key,
            "type":        self.type,
            "importance":  self.importance,
            "secret":      self.secret,
            "default":     self.default,
            "placeholder": self.placeholder,
            "doc":         self.doc,
            "options":     list(self.options),
            "group":        self.group,
            "order":        self.order,
            "visibleWhen":  self.visible_when,
        }


@dataclass(frozen=True)
class Schema:
    """A connector's form + kc + test schema."""

    subtype: str
    label: str
    fields: tuple[FieldDef, ...] = field(default_factory=tuple)

    def get(self, field_id: str) -> FieldDef | None:
        return next((f for f in self.fields if f.id == field_id), None)

    def by_kc_key(self, kc_key: str) -> FieldDef | None:
        return next((f for f in self.fields if f.kc_key == kc_key), None)

    def _by_importance(self, importance: str) -> list[FieldDef]:
        return sorted(
            [f for f in self.fields if f.importance == importance],
            key=lambda x: (x.group, x.order),
        )

    def required_fields(self) -> list[FieldDef]:
        return self._by_importance("required")

    def recommended_fields(self) -> list[FieldDef]:
        return self._by_importance("recommended")

    def advanced_fields(self) -> list[FieldDef]:
        return self._by_importance("advanced")

    def to_json(self) -> dict:
        return {
            "subtype":     self.subtype,
            "label":       self.label,
            "required":    [f.to_json() for f in self.required_fields()],
            "recommended": [f.to_json() for f in self.recommended_fields()],
            "advanced":    [f.to_json() for f in self.advanced_fields()],
        }


# ── helpers used by BaseConnector ─────────────────────────────────────────────

def build_kc_config(schema: Schema, form: dict) -> dict:
    """Convert a form dict `{field_id: value}` → kc_config dict `{kc_key: value}`.

    - Skips fields with no `kc_key`.
    - Skips empty / None values (so blank optional fields don't overwrite defaults).
    - Applies each field's `cast`.
    """
    out: dict = {}
    for f in schema.fields:
        if not f.kc_key:
            continue
        raw = form.get(f.id)
        if raw is None or raw == "":
            continue
        if raw == SECRET_MASK:
            # Masked secret echoed back unchanged; let merge_preserved_secrets keep the stored one.
            continue
        try:
            out[f.kc_key] = f.cast(raw)
        except (TypeError, ValueError):
            # Preserve the raw string; the connector's validate() will surface it.
            out[f.kc_key] = str(raw)
    return out


def build_test_kwargs(schema: Schema, config: dict) -> dict:
    """Convert a kc_config dict `{kc_key: value}` → test-lib kwargs `{test_key: value}`.

    - Skips fields with no `test_key`.
    - Skips empty / None values.
    - Applies each field's `test_transform` if set.
    """
    out: dict = {}
    for f in schema.fields:
        if not f.test_key:
            continue
        val = config.get(f.kc_key) if f.kc_key else None
        if val is None or val == "":
            continue
        if f.test_transform is not None:
            try:
                val = f.test_transform(val)
            except (TypeError, ValueError):
                continue
        out[f.test_key] = val
    return out


def defaults_kc_config(schema: Schema) -> dict:
    """Return `{kc_key: default}` for fields that declare a non-empty default."""
    return {
        f.kc_key: f.default
        for f in schema.fields
        if f.kc_key and f.default not in (None, "")
    }
