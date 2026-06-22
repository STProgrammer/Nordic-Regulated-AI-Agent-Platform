"""Business-case persistence model."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import ArchivableMixin, Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.identity import User
    from app.db.models.organization import Organization


class Case(UUIDPrimaryKeyMixin, TimestampMixin, ArchivableMixin, Base):
    """A tenant-scoped business case governed by the Case Management service."""

    __tablename__ = "cases"
    __table_args__ = (
        CheckConstraint(
            "domain IN ('public_sector', 'banking', 'energy', 'internal_policy')",
            name="domain_allowed",
        ),
        ForeignKeyConstraint(
            ["organization_id", "assigned_user_id"],
            ["users.organization_id", "users.id"],
            name="fk_cases_organization_assigned_user",
        ),
        ForeignKeyConstraint(
            ["organization_id", "submitted_by_user_id"],
            ["users.organization_id", "users.id"],
            name="fk_cases_organization_submitted_by_user",
        ),
        UniqueConstraint("id", "organization_id", name="uq_cases_id_organization"),
        UniqueConstraint(
            "organization_id", "case_number", name="uq_cases_organization_case_number"
        ),
        Index("ix_cases_organization_status", "organization_id", "status"),
        Index("ix_cases_organization_risk_level", "organization_id", "risk_level"),
        Index("ix_cases_organization_case_number", "organization_id", "case_number"),
        Index("ix_cases_organization_inserted_at", "organization_id", "inserted_at"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    case_number: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    domain: Mapped[str] = mapped_column(String(100), nullable=False)
    case_type: Mapped[str | None] = mapped_column(String(100))
    priority: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    risk_level: Mapped[str | None] = mapped_column(String(50))
    assigned_user_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    submitted_by_user_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date)
    external_reference: Mapped[str | None] = mapped_column(String(255))

    organization: Mapped[Organization] = relationship(back_populates="cases", lazy="raise")
    assigned_user: Mapped[User | None] = relationship(
        foreign_keys=[organization_id, assigned_user_id], lazy="raise", viewonly=True
    )
    submitted_by_user: Mapped[User] = relationship(
        foreign_keys=[organization_id, submitted_by_user_id], lazy="raise", viewonly=True
    )
