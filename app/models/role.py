"""RBAC models: roles, inheritance edges, permission grants, and assignments.

A permission grant is (permission_key, scope_type, scope_id). Effective access
for a user is the union over all assigned roles plus every role they inherit.
The `User.is_admin` superuser flag bypasses all of this (see app/models/user.py).
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.utils.db import Base

SCOPE_GLOBAL = "global"
SCOPE_FOLDER = "folder"
SCOPE_CLUSTER = "cluster"
SCOPE_TYPES = frozenset({SCOPE_GLOBAL, SCOPE_FOLDER, SCOPE_CLUSTER})

# Matches any entity id within a scope type (e.g. all folders).
SCOPE_ALL = "*"


class Role(Base):
    __tablename__ = "roles"

    id:          Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
    name:        Mapped[str]      = mapped_column(String(64), unique=True, nullable=False)
    description: Mapped[str]      = mapped_column(String(255), nullable=False, default="")
    is_builtin:  Mapped[bool]     = mapped_column(nullable=False, default=False)
    created_at:  Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at:  Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc),
                                                  onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "id":          self.id,
            "name":        self.name,
            "description": self.description,
            "isBuiltin":   self.is_builtin,
            "createdAt":   self.created_at.isoformat() if self.created_at else None,
            "updatedAt":   self.updated_at.isoformat() if self.updated_at else None,
        }


class RoleParent(Base):
    """Edge: `role_id` inherits from `parent_id`."""

    __tablename__ = "role_parents"

    role_id:   Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    parent_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)


class RolePermission(Base):
    __tablename__ = "role_permissions"
    __table_args__ = (
        UniqueConstraint("role_id", "permission_key", "scope_type", "scope_id",
                         name="uq_role_permission"),
    )

    id:             Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role_id:        Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    permission_key: Mapped[str] = mapped_column(String(64), nullable=False)
    scope_type:     Mapped[str] = mapped_column(String(16), nullable=False, default=SCOPE_GLOBAL)
    scope_id:       Mapped[str] = mapped_column(String(128), nullable=False, default=SCOPE_ALL)


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
