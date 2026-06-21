"""Workflow traces, AI outputs, risk, and approval persistence models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, InsertedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.case import Case
    from app.db.models.document import Document, DocumentChunk
    from app.db.models.identity import User
    from app.db.models.organization import Organization
    from app.db.models.prompt import PromptVersion


class WorkflowRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A persisted workflow invocation, without graph-execution behavior."""

    __tablename__ = "workflow_runs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            name="fk_workflow_runs_organization_case",
        ),
        ForeignKeyConstraint(
            ["organization_id", "started_by_user_id"],
            ["users.organization_id", "users.id"],
            name="fk_workflow_runs_organization_started_by_user",
        ),
        UniqueConstraint("id", "organization_id", name="uq_workflow_runs_id_organization"),
        CheckConstraint("duration_ms IS NULL OR duration_ms >= 0", name="duration_ms_nonnegative"),
        CheckConstraint(
            "total_tokens IS NULL OR total_tokens >= 0", name="total_tokens_nonnegative"
        ),
        Index("ix_workflow_runs_organization_case", "organization_id", "case_id"),
        Index("ix_workflow_runs_organization_workflow_name", "organization_id", "workflow_name"),
        Index("ix_workflow_runs_organization_status", "organization_id", "status"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    case_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    workflow_name: Mapped[str] = mapped_column(String(255), nullable=False)
    workflow_version: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    started_by_user_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    total_cost_estimate: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    total_tokens: Mapped[int | None] = mapped_column(Integer)
    error_summary: Mapped[str | None] = mapped_column(Text)
    state_snapshot: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    organization: Mapped[Organization] = relationship(back_populates="workflow_runs", lazy="raise")
    case: Mapped[Case] = relationship(
        foreign_keys=[organization_id, case_id], lazy="raise", viewonly=True
    )
    started_by_user: Mapped[User] = relationship(
        foreign_keys=[organization_id, started_by_user_id], lazy="raise", viewonly=True
    )
    node_runs: Mapped[list[WorkflowNodeRun]] = relationship(
        back_populates="workflow_run", lazy="raise"
    )
    tool_calls: Mapped[list[WorkflowToolCall]] = relationship(
        back_populates="workflow_run", lazy="raise"
    )


class WorkflowNodeRun(UUIDPrimaryKeyMixin, InsertedAtMixin, Base):
    """A compact, safe trace for one future workflow node execution."""

    __tablename__ = "workflow_node_runs"
    __table_args__ = (
        CheckConstraint("duration_ms IS NULL OR duration_ms >= 0", name="duration_ms_nonnegative"),
        CheckConstraint("retry_count >= 0", name="retry_count_nonnegative"),
        Index("ix_workflow_node_runs_workflow_run_id", "workflow_run_id"),
        Index("ix_workflow_node_runs_node_name_status", "node_name", "status"),
    )

    workflow_run_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("workflow_runs.id"), nullable=False
    )
    node_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    input_summary: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    output_summary: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    error_summary: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    workflow_run: Mapped[WorkflowRun] = relationship(back_populates="node_runs", lazy="raise")


class WorkflowToolCall(UUIDPrimaryKeyMixin, InsertedAtMixin, Base):
    """Metadata-only invocation record for one server-registered workflow tool."""

    __tablename__ = "workflow_tool_calls"
    __table_args__ = (
        CheckConstraint("duration_ms IS NULL OR duration_ms >= 0", name="duration_ms_nonnegative"),
        CheckConstraint("retry_count >= 0", name="retry_count_nonnegative"),
        Index("ix_workflow_tool_calls_workflow_run_started", "workflow_run_id", "started_at"),
        Index("ix_workflow_tool_calls_workflow_node_run_id", "workflow_node_run_id"),
    )

    workflow_run_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("workflow_runs.id"), nullable=False
    )
    workflow_node_run_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("workflow_node_runs.id")
    )
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    input_summary: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    output_summary: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    error_summary: Mapped[str | None] = mapped_column(Text)

    workflow_run: Mapped[WorkflowRun] = relationship(back_populates="tool_calls", lazy="raise")


class AgentMessage(UUIDPrimaryKeyMixin, InsertedAtMixin, Base):
    """An AI message or structured model output tied to a workflow trace."""

    __tablename__ = "agent_messages"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            name="fk_agent_messages_organization_case",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workflow_run_id"],
            ["workflow_runs.organization_id", "workflow_runs.id"],
            name="fk_agent_messages_organization_workflow_run",
        ),
        CheckConstraint("token_input IS NULL OR token_input >= 0", name="token_input_nonnegative"),
        CheckConstraint(
            "token_output IS NULL OR token_output >= 0", name="token_output_nonnegative"
        ),
        CheckConstraint("latency_ms IS NULL OR latency_ms >= 0", name="latency_ms_nonnegative"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    case_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    workflow_run_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    message_type: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    structured_output: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    model_provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt_version_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("prompt_versions.id")
    )
    token_input: Mapped[int | None] = mapped_column(Integer)
    token_output: Mapped[int | None] = mapped_column(Integer)
    cost_estimate: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    latency_ms: Mapped[int | None] = mapped_column(Integer)

    workflow_run: Mapped[WorkflowRun] = relationship(
        foreign_keys=[organization_id, workflow_run_id], lazy="raise", viewonly=True
    )
    prompt_version: Mapped[PromptVersion | None] = relationship(lazy="raise")


