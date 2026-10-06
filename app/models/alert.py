import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.utils.db import Base


def _rules_to_dict(alert) -> list:
    from app.services.alerting.policy import rules_for
    return rules_for(alert)


class Alert(Base):
    __tablename__ = "alerts"

    id:               Mapped[str]           = mapped_column(String(36),  primary_key=True, default=lambda: str(uuid.uuid4()))
    name:             Mapped[str]           = mapped_column(String(128), nullable=False)
    connector_name:   Mapped[str]           = mapped_column(String(128), nullable=False, index=True)
    connector_type:   Mapped[str]           = mapped_column(String(16),  nullable=False)
    pipeline_id:      Mapped[str | None]    = mapped_column(String(36),  nullable=True)
    pipeline_name:    Mapped[str | None]    = mapped_column(String(128), nullable=True)
    notebook_id:      Mapped[str | None]    = mapped_column(String(36),  nullable=True, index=True)
    condition_metric: Mapped[str]           = mapped_column(String(64),  nullable=False, default="connector_status")
    condition_op:     Mapped[str]           = mapped_column(String(8),   nullable=False, default="eq")
    condition_value:  Mapped[str]           = mapped_column(String(128), nullable=False, default="FAILED")
    severity:         Mapped[str]           = mapped_column(String(16),  nullable=False, default="high")
    channel_type:     Mapped[str]           = mapped_column(String(32),  nullable=False, default="slack")
    channel_name:     Mapped[str]           = mapped_column(String(256), nullable=False, default="")
    message:          Mapped[str]           = mapped_column(String(512), nullable=False, default="")
    attempts:         Mapped[int]           = mapped_column(Integer,     nullable=False, default=1)
    active:           Mapped[bool]          = mapped_column(Boolean,     nullable=False, default=True)
    check_every_min:  Mapped[int]           = mapped_column(Integer,     nullable=False, default=5)
    match_action:     Mapped[str]           = mapped_column(String(16),  nullable=False, default="pause")
    rules_json:       Mapped[str | None]    = mapped_column(Text,        nullable=True, default="[]")
    state:            Mapped[str]           = mapped_column(String(16),  nullable=False, default="unknown")
    last_fired_at:    Mapped[datetime|None] = mapped_column(DateTime,    nullable=True)
    created_at:       Mapped[datetime]      = mapped_column(DateTime,    default=lambda: datetime.now(timezone.utc))
    updated_at:       Mapped[datetime]      = mapped_column(DateTime,    default=lambda: datetime.now(timezone.utc),
                                                            onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "id":              self.id,
            "name":            self.name,
            "connectorName":   self.connector_name,
            "connectorType":   self.connector_type,
            "pipelineId":      self.pipeline_id,
            "pipelineName":    self.pipeline_name,
            "notebookId":      self.notebook_id,
            "conditionMetric": self.condition_metric,
            "conditionOp":     self.condition_op,
            "conditionValue":  self.condition_value,
            "severity":        self.severity,
            "channelType":     self.channel_type,
            "channelName":     self.channel_name,
            "message":         self.message,
            "active":          bool(self.active),
            "checkEveryMin":   self.check_every_min,
            "action":          self.match_action,
            "rules":           _rules_to_dict(self),
            "state":           self.state,
            "lastFiredAt":     self.last_fired_at.isoformat() if self.last_fired_at else None,
            "createdAt":       self.created_at.isoformat(),
            "updatedAt":       self.updated_at.isoformat(),
        }
