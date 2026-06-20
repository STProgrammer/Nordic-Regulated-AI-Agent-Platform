"""Controlled-memory persistence model without a memory-provider integration."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Boolean,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import ArchivableMixin, Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.identity import User


class MemoryEntry(UUIDPrimaryKeyMixin, TimestampMixin, ArchivableMixin, Base):
    """An auditable organization/user-scoped memory record."""

    __tablename__ = "memory_entries"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "user_id"],
            ["users.organization_id", "users.id"],
            name="fk_memory_entries_organization_user",
        ),
        UniqueConstraint("id", "organization_id", name="uq_memory_entries_id_organization"),
        Index("ix_memory_entries_organization_memory_scope", "organization_id", "memory_scope"),
        Index("ix_memory_entries_organization_user", "organization_id", "user_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    user_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    memory_scope: Mapped[str] = mapped_column(String(100), nullable=False)
    memory_type: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    user: Mapped[User | None] = relationship(foreign_keys=[organization_id, user_id], lazy="raise")
