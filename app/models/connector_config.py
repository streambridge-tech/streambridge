import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.utils.db import Base


class ConnectorConfig(Base):
    __tablename__ = "connector_configs"

    id:             Mapped[str]      = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    pipeline_id:    Mapped[str]      = mapped_column(String(36), ForeignKey("pipelines.id"), nullable=False, index=True)
    connector_name: Mapped[str]      = mapped_column(String(256), nullable=False)   # <pipeline_name>-source/sink
    type:           Mapped[str]      = mapped_column(String(16),  nullable=False)   # source | sink
    plugin_name:    Mapped[str]      = mapped_column(String(128), nullable=False)   # e.g. postgres-json
    config:         Mapped[str]      = mapped_column(Text,        nullable=False, default="{}")  # final merged JSON
    created_at:     Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at:     Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc),
                                                     onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        import json
        return {
            "id":            self.id,
            "pipelineId":    self.pipeline_id,
            "connectorName": self.connector_name,
            "type":          self.type,
            "pluginName":    self.plugin_name,
            "config":        json.loads(self.config),
            "createdAt":     self.created_at.isoformat(),
            "updatedAt":     self.updated_at.isoformat(),
        }
