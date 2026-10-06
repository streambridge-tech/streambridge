from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.utils.db import Base


class ConnectorFolder(Base):
    """Empty connector folders. A folder that holds a notebook also lives on that notebook."""

    __tablename__ = "connector_folders"

    path: Mapped[str] = mapped_column(String(256), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {"path": self.path}