class RetrievedSource(UUIDPrimaryKeyMixin, InsertedAtMixin, Base):
    """Evidence provenance captured by a future retrieval operation."""

    __tablename__ = "retrieved_sources"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            name="fk_retrieved_sources_organization_case",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workflow_run_id"],
            ["workflow_runs.organization_id", "workflow_runs.id"],
            name="fk_retrieved_sources_organization_workflow_run",
        ),
        ForeignKeyConstraint(
            ["organization_id", "document_id"],
            ["documents.organization_id", "documents.id"],
            name="fk_retrieved_sources_organization_document",
        ),
        ForeignKeyConstraint(
            ["organization_id", "chunk_id"],
            ["document_chunks.organization_id", "document_chunks.id"],
            name="fk_retrieved_sources_organization_chunk",
        ),
        CheckConstraint("rank >= 0", name="rank_nonnegative"),
        Index("ix_retrieved_sources_organization_case", "organization_id", "case_id"),
        Index("ix_retrieved_sources_workflow_run_id", "workflow_run_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    case_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    workflow_run_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    document_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    chunk_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    retrieval_method: Mapped[str] = mapped_column(String(100), nullable=False)
    excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    citation_label: Mapped[str] = mapped_column(Text, nullable=False)

    document: Mapped[Document] = relationship(
        foreign_keys=[organization_id, document_id], lazy="raise", viewonly=True
    )
    chunk: Mapped[DocumentChunk] = relationship(
        foreign_keys=[organization_id, chunk_id], lazy="raise", viewonly=True
    )


class ExtractedField(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A structured field extraction with optional source-chunk provenance."""

    __tablename__ = "extracted_fields"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            name="fk_extracted_fields_organization_case",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workflow_run_id"],
            ["workflow_runs.organization_id", "workflow_runs.id"],
            name="fk_extracted_fields_organization_workflow_run",
        ),
        ForeignKeyConstraint(
            ["organization_id", "source_chunk_id"],
            ["document_chunks.organization_id", "document_chunks.id"],
            name="fk_extracted_fields_organization_source_chunk",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    case_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    workflow_run_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    field_name: Mapped[str] = mapped_column(String(255), nullable=False)
    field_value: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    source_chunk_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    human_edited: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )


class RiskAssessment(UUIDPrimaryKeyMixin, InsertedAtMixin, Base):
    """Persisted risk signals; assessment policy is introduced later."""

    __tablename__ = "risk_assessments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            name="fk_risk_assessments_organization_case",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workflow_run_id"],
            ["workflow_runs.organization_id", "workflow_runs.id"],
            name="fk_risk_assessments_organization_workflow_run",
        ),
        UniqueConstraint(
            "organization_id",
            "workflow_run_id",
            name="uq_risk_assessments_organization_workflow_run",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    case_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    workflow_run_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(50), nullable=False)
    risk_reasons: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    pii_detected: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    prompt_injection_detected: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    weak_evidence: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    high_impact_action: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    requires_approval: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )


class Approval(UUIDPrimaryKeyMixin, InsertedAtMixin, Base):
    """Human decision record preserving AI and final text separately."""

    __tablename__ = "approvals"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            name="fk_approvals_organization_case",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workflow_run_id"],
            ["workflow_runs.organization_id", "workflow_runs.id"],
            name="fk_approvals_organization_workflow_run",
        ),
        ForeignKeyConstraint(
            ["organization_id", "reviewer_user_id"],
            ["users.organization_id", "users.id"],
            name="fk_approvals_organization_reviewer_user",
        ),
        ForeignKeyConstraint(
            ["organization_id", "assigned_user_id"],
            ["users.organization_id", "users.id"],
            name="fk_approvals_organization_assigned_user",
        ),
        ForeignKeyConstraint(
            ["organization_id", "drafting_workflow_run_id"],
            ["workflow_runs.organization_id", "workflow_runs.id"],
            name="fk_approvals_organization_drafting_workflow_run",
        ),
        ForeignKeyConstraint(
            ["risk_assessment_id"],
            ["risk_assessments.id"],
            name="fk_approvals_risk_assessment_id",
        ),
        UniqueConstraint(
            "organization_id", "workflow_run_id", name="uq_approvals_organization_workflow_run"
        ),
        CheckConstraint(
            "status IN ('pending', 'assigned', 'approved', 'rejected', 'needs_more_evidence')",
            name="approval_status_valid",
        ),
        CheckConstraint(
            "decision IS NULL OR decision IN "
            "('approve', 'edit_and_approve', 'reject', 'request_more_evidence')",
            name="approval_decision_valid",
        ),
        Index(
            "ix_approvals_organization_status_assigned_inserted",
            "organization_id",
            "status",
            "assigned_user_id",
            "inserted_at",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    case_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    workflow_run_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    reviewer_user_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    assigned_user_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    drafting_workflow_run_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    risk_assessment_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default=text("'pending'")
    )
    decision: Mapped[str | None] = mapped_column(String(50))
    reviewer_comment: Mapped[str | None] = mapped_column(Text)
    ai_draft: Mapped[str | None] = mapped_column(Text)
    final_text: Mapped[str | None] = mapped_column(Text)
    decision_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    interrupted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
