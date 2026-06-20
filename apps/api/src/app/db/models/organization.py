"""Tenant organization persistence model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import ArchivableMixin, Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.case import Case
    from app.db.models.document import Document, DocumentChunk
    from app.db.models.identity import User
    from app.db.models.workflow import WorkflowRun


class Organization(UUIDPrimaryKeyMixin, TimestampMixin, ArchivableMixin, Base):
    """An organization is the root scope for regulated product records."""

    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    default_language: Mapped[str] = mapped_column(String(16), nullable=False)
    retention_policy: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    settings: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    users: Mapped[list[User]] = relationship(back_populates="organization", lazy="raise")
    cases: Mapped[list[Case]] = relationship(back_populates="organization", lazy="raise")
    documents: Mapped[list[Document]] = relationship(back_populates="organization", lazy="raise")
    document_chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="organization", lazy="raise", viewonly=True
    )
    workflow_runs: Mapped[list[WorkflowRun]] = relationship(
        back_populates="organization", lazy="raise"
    )
