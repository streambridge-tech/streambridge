import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.utils.db import Base


class Pipeline(Base):
    __tablename__ = "pipelines"

    id:              Mapped[str]      = mapped_column(String(36),  primary_key=True, default=lambda: str(uuid.uuid4()))
    name:            Mapped[str]      = mapped_column(String(128), nullable=False, index=True)
    env:             Mapped[str]      = mapped_column(String(64),  nullable=False, default="")
    yaml_raw:        Mapped[str]      = mapped_column(Text,        nullable=False, default="")
    yaml_resolved:   Mapped[str]      = mapped_column(Text,        nullable=False, default="")
    # final merged configs sent to Kafka Connect (plugin base + conn values + pipeline YAML keys)
    source_config:   Mapped[str]      = mapped_column(Text,        nullable=False, default="{}")
    sink_config:     Mapped[str]      = mapped_column(Text,        nullable=False, default="{}")
    status:          Mapped[str]      = mapped_column(String(32),  nullable=False, default="deploying")
    created_at:      Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at:      Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc),
                                                      onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        import json
        return {
            "id":           self.id,
            "name":         self.name,
            "env":          self.env,
            "yamlRaw":      self.yaml_raw,
            "yamlResolved": self.yaml_resolved,
            "sourceConfig": json.loads(self.source_config),
            "sinkConfig":   json.loads(self.sink_config),
            "status":       self.status,
            "createdAt":    self.created_at.isoformat(),
            "updatedAt":    self.updated_at.isoformat(),
        }
