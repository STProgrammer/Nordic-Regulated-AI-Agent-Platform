"""Governed document, extracted-text, and retrieval-storage models."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pgvector.sqlalchemy import Vector  # type: ignore[import-untyped]
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import (
    EMBEDDING_DIMENSIONS,
    ArchivableMixin,
    Base,
    InsertedAtMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)

if TYPE_CHECKING:
    from app.db.models.case import Case
    from app.db.models.identity import User
    from app.db.models.organization import Organization


class Document(UUIDPrimaryKeyMixin, TimestampMixin, ArchivableMixin, Base):
    """Metadata for a raw object held outside PostgreSQL."""

    __tablename__ = "documents"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            name="fk_documents_organization_case",
        ),
        ForeignKeyConstraint(
            ["organization_id", "uploaded_by_user_id"],
            ["users.organization_id", "users.id"],
            name="fk_documents_organization_uploaded_by_user",
        ),
        UniqueConstraint("id", "organization_id", name="uq_documents_id_organization"),
        CheckConstraint("file_size_bytes >= 0", name="file_size_bytes_nonnegative"),
        CheckConstraint("page_count IS NULL OR page_count >= 0", name="page_count_nonnegative"),
        Index("ix_documents_organization_case", "organization_id", "case_id"),
        Index("ix_documents_organization_source_status", "organization_id", "source_status"),
        Index("ix_documents_checksum_sha256", "checksum_sha256"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    case_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    uploaded_by_user_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    file_type: Mapped[str] = mapped_column(String(100), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    object_storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str | None] = mapped_column(String(16))
    source_status: Mapped[str] = mapped_column(String(50), nullable=False)
    confidentiality_level: Mapped[str] = mapped_column(String(50), nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer)
    parsing_status: Mapped[str] = mapped_column(String(50), nullable=False)
    parsing_error: Mapped[str | None] = mapped_column(Text)
    organization: Mapped[Organization] = relationship(back_populates="documents", lazy="raise")
    case: Mapped[Case | None] = relationship(
        foreign_keys=[organization_id, case_id], lazy="raise", viewonly=True
    )
    uploaded_by_user: Mapped[User] = relationship(
        foreign_keys=[organization_id, uploaded_by_user_id], lazy="raise", viewonly=True
    )
    text_record: Mapped[DocumentText | None] = relationship(
        back_populates="document", lazy="raise", uselist=False
    )
    chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="document", lazy="raise", viewonly=True
    )


class DocumentText(UUIDPrimaryKeyMixin, InsertedAtMixin, Base):
    """One canonical extracted-text record per document."""

    __tablename__ = "document_texts"

    document_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, unique=True
    )
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False)
    extraction_metadata: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    document: Mapped[Document] = relationship(back_populates="text_record", lazy="raise")


class DocumentChunk(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Future retrieval chunk with a fixed 1536-dimensional vector contract."""

    __tablename__ = "document_chunks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "document_id"],
            ["documents.organization_id", "documents.id"],
            name="fk_document_chunks_organization_document",
        ),
        UniqueConstraint("id", "organization_id", name="uq_document_chunks_id_organization"),
        UniqueConstraint(
            "document_id", "chunk_index", name="uq_document_chunks_document_chunk_index"
        ),
        CheckConstraint("chunk_index >= 0", name="chunk_index_nonnegative"),
        CheckConstraint("page_number IS NULL OR page_number >= 0", name="page_number_nonnegative"),
        CheckConstraint("token_count >= 0", name="token_count_nonnegative"),
        Index("ix_document_chunks_organization_document", "organization_id", "document_id"),
        Index(
            "ix_document_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
            postgresql_with={"m": 16, "ef_construction": 64},
        ),
        Index(
            "ix_document_chunks_content_fts",
            text("to_tsvector('simple', content)"),
            postgresql_using="gin",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    document_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer)
    section_title: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_metadata: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS), nullable=False)

    organization: Mapped[Organization] = relationship(
        back_populates="document_chunks", lazy="raise", viewonly=True
    )
    document: Mapped[Document] = relationship(back_populates="chunks", lazy="raise", viewonly=True)
