from datetime import datetime, timezone
from sqlalchemy import Integer, String, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.utils.db import Base

# Mask value echoed to clients in place of stored secrets.
_SECRET_MASK = "\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022"
# Secret key names masked on connections that have no registered schema
# (e.g. notification-slack/gchat store their token under these keys).
_GENERIC_SECRET_KEYS = frozenset({
    "password", "passwd", "secret", "token", "api_key", "apikey",
    "aws_secret_access_key", "sasl_password", "sasl.password", "private_key",
})


def _mask_config(config, schema) -> dict:
    if not isinstance(config, dict):
        return config
    masked = dict(config)
    if schema is not None:
        for f in schema.fields:
            if f.secret and f.kc_key and masked.get(f.kc_key) not in (None, ""):
                masked[f.kc_key] = _SECRET_MASK
    else:
        for key in list(masked):
            if key.lower() in _GENERIC_SECRET_KEYS and masked.get(key) not in (None, ""):
                masked[key] = _SECRET_MASK
    return masked


class Connection(Base):
    __tablename__ = "connections"

    id:         Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
    name:       Mapped[str]      = mapped_column(String(128), unique=True, nullable=False)
    type:       Mapped[str]      = mapped_column(String(64),  nullable=False)  # transport | connect | notification
    subtype:    Mapped[str]      = mapped_column(String(64),  nullable=False)  # postgres | mysql …
    status:     Mapped[str]      = mapped_column(String(32),  nullable=False, default="draft")
    used_in:    Mapped[list]     = mapped_column(JSON, nullable=False, default=list)
    config:     Mapped[dict]     = mapped_column(JSON, nullable=False, default=dict)  # merged form + extra
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc),
                                                 onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self, *, include_views: bool = True) -> dict:
        schema = None
        try:
            from app.connectors.schemas import get_schema
            schema = get_schema(self.subtype)
        except Exception:
            schema = None
        d = {
            "id":        self.id,
            "name":      self.name,
            "type":      self.type,
            "subtype":   self.subtype,
            "status":    self.status,
            "usedIn":    self.used_in,
            "config":    _mask_config(self.config, schema),
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
        }
        if include_views:
            # Dual-view: expose test_kwargs alongside the canonical config so
            # consumers (test-connection UI, frontend, external tools) don't
            # need to know the mapping. Storage stays single-shape.
            try:
                from app.connectors.schemas import build_test_kwargs
                if schema:
                    d["deployConfig"] = _mask_config(self.config, schema)
                    # Mask secrets so we never echo passwords on read.
                    kwargs = build_test_kwargs(schema, self.config)
                    for f in schema.fields:
                        if f.secret and f.test_key in kwargs:
                            kwargs[f.test_key] = _SECRET_MASK
                    d["testKwargs"] = kwargs
            except Exception:
                # Schema module optional; if unavailable, degrade to config-only.
                pass
        return d
