import json
import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.utils.db import Base


def _json_obj(raw, fallback):
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else fallback
        except json.JSONDecodeError:
            return fallback
    return fallback


class ConnectorNotebook(Base):
    """Authored Connectors page notebook. Not a live Kafka Connect record."""

    __tablename__ = "connector_notebooks"

    id:                 Mapped[str]           = mapped_column(String(36),  primary_key=True, default=lambda: str(uuid.uuid4()))
    name:               Mapped[str]           = mapped_column(String(128), nullable=False, index=True)
    folder:             Mapped[str]           = mapped_column(String(256), nullable=False, default="default")
    attached_cluster:   Mapped[str]           = mapped_column(String(128), nullable=False, default="")
    plugin_id:          Mapped[str]           = mapped_column(String(128), nullable=False, default="blank")
    level:              Mapped[str]           = mapped_column(String(32),  nullable=False, default="starter")
    connector_type:     Mapped[str]           = mapped_column(String(32),  nullable=False, default="expert")
    notes:              Mapped[str | None]    = mapped_column(Text,        nullable=True)
    doc_json:           Mapped[str | None]    = mapped_column(Text,        nullable=True)
    lineage_json:       Mapped[str | None]    = mapped_column(Text,        nullable=True)
    connections_json:   Mapped[str | None]    = mapped_column(Text,        nullable=True)
    bound:              Mapped[bool]          = mapped_column(Boolean,     nullable=False, default=False)
    last_deploy_status: Mapped[str]           = mapped_column(String(16),  nullable=False, default="never")
    last_deploy_error:  Mapped[str | None]    = mapped_column(String(2000), nullable=True)
    last_deployed_at:   Mapped[datetime | None] = mapped_column(DateTime,  nullable=True)
    live_state:         Mapped[str]           = mapped_column(String(16),  nullable=False, default="")
    live_tasks:         Mapped[str | None]    = mapped_column(String(16),  nullable=True)
    live_checked_at:    Mapped[datetime | None] = mapped_column(DateTime,  nullable=True)
    created_at:         Mapped[datetime]      = mapped_column(DateTime,    default=lambda: datetime.now(timezone.utc))
    updated_at:         Mapped[datetime]      = mapped_column(DateTime,    default=lambda: datetime.now(timezone.utc),
                                                              onupdate=lambda: datetime.now(timezone.utc))

    def doc(self) -> dict:
        return _json_obj(self.doc_json, {"name": self.name, "config": {}})

    def lineage(self) -> dict:
        return _json_obj(self.lineage_json, {"dependsOn": []})

    def connections(self) -> dict:
        return _json_obj(self.connections_json, {"database": "", "kafka": "", "schemaRegistry": ""})

    def to_dict(self) -> dict:
        doc = self.doc()
        if not doc.get("name"):
            doc["name"] = self.name
        return {
            "id":               self.id,
            "name":             self.name,
            "folder":           self.folder or "default",
            "attachedCluster":  self.attached_cluster or "",
            "pluginId":         self.plugin_id,
            "level":            self.level,
            "type":             self.connector_type,
            "notes":            self.notes or "",
            "doc":              doc,
            "lineage":          self.lineage(),
            "connections":      self.connections(),
            "bound":            bool(self.bound),
            "lastDeployStatus": self.last_deploy_status,
            "lastDeployError":  self.last_deploy_error,
            "lastDeployedAt":   self.last_deployed_at.isoformat() if self.last_deployed_at else None,
            "liveState":        self.live_state or "",
            "liveTasks":        self.live_tasks or "",
            "liveCheckedAt":    self.live_checked_at.isoformat() if self.live_checked_at else None,
            "createdAt":        self.created_at.isoformat() if self.created_at else None,
            "updatedAt":        self.updated_at.isoformat() if self.updated_at else None,
        }
