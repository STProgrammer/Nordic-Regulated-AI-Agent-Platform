"""Controlled-memory persistence model without a memory-provider integration."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
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
        CheckConstraint(
            "NOT is_active OR ((memory_scope = 'user' AND user_id IS NOT NULL "
            "AND memory_type = 'ui_language_preference') "
            "OR (memory_scope = 'organization' AND user_id IS NULL AND memory_type IN "
            "('workflow_presentation_preference', 'approved_terminology', 'process_hint')))",
            name="memory_entries_scope_type_owner",
        ),
        CheckConstraint(
            "NOT is_active OR source IN ('self_preference', 'admin_approved')",
            name="memory_entries_source_closed",
        ),
        ForeignKeyConstraint(
            ["organization_id", "user_id"],
            ["users.organization_id", "users.id"],
            name="fk_memory_entries_organization_user",
        ),
        UniqueConstraint("id", "organization_id", name="uq_memory_entries_id_organization"),
        Index("ix_memory_entries_organization_memory_scope", "organization_id", "memory_scope"),
        Index("ix_memory_entries_organization_user", "organization_id", "user_id"),
        Index(
            "uq_memory_entries_active_natural_key",
            "organization_id",
            "memory_scope",
            "user_id",
            "natural_key",
            unique=True,
            postgresql_where=text("is_active AND archived_at IS NULL"),
        ),
        Index(
            "ix_memory_entries_active_presentation",
            "organization_id",
            "memory_scope",
            "memory_type",
            "updated_at",
            postgresql_where=text("is_active AND archived_at IS NULL"),
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    user_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    memory_scope: Mapped[str] = mapped_column(String(32), nullable=False)
    memory_type: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    store_key: Mapped[str] = mapped_column(String(64), nullable=False)
    natural_key: Mapped[str] = mapped_column(String(320), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    user: Mapped[User | None] = relationship(foreign_keys=[organization_id, user_id], lazy="raise")


class MemoryUsageRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Content-free record of a governed memory consideration or application."""

    __tablename__ = "memory_usage_records"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "memory_entry_id"],
            ["memory_entries.organization_id", "memory_entries.id"],
            name="fk_memory_usage_records_organization_entry",
        ),
        Index("ix_memory_usage_records_organization_inserted", "organization_id", "inserted_at"),
        Index("ix_memory_usage_records_entry_inserted", "memory_entry_id", "inserted_at"),
        Index("ix_memory_usage_records_workflow_inserted", "workflow_run_id", "inserted_at"),
        CheckConstraint(
            "operation IN ('drafting_presentation')", name="memory_usage_records_operation_closed"
        ),
        CheckConstraint(
            "outcome IN ('applied', 'skipped', 'blocked')",
            name="memory_usage_records_outcome_closed",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    memory_entry_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    workflow_run_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("workflow_runs.id")
    )
    operation: Mapped[str] = mapped_column(String(64), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
