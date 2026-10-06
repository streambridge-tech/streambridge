import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.utils.db import Base


class ConnectorCommandLog(Base):
    """One persisted Logs-tab row: save / secrets / deploy / API command."""

    __tablename__ = "connector_command_logs"

    id:          Mapped[str]           = mapped_column(String(36),  primary_key=True, default=lambda: str(uuid.uuid4()))
    notebook_id: Mapped[str]           = mapped_column(String(36),  nullable=False, index=True)
    step:        Mapped[str]           = mapped_column(String(32),  nullable=False)
    message:     Mapped[str]           = mapped_column(String(512), nullable=False)
    status:      Mapped[str]           = mapped_column(String(16),  nullable=False, default="ok")
    detail:      Mapped[str | None]    = mapped_column(Text,        nullable=True)
    http_status: Mapped[int | None]    = mapped_column(Integer,     nullable=True)
    latency_ms:  Mapped[int]           = mapped_column(Integer,     nullable=False, default=0)
    created_at:  Mapped[datetime]      = mapped_column(DateTime,    default=lambda: datetime.now(timezone.utc), index=True)

    def to_dict(self) -> dict:
        ok = self.status == "ok"
        http = self.http_status if self.http_status is not None else (200 if ok else 400)
        return {
            "id":         self.id,
            "configId":   self.notebook_id,
            "at":         self.created_at.isoformat() if self.created_at else None,
            "action":     self.message,
            "key":        self.step,
            "method":     "STEP",
            "http":       http,
            "statusText": self.status.upper() if self.status else "",
            "timeMs":     self.latency_ms,
            "bodyText":   self.detail or "",
            "step":       self.step,
            "status":     self.status,
        }
