"""Tenant-safe assembly of the public workflow trace read model."""

from __future__ import annotations

import math
import re
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.workflows import (
    WorkflowTraceData,
    WorkflowTraceHeaderData,
    WorkflowTraceModelCallData,
    WorkflowTraceNodeData,
    WorkflowTraceSourceData,
    WorkflowTraceToolCallData,
)
from app.db.models.document import Document
from app.db.repositories.case import CaseRepository
from app.db.repositories.workflow import WorkflowTraceRepository, WorkflowTraceSourceRecord
from app.services.auth.policy import (
    CaseAction,
    RetrievalAction,
    authorize_case_action,
    authorize_retrieval_action,
    has_restricted_source_entitlement,
)
from app.services.auth.principal import Principal
from app.services.errors import AuthorizationDeniedError, NotFoundError
from app.services.workflows.trace_safety import controlled_code, sanitize_metadata

_SAFE_FINAL_SCALARS = frozenset(
    {
        "workflow_name",
        "workflow_version",
        "state_schema_version",
        "status",
        "target_language",
        "declared_language",
        "detected_language",
        "classification_case_type",
        "recommended_domain",
        "preliminary_risk_level",
        "suggested_workflow",
        "classification_source",
        "evidence_outcome",
        "extraction_schema",
        "draft_kind",
        "final_risk_level",
        "safe_next_state",
        "approval_lifecycle",
        "approval_decision",
    }
)
_SAFE_FINAL_BOOLEANS = frozenset(
    {
        "approval_required",
        "detected_language_confident",
        "language_mismatch",
        "low_confidence",
        "pii_detected",
        "prompt_injection_detected",
        "evidence_sufficient",
        "contradiction_detected",
        "evidence_available",
        "draft_available",
        "unsupported_claims_detected",
        "sensitive_domain",
        "weak_evidence",
        "missing_required_source",
        "high_impact_action",
        "policy_conflict",
        "requires_approval",
    }
)
_SAFE_FINAL_COUNTS = frozenset(
    {
        "node_count",
        "vector_candidate_count",
        "keyword_candidate_count",
        "merged_candidate_count",
        "reranked_source_count",
        "permitted_source_count",
        "approved_source_count",
        "evidence_source_count",
        "extracted_field_count",
        "low_confidence_field_count",
        "citation_count",
    }
)
_SAFE_FINAL_CODE_LISTS = frozenset(
    {
        "reason_codes",
        "classification_reason_codes",
        "pii_categories",
        "prompt_injection_categories",
        "preliminary_risk_reasons",
        "suggested_workflow_reasons",
    }
)
_DISPLAY_LABEL = re.compile(r"^[A-Za-z0-9_.:-]{1,255}$")
_SOURCE_LABEL = re.compile(r"^S[1-9][0-9]*$")
_SOURCE_METHOD = re.compile(r"^[a-z][a-z0-9_-]{0,99}$")


class WorkflowTraceService:
    """Compose tenant-scoped durable records into an intentionally small trace DTO."""

    def __init__(self, session: AsyncSession) -> None:
        self._records = WorkflowTraceRepository(session)
        self._cases = CaseRepository(session)

    async def get_for_principal(
        self, principal: Principal, workflow_run_id: UUID
    ) -> WorkflowTraceData:
        """Read a trace only for a current-tenant workflow attached to a readable case."""

        authorize_case_action(principal, CaseAction.READ)
        records = await self._records.get(principal.organization_id, workflow_run_id)
        if records is None:
            raise NotFoundError("Workflow run")
        if await self._cases.get(principal.organization_id, records.run.case_id) is None:
            raise NotFoundError("Workflow run")
        source_data, unavailable_source_count = _source_data(principal, records.sources)
        return WorkflowTraceData(
            header=WorkflowTraceHeaderData(
                workflow_run_id=records.run.id,
                workflow_name=_display_label(records.run.workflow_name, maximum=255),
                workflow_version=_display_label(records.run.workflow_version, maximum=100),
                case_id=records.run.case_id,
                status=_display_label(records.run.status, maximum=50),
                started_at=records.run.started_at,
                finished_at=records.run.finished_at,
                duration_ms=_nonnegative_int(records.run.duration_ms),
                total_tokens=_nonnegative_int(records.run.total_tokens),
                total_cost_estimate=_nonnegative_float(records.run.total_cost_estimate),
                final_error_code=controlled_code(records.run.error_summary),
            ),
            final_state=_final_state(records.run.state_snapshot),
            nodes=tuple(
                WorkflowTraceNodeData(
                    node_run_id=node.id,
                    node_name=_display_label(node.node_name, maximum=255),
                    status=_display_label(node.status, maximum=50),
                    started_at=node.started_at,
                    finished_at=node.finished_at,
                    duration_ms=_nonnegative_int(node.duration_ms),
                    retry_count=max(0, node.retry_count),
                    input_summary=sanitize_metadata(node.input_summary),
                    output_summary=sanitize_metadata(node.output_summary),
                    error_code=controlled_code(node.error_summary),
                )
                for node in records.nodes
            ),
            tool_calls=tuple(
                WorkflowTraceToolCallData(
                    tool_call_id=tool_call.id,
                    node_run_id=tool_call.workflow_node_run_id,
                    tool_name=_display_label(tool_call.tool_name, maximum=100),
                    status=_display_label(tool_call.status, maximum=50),
                    started_at=tool_call.started_at,
                    finished_at=tool_call.finished_at,
                    duration_ms=_nonnegative_int(tool_call.duration_ms),
                    retry_count=max(0, tool_call.retry_count),
                    input_summary=sanitize_metadata(tool_call.input_summary),
                    output_summary=sanitize_metadata(tool_call.output_summary),
                    error_code=controlled_code(tool_call.error_summary),
                )
                for tool_call in records.tool_calls
            ),
            model_calls=tuple(
                WorkflowTraceModelCallData(
                    model_usage_id=usage.id,
                    provider=_display_label(usage.provider, maximum=100),
                    model_name=_display_label(usage.model_name, maximum=255),
                    operation=_display_label(usage.operation, maximum=100),
                    success=usage.success,
                    token_input=_nonnegative_int(usage.token_input),
                    token_output=_nonnegative_int(usage.token_output),
                    total_tokens=_total_tokens(usage.token_input, usage.token_output),
                    estimated_cost=_nonnegative_float(usage.cost_estimate),
                    latency_ms=_nonnegative_int(usage.latency_ms),
                    error_code=controlled_code(usage.error_summary),
                )
                for usage in records.model_usage
            ),
            sources=source_data,
            unavailable_source_count=unavailable_source_count,
        )


