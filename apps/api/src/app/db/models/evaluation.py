"""Evaluation dataset, run, and result persistence models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
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
    from app.db.models.workflow import WorkflowRun


class EvalDataset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A global or organization-owned evaluation dataset definition."""

    __tablename__ = "eval_datasets"
    __table_args__ = (
        CheckConstraint("organization_id IS NULL", name="global_only"),
        UniqueConstraint("dataset_key", "dataset_version", name="dataset_key_version"),
    )

    organization_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("organizations.id")
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    dataset_key: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default=text("'legacy'")
    )
    dataset_version: Mapped[str] = mapped_column(String(100), nullable=False)
    content_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default=text("repeat('0', 64)")
    )
    domain: Mapped[str] = mapped_column(String(100), nullable=False)

    cases: Mapped[list[EvalCase]] = relationship(back_populates="dataset", lazy="raise")
    runs: Mapped[list[EvalRun]] = relationship(back_populates="dataset", lazy="raise")


class EvalCase(UUIDPrimaryKeyMixin, InsertedAtMixin, Base):
    """An expected-behavior fixture; execution remains a later phase."""

    __tablename__ = "eval_cases"
    __table_args__ = (
        UniqueConstraint("eval_dataset_id", "case_key", name="dataset_case_key"),
        Index("ix_eval_cases_dataset_case_key", "eval_dataset_id", "case_key"),
    )

    eval_dataset_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("eval_datasets.id"), nullable=False
    )
    case_key: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default=text("'legacy'")
    )
    input_case: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    expected_behavior: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    expected_sources: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    expected_risk_level: Mapped[str | None] = mapped_column(String(50))
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default=text("'{}'::text[]")
    )

    dataset: Mapped[EvalDataset] = relationship(back_populates="cases", lazy="raise")
    results: Mapped[list[EvalResult]] = relationship(back_populates="eval_case", lazy="raise")


class EvalRun(UUIDPrimaryKeyMixin, InsertedAtMixin, Base):
    """One persisted evaluation run summary."""

    __tablename__ = "eval_runs"
    __table_args__ = (
        CheckConstraint("status IN ('queued', 'running', 'completed', 'failed')", name="status"),
        CheckConstraint("pass_fail IN ('pending', 'pass', 'fail')", name="pass_fail"),
        Index(
            "uq_eval_runs_active_organization_dataset",
            "organization_id",
            "eval_dataset_id",
            unique=True,
            postgresql_where=text("status IN ('queued', 'running')"),
        ),
        Index("ix_eval_runs_organization_started", "organization_id", "started_at"),
    )

    organization_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("organizations.id")
    )
    eval_dataset_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("eval_datasets.id"), nullable=False
    )
    dataset_version: Mapped[str] = mapped_column(
        String(100), nullable=False, server_default=text("'legacy'")
    )
    dataset_content_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default=text("repeat('0', 64)")
    )
    run_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    summary_metrics: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    pass_fail: Mapped[str] = mapped_column(String(50), nullable=False)

    dataset: Mapped[EvalDataset] = relationship(back_populates="runs", lazy="raise")
    results: Mapped[list[EvalResult]] = relationship(back_populates="eval_run", lazy="raise")


class EvalResult(UUIDPrimaryKeyMixin, InsertedAtMixin, Base):
    """Per-evaluation-case scores and failure details."""

    __tablename__ = "eval_results"
    __table_args__ = (
        UniqueConstraint("eval_run_id", "eval_case_id", name="run_case"),
        CheckConstraint(
            "risk_score IS NULL OR (risk_score >= 0 AND risk_score <= 1)", name="risk_score_range"
        ),
        CheckConstraint(
            "routing_score IS NULL OR (routing_score >= 0 AND routing_score <= 1)",
            name="routing_score_range",
        ),
    )

    eval_run_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("eval_runs.id"), nullable=False
    )
    eval_case_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("eval_cases.id"), nullable=False
    )
    workflow_run_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("workflow_runs.id")
    )
    retrieval_score: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    citation_score: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    faithfulness_score: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    refusal_score: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    risk_score: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    routing_score: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    cost_estimate: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    failure_reasons: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    eval_run: Mapped[EvalRun] = relationship(back_populates="results", lazy="raise")
    eval_case: Mapped[EvalCase] = relationship(back_populates="results", lazy="raise")
    workflow_run: Mapped[WorkflowRun | None] = relationship(lazy="raise")
