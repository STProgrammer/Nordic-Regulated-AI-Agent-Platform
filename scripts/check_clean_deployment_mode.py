"""Verify that a migrated database contains no application runtime data."""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import DeclarativeBase

ROOT = Path(__file__).resolve().parents[1]
API_SOURCE = ROOT / "apps" / "api" / "src"
if str(API_SOURCE) not in sys.path:
    sys.path.insert(0, str(API_SOURCE))

from app.core.config import AppSettings, get_settings  # noqa: E402
from app.db.models import (  # noqa: E402
    AgentMessage,
    Approval,
    AuditEvent,
    Case,
    Document,
    DocumentChunk,
    DocumentText,
    EvalCase,
    EvalDataset,
    EvalResult,
    EvalRun,
    ExtractedField,
    MemoryEntry,
    MemoryUsageRecord,
    ModelUsageRecord,
    Organization,
    PromptVersion,
    RetrievedSource,
    RiskAssessment,
    Role,
    User,
    UserRole,
    WorkflowNodeRun,
    WorkflowRun,
    WorkflowToolCall,
)

RuntimeDataModel = type[DeclarativeBase]
RUNTIME_DATA_MODELS: Sequence[tuple[str, RuntimeDataModel]] = (
    ("agent_messages", AgentMessage),
    ("approvals", Approval),
    ("audit_events", AuditEvent),
    ("cases", Case),
    ("document_chunks", DocumentChunk),
    ("document_texts", DocumentText),
    ("documents", Document),
    ("eval_cases", EvalCase),
    ("eval_datasets", EvalDataset),
    ("eval_results", EvalResult),
    ("eval_runs", EvalRun),
    ("extracted_fields", ExtractedField),
    ("memory_entries", MemoryEntry),
    ("memory_usage_records", MemoryUsageRecord),
    ("model_usage_records", ModelUsageRecord),
    ("organizations", Organization),
    ("prompt_versions", PromptVersion),
    ("retrieved_sources", RetrievedSource),
    ("risk_assessments", RiskAssessment),
    ("roles", Role),
    ("user_roles", UserRole),
    ("users", User),
    ("workflow_node_runs", WorkflowNodeRun),
    ("workflow_runs", WorkflowRun),
    ("workflow_tool_calls", WorkflowToolCall),
)


def runtime_data_counts(settings: AppSettings | None = None) -> dict[str, int]:
    """Return row counts only; no runtime record content is read or printed."""

    resolved_settings = settings if settings is not None else get_settings()
    engine = create_engine(resolved_settings.database_sync_url())
    try:
        with engine.connect() as connection:
            return {
                table_name: int(connection.scalar(select(func.count()).select_from(model)) or 0)
                for table_name, model in RUNTIME_DATA_MODELS
            }
    finally:
        engine.dispose()


def is_clean_deployment_mode(counts: dict[str, int]) -> bool:
    """Return whether every persisted application-data table is empty."""

    return not any(counts.values())


def main() -> int:
    """Print a safe machine-readable status and fail when runtime rows exist."""

    try:
        counts = runtime_data_counts()
    except Exception:
        print("Unable to inspect clean deployment data mode.", file=sys.stderr)
        return 2

    clean = is_clean_deployment_mode(counts)
    print(json.dumps({"clean_deployment_data": clean, "table_counts": counts}, sort_keys=True))
    if not clean:
        print("Deployment-ready mode requires an empty application database.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
