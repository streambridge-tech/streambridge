"""Workspace-level key/value settings (mode, persisted secret key)."""
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.utils.db import Base


class WorkspaceSetting(Base):
    __tablename__ = "workspace_settings"

    key:   Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")
