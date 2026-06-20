"""Prompt-version and model-usage persistence models."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, InsertedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    pass


class PromptVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A global or organization-specific prompt template revision."""

    __tablename__ = "prompt_versions"

    organization_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("organizations.id")
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


class ModelUsageRecord(UUIDPrimaryKeyMixin, InsertedAtMixin, Base):
    """Safe accounting and outcome data for a model-provider invocation."""

    __tablename__ = "model_usage_records"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            name="fk_model_usage_records_organization_case",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workflow_run_id"],
            ["workflow_runs.organization_id", "workflow_runs.id"],
            name="fk_model_usage_records_organization_workflow_run",
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
    case_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    workflow_run_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    operation: Mapped[str] = mapped_column(String(100), nullable=False)
    token_input: Mapped[int | None] = mapped_column(Integer)
    token_output: Mapped[int | None] = mapped_column(Integer)
    cost_estimate: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_summary: Mapped[str | None] = mapped_column(Text)
