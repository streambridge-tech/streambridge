import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.utils.db import Base


class AlertDeliveryAttempt(Base):
    """One attempt to deliver an alert message to a notification channel.

    Written by `POST /api/alerts/<id>/test` and the alert scheduler (`kind=fire`).
    """

    __tablename__ = "alert_delivery_attempts"

    id:            Mapped[str]           = mapped_column(String(36),  primary_key=True, default=lambda: str(uuid.uuid4()))
    alert_id:      Mapped[str]           = mapped_column(String(36),  nullable=False, index=True)
    connection_id: Mapped[int | None]    = mapped_column(Integer,     nullable=True)
    channel:       Mapped[str]           = mapped_column(String(64),  nullable=False)   # notification-slack | notification-gchat | ...
    kind:          Mapped[str]           = mapped_column(String(16),  nullable=False, default="test")  # test | fire
    success:       Mapped[int]           = mapped_column(Integer,     nullable=False)   # 0/1 (SQLite boolean)
    http_status:   Mapped[int | None]    = mapped_column(Integer,     nullable=True)
    error:         Mapped[str | None]    = mapped_column(String(512), nullable=True)
    latency_ms:    Mapped[int]           = mapped_column(Integer,     nullable=False, default=0)
    message:       Mapped[str | None]    = mapped_column(String(2000), nullable=True)
    status:        Mapped[str | None]    = mapped_column(String(32),  nullable=True)
    log_text:      Mapped[str | None]    = mapped_column(Text,        nullable=True)
    created_at:    Mapped[datetime]      = mapped_column(DateTime,    default=lambda: datetime.now(timezone.utc), index=True)

    def to_dict(self) -> dict:
        return {
            "id":           self.id,
            "alertId":      self.alert_id,
            "connectionId": self.connection_id,
            "channel":      self.channel,
            "kind":         self.kind,
            "success":      bool(self.success),
            "httpStatus":   self.http_status,
            "error":        self.error,
            "latencyMs":    self.latency_ms,
            "message":      self.message,
            "status":       self.status,
            "logText":      self.log_text,
            "createdAt":    self.created_at.isoformat() if self.created_at else None,
        }
