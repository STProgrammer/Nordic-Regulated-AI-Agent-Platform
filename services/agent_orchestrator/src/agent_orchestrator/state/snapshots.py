"""Default-deny serializers for durable state and node trace projections."""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel

_SCALAR_KEYS = frozenset(
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
        "approval_id",
        "approval_lifecycle",
        "approval_decision",
    }
)
_BOOLEAN_KEYS = frozenset(
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
_CODE_LIST_KEYS = frozenset(
    {
        "reason_codes",
        "classification_reason_codes",
        "pii_categories",
        "prompt_injection_categories",
        "preliminary_risk_reasons",
        "suggested_workflow_reasons",
        "citation_labels",
    }
)
_MAX_CODES = 12
_PRESENTATION_SOURCE_KEYS = frozenset({"evidence_sources"})
_MAX_PRESENTATION_SOURCES = 12


def _mapping(value: Mapping[str, object] | BaseModel) -> Mapping[str, object]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value


def state_snapshot(value: Mapping[str, object] | BaseModel) -> dict[str, object]:
    """Return an explicit allowlist projection, dropping every unknown field."""

    source = _mapping(value)
    safe: dict[str, object] = {}
    for key in _SCALAR_KEYS:
        item = source.get(key)
        if isinstance(item, (str, int)) and not isinstance(item, bool):
            safe[key] = item
    for key in _BOOLEAN_KEYS:
        item = source.get(key)
        if isinstance(item, bool):
            safe[key] = item
    for key in _CODE_LIST_KEYS:
        item = source.get(key)
        if isinstance(item, (list, tuple)):
            safe[key] = [
                code for code in item[:_MAX_CODES] if isinstance(code, str) and len(code) <= 80
            ]
    for key in _PRESENTATION_SOURCE_KEYS:
        item = source.get(key)
        if not isinstance(item, (list, tuple)):
            continue
        sources: list[dict[str, object]] = []
        for source in item[:_MAX_PRESENTATION_SOURCES]:
            if not isinstance(source, Mapping):
                continue
            citation_label = source.get("citation_label")
            document_id = source.get("document_id")
            chunk_id = source.get("chunk_id")
            source_status = source.get("source_status")
            warning_codes = source.get("warning_codes", ())
            if not all(
                isinstance(value, str) and len(value) <= 100
                for value in (citation_label, document_id, chunk_id, source_status)
            ):
                continue
            if not isinstance(warning_codes, (list, tuple)) or not all(
                isinstance(code, str) and len(code) <= 80 for code in warning_codes[:_MAX_CODES]
            ):
                continue
            sources.append(
                {
                    "citation_label": citation_label,
                    "document_id": document_id,
                    "chunk_id": chunk_id,
                    "source_status": source_status,
                    "warning_codes": list(warning_codes[:_MAX_CODES]),
                }
            )
        if sources:
            safe[key] = sources
    return safe


def node_summary(
    value: Mapping[str, object] | BaseModel, *, outcome_code: str | None = None
) -> dict[str, object]:
    """Summarize state shape, never values, for an operational node trace."""

    source = _mapping(value)
    labels: dict[str, str] = {}
    booleans: dict[str, bool] = {}
    counters: dict[str, int] = {}
    for key, item in source.items():
        if key in _SCALAR_KEYS and isinstance(item, str) and len(item) <= 100:
            labels[key] = item
        elif key in _BOOLEAN_KEYS and isinstance(item, bool):
            booleans[key] = item
        elif (
            key.endswith("_count")
            and isinstance(item, int)
            and not isinstance(item, bool)
            and item >= 0
        ):
            counters[key] = item
    summary: dict[str, object] = {"field_names": sorted(source.keys())[:32]}
    if labels:
        summary["labels"] = labels
    if booleans:
        summary["booleans"] = booleans
    if counters:
        summary["counters"] = counters
    if outcome_code is not None:
        summary["outcome_code"] = outcome_code
    return summary
