"""Local user account (team mode).

`is_admin` is a superuser flag that bypasses RBAC checks. It exists so the
bootstrap Admin and recovery CLI can never be locked out by a role mistake.
Regular access is granted through roles (Phase 3), not this flag.
"""
import re
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.utils.db import Base
from app.utils.passwords import hash_password, needs_rehash, verify_password

_USERNAME_RE = re.compile(r"^[A-Za-z0-9._@+-]{3,128}$")


def normalize_username(raw: str) -> str:
    return (raw or "").strip().lower()


def valid_username(raw: str) -> bool:
    return bool(_USERNAME_RE.match(normalize_username(raw)))


class User(Base):
    __tablename__ = "users"

    id:            Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
    username:      Mapped[str]      = mapped_column(String(128), unique=True, nullable=False)
    password_hash: Mapped[str]      = mapped_column(String(255), nullable=False)
    active:        Mapped[bool]     = mapped_column(Boolean, nullable=False, default=True)
    is_admin:      Mapped[bool]     = mapped_column(Boolean, nullable=False, default=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    default_role_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at:    Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at:    Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc),
                                                    onupdate=lambda: datetime.now(timezone.utc))

    def set_password(self, raw: str) -> None:
        self.password_hash = hash_password(raw)

    def check_password(self, raw: str) -> bool:
        return verify_password(self.password_hash, raw)

    def password_needs_rehash(self) -> bool:
        return needs_rehash(self.password_hash)

    def to_public_dict(self) -> dict:
        # Never expose password_hash.
        return {
            "id":                 self.id,
            "username":           self.username,
            "active":             self.active,
            "isAdmin":            self.is_admin,
            "mustChangePassword": self.must_change_password,
            "defaultRoleId":      self.default_role_id,
            "createdAt":          self.created_at.isoformat() if self.created_at else None,
            "updatedAt":          self.updated_at.isoformat() if self.updated_at else None,
        }
