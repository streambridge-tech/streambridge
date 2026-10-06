from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, JSON, String
from sqlalchemy.orm import Mapped, mapped_column
from app.utils.db import Base


class Vault(Base):
    """Named secret set (dev, prod). Pipeline YAML maps stage → vault."""

    __tablename__ = "vaults"

    name:       Mapped[str]      = mapped_column(String(64), primary_key=True)
    vars:       Mapped[list]     = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc),
                                                 onupdate=lambda: datetime.now(timezone.utc))

    def to_public_dict(self) -> dict:
        rows = []
        for raw in self.vars or []:
            key = str(raw.get("key") or "").strip()
            if not key:
                continue
            masked = bool(raw.get("masked"))
            value = raw.get("value") or ""
            item = {
                "key": key,
                "masked": masked,
                "hasValue": bool(value),
            }
            if not masked:
                item["value"] = value
            rows.append(item)
        return {
            "name": self.name,
            "vars": rows,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }
