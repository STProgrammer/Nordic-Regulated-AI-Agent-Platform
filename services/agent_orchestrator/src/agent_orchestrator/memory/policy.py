"""Strict payloads and conservative content policy for controlled memory."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator

from agent_orchestrator.graphs.drafting_types import OutputLanguage
from agent_orchestrator.graphs.intake_policy import detect_injection_signals, detect_pii_signals


class MemoryScope(StrEnum):
    USER = "user"
    ORGANIZATION = "organization"


class MemoryType(StrEnum):
    UI_LANGUAGE_PREFERENCE = "ui_language_preference"
    WORKFLOW_PRESENTATION_PREFERENCE = "workflow_presentation_preference"
    APPROVED_TERMINOLOGY = "approved_terminology"
    PROCESS_HINT = "process_hint"


class MemoryOrigin(StrEnum):
    SELF_PREFERENCE = "self_preference"
    ADMIN_APPROVED = "admin_approved"


class MemoryLifecycle(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class MemoryUseOutcome(StrEnum):
    APPLIED = "applied"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


class MemoryPolicyError(ValueError):
    """A safe rejection carrying only a closed reason code."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


_URL_OR_STORAGE_REFERENCE = re.compile(
    r"(?:https?://|s3://|az://|blob\.core\.windows\.net|/documents?/|storage[_ -]?key)",
    re.IGNORECASE,
)
_SECRET = re.compile(
    r"\b(?:api[_ -]?key|access[_ -]?token|bearer\s+\S+|password|secret|credential)\b",
    re.IGNORECASE,
)
_CASE_OR_DOCUMENT_REFERENCE = re.compile(
    r"\b(?:case|sak|document|dokument)[ _:-]?(?:id|#)?[a-f0-9]{6,}\b",
    re.IGNORECASE,
)


class _ClosedPayload(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)


class UserLanguagePreferencePayload(_ClosedPayload):
    language: OutputLanguage


class WorkflowPresentationPreferencePayload(_ClosedPayload):
    workflow: Literal["drafting"]
    style: Literal["plain", "formal"]


class ApprovedTerminologyPayload(_ClosedPayload):
    locale: OutputLanguage
    source_term: Annotated[str, Field(min_length=1, max_length=80)]
    preferred_term: Annotated[str, Field(min_length=1, max_length=80)]

    @field_validator("source_term", "preferred_term")
    @classmethod
    def _safe_term(cls, value: str) -> str:
        _ensure_safe_text(value)
        return value


class ProcessHintPayload(_ClosedPayload):
    category: Literal["drafting_clarity", "workflow_presentation"]
    guidance: Annotated[str, Field(min_length=1, max_length=240)]

    @field_validator("guidance")
    @classmethod
    def _safe_guidance(cls, value: str) -> str:
        _ensure_safe_text(value)
        return value


type MemoryPayload = (
    UserLanguagePreferencePayload
    | WorkflowPresentationPreferencePayload
    | ApprovedTerminologyPayload
    | ProcessHintPayload
)

_PAYLOAD_ADAPTERS: dict[MemoryType, TypeAdapter[MemoryPayload]] = {
    MemoryType.UI_LANGUAGE_PREFERENCE: TypeAdapter(UserLanguagePreferencePayload),
    MemoryType.WORKFLOW_PRESENTATION_PREFERENCE: TypeAdapter(WorkflowPresentationPreferencePayload),
    MemoryType.APPROVED_TERMINOLOGY: TypeAdapter(ApprovedTerminologyPayload),
    MemoryType.PROCESS_HINT: TypeAdapter(ProcessHintPayload),
}

_TYPE_SCOPES: dict[MemoryType, MemoryScope] = {
    MemoryType.UI_LANGUAGE_PREFERENCE: MemoryScope.USER,
    MemoryType.WORKFLOW_PRESENTATION_PREFERENCE: MemoryScope.ORGANIZATION,
    MemoryType.APPROVED_TERMINOLOGY: MemoryScope.ORGANIZATION,
    MemoryType.PROCESS_HINT: MemoryScope.ORGANIZATION,
}


def expected_scope(memory_type: MemoryType) -> MemoryScope:
    """Return the one permitted scope for a closed memory type."""

    return _TYPE_SCOPES[memory_type]


def validate_memory_payload(
    *, memory_scope: MemoryScope, memory_type: MemoryType, payload: object
) -> MemoryPayload:
    """Validate a payload and its scope before it can reach SQL or a store."""

    if expected_scope(memory_type) is not memory_scope:
        raise MemoryPolicyError("scope_type_mismatch")
    _screen_untrusted_strings(payload)
    try:
        value = _PAYLOAD_ADAPTERS[memory_type].validate_python(payload)
    except Exception as error:
        raise MemoryPolicyError("invalid_payload") from error
    if isinstance(value, (ApprovedTerminologyPayload, ProcessHintPayload)):
        # Validators run above. This branch documents that all free text goes
        # through the same conservative screen before it is retained.
        return value
    return value


def payload_as_dict(payload: MemoryPayload) -> dict[str, object]:
    """Return the exact validated structured value stored in both backends."""

    return payload.model_dump(mode="json")


def memory_natural_key(memory_type: MemoryType, payload: MemoryPayload) -> str:
    """Build a bounded deterministic active-entry uniqueness key."""

    if isinstance(payload, UserLanguagePreferencePayload):
        return memory_type.value
    if isinstance(payload, WorkflowPresentationPreferencePayload):
        return f"{memory_type.value}:{payload.workflow}"
    if isinstance(payload, ApprovedTerminologyPayload):
        return f"{memory_type.value}:{payload.locale.value}:{payload.source_term.casefold()}"
    if isinstance(payload, ProcessHintPayload):
        return f"{memory_type.value}:{payload.category}"
    raise MemoryPolicyError("invalid_payload")


class PresentationMemoryContext(BaseModel):
    """Small ephemeral drafting input; it is never a graph state/snapshot model."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    language: OutputLanguage | None = None
    style: Literal["plain", "formal"] | None = None
    terminology: tuple[tuple[str, str], ...] = ()
    process_hints: tuple[str, ...] = ()


def _ensure_safe_text(value: str) -> None:
    """Reject known-sensitive, reference-like, or instruction-like free text."""

    if not value.strip():
        raise MemoryPolicyError("blank_content")
    if detect_pii_signals(value):
        raise MemoryPolicyError("sensitive_content")
    if detect_injection_signals(value):
        raise MemoryPolicyError("prompt_injection_detected")
    if _URL_OR_STORAGE_REFERENCE.search(value):
        raise MemoryPolicyError("storage_reference_detected")
    if _SECRET.search(value):
        raise MemoryPolicyError("credential_content_detected")
    if _CASE_OR_DOCUMENT_REFERENCE.search(value):
        raise MemoryPolicyError("case_reference_detected")


def _screen_untrusted_strings(value: object) -> None:
    """Retain a precise closed rejection code before Pydantic wraps field errors."""

    if isinstance(value, str):
        _ensure_safe_text(value)
    elif isinstance(value, dict):
        for key, item in value.items():
            if isinstance(key, str):
                _ensure_safe_text(key)
            _screen_untrusted_strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _screen_untrusted_strings(item)