def _final_state(snapshot: object) -> dict[str, object]:
    """Select known lifecycle labels, booleans, reason codes, and counts only."""

    if not isinstance(snapshot, dict):
        return {}
    safe: dict[str, object] = {}
    for key in _SAFE_FINAL_SCALARS:
        value = snapshot.get(key)
        if isinstance(value, str) and len(value) <= 100:
            safe[key] = value
    for key in _SAFE_FINAL_BOOLEANS:
        value = snapshot.get(key)
        if isinstance(value, bool):
            safe[key] = value
    for key in _SAFE_FINAL_COUNTS:
        value = snapshot.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            safe[key] = value
    for key in _SAFE_FINAL_CODE_LISTS:
        value = snapshot.get(key)
        if isinstance(value, (list, tuple)):
            codes = [item for item in value[:12] if controlled_code(item) is not None]
            if codes:
                safe[key] = codes
    return sanitize_metadata(safe)


def _source_data(
    principal: Principal, source_records: tuple[WorkflowTraceSourceRecord, ...]
) -> tuple[tuple[WorkflowTraceSourceData, ...], int]:
    visible: list[WorkflowTraceSourceData] = []
    unavailable = 0
    for record in source_records:
        if not _source_context_is_currently_readable(principal, record.document):
            unavailable += 1
            continue
        source = record.source
        if (
            _SOURCE_LABEL.fullmatch(source.citation_label) is None
            or _SOURCE_METHOD.fullmatch(source.retrieval_method) is None
        ):
            unavailable += 1
            continue
        visible.append(
            WorkflowTraceSourceData(
                source_status="available",
                citation_label=source.citation_label,
                document_id=source.document_id,
                chunk_id=source.chunk_id,
                rank=source.rank,
                retrieval_method=source.retrieval_method,
            )
        )
    return tuple(visible), unavailable


def _source_context_is_currently_readable(principal: Principal, document: Document | None) -> bool:
    """Mirror the existing source-context role/governance boundary without returning content."""

    if document is None or document.archived_at is not None:
        return False
    try:
        authorize_retrieval_action(principal, RetrievalAction.SEARCH)
    except AuthorizationDeniedError:
        return False
    if document.source_status == "archived":
        return False
    if document.source_status == "restricted":
        return has_restricted_source_entitlement(principal)
    return document.source_status in {"approved", "draft", "deprecated"}


def _display_label(value: object, *, maximum: int) -> str:
    if (
        isinstance(value, str)
        and len(value) <= maximum
        and _DISPLAY_LABEL.fullmatch(value) is not None
    ):
        return value
    return "unavailable"


def _nonnegative_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _nonnegative_float(value: object) -> float | None:
    if isinstance(value, Decimal):
        value = float(value)
    if isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value):
        return float(value) if value >= 0 else None
    return None


def _total_tokens(input_tokens: object, output_tokens: object) -> int | None:
    input_value = _nonnegative_int(input_tokens)
    output_value = _nonnegative_int(output_tokens)
    if input_value is None or output_value is None:
        return None
    return input_value + output_value
