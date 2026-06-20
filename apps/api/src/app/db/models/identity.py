"""Identity and global role persistence models."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, InsertedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.organization import Organization


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A future authenticated identity, scoped to one organization."""

    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("id", "organization_id", name="uq_users_id_organization"),)

    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(Text)
    identity_provider: Mapped[str | None] = mapped_column(String(100))
    identity_subject: Mapped[str | None] = mapped_column(String(255))
    preferred_language: Mapped[str] = mapped_column(String(16), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    organization: Mapped[Organization] = relationship(back_populates="users", lazy="raise")
    role_assignments: Mapped[list[UserRole]] = relationship(back_populates="user", lazy="raise")


class Role(UUIDPrimaryKeyMixin, InsertedAtMixin, Base):
    """A global role definition; authorization semantics arrive in Phase 6."""

    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    user_assignments: Mapped[list[UserRole]] = relationship(back_populates="role", lazy="raise")


class UserRole(InsertedAtMixin, Base):
    """Organization-bound membership in a global role."""

    __tablename__ = "user_roles"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "user_id"],
            ["users.organization_id", "users.id"],
            name="fk_user_roles_organization_user",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    role_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("roles.id"), primary_key=True
    )
    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("organizations.id"), primary_key=True
    )

    user: Mapped[User] = relationship(back_populates="role_assignments", lazy="raise")
    role: Mapped[Role] = relationship(back_populates="user_assignments", lazy="raise")
