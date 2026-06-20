"""Append-only audit-event persistence model."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, ForeignKeyConstraint, Index, String, Text, text
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, InsertedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.case import Case
    from app.db.models.identity import User


class AuditEvent(UUIDPrimaryKeyMixin, InsertedAtMixin, Base):
    """Immutable application audit record without mutable timestamps."""

    __tablename__ = "audit_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "actor_user_id"],
            ["users.organization_id", "users.id"],
            name="fk_audit_events_organization_actor_user",
        ),
        ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            name="fk_audit_events_organization_case",
        ),
        Index("ix_audit_events_organization_inserted_at", "organization_id", "inserted_at"),
        Index("ix_audit_events_organization_event_type", "organization_id", "event_type"),
        Index("ix_audit_events_case_id", "case_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    actor_user_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    case_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    ip_address: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)
    event_data: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    actor_user: Mapped[User | None] = relationship(
        foreign_keys=[organization_id, actor_user_id], lazy="raise", viewonly=True
    )
    case: Mapped[Case | None] = relationship(
        foreign_keys=[organization_id, case_id], lazy="raise", viewonly=True
    )
