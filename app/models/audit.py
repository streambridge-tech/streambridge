"""Append-only audit log: who did what, when."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.utils.db import Base


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id:          Mapped[str]          = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    at:          Mapped[datetime]     = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    actor_id:    Mapped[int | None]   = mapped_column(Integer, nullable=True)
    actor:       Mapped[str]          = mapped_column(String(128), nullable=False, default="-")
    action:      Mapped[str]          = mapped_column(String(64), nullable=False)
    target_type: Mapped[str]          = mapped_column(String(32), nullable=False, default="")
    target_id:   Mapped[str]          = mapped_column(String(256), nullable=False, default="")
    summary:     Mapped[str]          = mapped_column(String(512), nullable=False, default="")
    status:      Mapped[str]          = mapped_column(String(16), nullable=False, default="ok")

    def to_dict(self) -> dict:
        return {
            "id":         self.id,
            "at":         self.at.isoformat() if self.at else None,
            "actor":      self.actor,
            "actorId":    self.actor_id,
            "action":     self.action,
            "targetType": self.target_type,
            "targetId":   self.target_id,
            "summary":    self.summary,
            "status":     self.status,
        }
