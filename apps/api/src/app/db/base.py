"""Shared SQLAlchemy metadata and PostgreSQL column conventions."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, MetaData, text
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.schema import FetchedValue

UTC_NOW_SQL = text("timezone('utc', now())")
UUID_SERVER_DEFAULT = text("gen_random_uuid()")
EMBEDDING_DIMENSIONS = 1536


class Base(DeclarativeBase):
    """Declarative base imported by models and Alembic."""

    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_name)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


class UUIDPrimaryKeyMixin:
    """Database-generated UUID primary key for durable records."""

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        server_default=UUID_SERVER_DEFAULT,
    )


class InsertedAtMixin:
    """UTC database timestamp for immutable or append-only records."""

    inserted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=UTC_NOW_SQL
    )


class TimestampMixin(InsertedAtMixin):
    """UTC insertion/update timestamps backed by the migration trigger."""

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=UTC_NOW_SQL,
        server_onupdate=FetchedValue(),
    )


class ArchivableMixin:
    """Optional soft-archival marker; retention workflows arrive later."""

    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
