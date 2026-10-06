from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.utils.db import Base


class Plugin(Base):
    __tablename__ = "plugins"

    name:        Mapped[str]      = mapped_column(String(128), primary_key=True)
    db:          Mapped[str]      = mapped_column(String(64),  nullable=False)
    type:        Mapped[str]      = mapped_column(String(16),  nullable=False)   # source | sink
    format:      Mapped[str]      = mapped_column(String(16),  nullable=False)   # JSON | AVRO …
    description: Mapped[str]      = mapped_column(Text,        nullable=False, default="")
    config:      Mapped[str]      = mapped_column(Text,        nullable=False)   # JSON string
    is_builtin:  Mapped[bool]     = mapped_column(Boolean,     nullable=False, default=False)
    created_at:  Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at:  Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc),
                                                  onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        import json
        return {
            "name":        self.name,
            "db":          self.db,
            "type":        self.type,
            "format":      self.format,
            "description": self.description,
            "config":      json.loads(self.config),
            "isBuiltin":   self.is_builtin,
            "createdAt":   self.created_at.isoformat(),
            "updatedAt":   self.updated_at.isoformat(),
        }
