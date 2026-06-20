"""Closed field taxonomy, value schemas, and durable-safe state for Extraction."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from agent_orchestrator.state.case_state import CaseWorkflowState

_REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{1,99}$")


class ExtractionFieldKind(StrEnum):
    PEOPLE = "people"
    ORGANIZATIONS = "organizations"
    DATES = "dates"
    DEADLINES = "deadlines"
    AMOUNTS = "amounts"
    REFERENCE_NUMBERS = "reference_numbers"
    OBLIGATIONS = "obligations"
    TASKS = "tasks"
    RISKS = "risks"
    MISSING_INFORMATION = "missing_information"
    SUGGESTED_NEXT_ACTIONS = "suggested_next_actions"


class ConfidenceBand(StrEnum):
    HIGH = "high"
    LOW = "low"


class StringItemsValue(BaseModel):
    """Bounded normalized text observations for closed list-like field kinds."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    items: tuple[Annotated[str, Field(min_length=1, max_length=500)], ...] = Field(
        min_length=1, max_length=12
    )

    @field_validator("items")
    @classmethod
    def _unique_items(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(" ".join(item.split()) for item in value)
        if any(not item for item in normalized) or len(
            {item.casefold() for item in normalized}
        ) != len(normalized):
            raise ValueError("items must be non-empty and unique")
        return normalized


class DatesValue(BaseModel):
    """Calendar-only values prevent a provider from introducing an ambiguous timestamp."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dates: tuple[date, ...] = Field(min_length=1, max_length=12)

    @field_validator("dates")
    @classmethod
    def _unique_dates(cls, value: tuple[date, ...]) -> tuple[date, ...]:
        if len(set(value)) != len(value):
            raise ValueError("dates must be unique")
        return tuple(sorted(value))


class AmountItem(BaseModel):
    """A non-negative monetary observation with a closed ISO-like currency code."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    amount: Annotated[Decimal, Field(ge=0, max_digits=16, decimal_places=2)]
    currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
    label: Annotated[str | None, Field(default=None, max_length=160)] = None


class AmountsValue(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    amounts: tuple[AmountItem, ...] = Field(min_length=1, max_length=12)


class ReferencesValue(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    references: tuple[Annotated[str, Field(min_length=2, max_length=100)], ...] = Field(
        min_length=1, max_length=12
    )

    @field_validator("references")
    @classmethod
    def _valid_references(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(item.strip().upper() for item in value)
        if any(_REFERENCE.fullmatch(item) is None for item in normalized):
            raise ValueError("references must use the normalized reference format")
        if len(set(normalized)) != len(normalized):
            raise ValueError("references must be unique")
        return normalized


ExtractionValue = StringItemsValue | DatesValue | AmountsValue | ReferencesValue

_STRING_ITEM_KINDS = frozenset(
    {
        ExtractionFieldKind.PEOPLE,
        ExtractionFieldKind.ORGANIZATIONS,
        ExtractionFieldKind.OBLIGATIONS,
        ExtractionFieldKind.TASKS,
        ExtractionFieldKind.RISKS,
        ExtractionFieldKind.MISSING_INFORMATION,
        ExtractionFieldKind.SUGGESTED_NEXT_ACTIONS,
    }
)


class ExtractionProviderField(BaseModel):
    """Untrusted structured-model shape. Its value is validated by kind in the next node."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: ExtractionFieldKind
    value: dict[str, object]
    source_citation: Annotated[str, Field(pattern=r"^S[1-9][0-9]*$", max_length=16)]
    confidence: Annotated[float, Field(ge=0, le=1)]


class ExtractionProviderOutput(BaseModel):
    """Closed provider response: no rationale, prompt, tool, or arbitrary top-level fields."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    fields: tuple[ExtractionProviderField, ...] = Field(default=(), max_length=11)


class ValidatedExtractionField(BaseModel):
    """Private validated output passed to persistence, never serialized into workflow state."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: ExtractionFieldKind
    value: ExtractionValue
    source_citation: str
    source_chunk_id: UUID
    confidence: Annotated[float, Field(ge=0, le=1)]
    confidence_band: ConfidenceBand


class ExtractionWorkflowState(CaseWorkflowState):
    """Only counts/bands/schema labels survive in snapshots and node summaries."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    extraction_schema: Annotated[str, Field(min_length=1, max_length=80)] = "conservative"
    evidence_available: bool = True
    node_count: Annotated[int, Field(ge=0, le=5)] = 0
    extracted_field_count: Annotated[int, Field(ge=0, le=11)] = 0
    low_confidence_field_count: Annotated[int, Field(ge=0, le=11)] = 0


def validate_extraction_value(
    kind: ExtractionFieldKind, value: dict[str, object]
) -> ExtractionValue:
    """Validate an untrusted JSON object against exactly one server-owned value schema."""

    model: type[ExtractionValue]
    if kind in _STRING_ITEM_KINDS:
        model = StringItemsValue
    elif kind in {ExtractionFieldKind.DATES, ExtractionFieldKind.DEADLINES}:
        model = DatesValue
    elif kind is ExtractionFieldKind.AMOUNTS:
        model = AmountsValue
    elif kind is ExtractionFieldKind.REFERENCE_NUMBERS:
        model = ReferencesValue
    else:  # Exhaustive closed enum guard for future additions.
        raise ValueError("unsupported extraction field kind")
    parsed = model.model_validate(value)
    return parsed


def value_matches_kind(kind: ExtractionFieldKind, value: ExtractionValue) -> bool:
    """Keep API edits and provider validation from mixing otherwise valid field shapes."""

    if kind in _STRING_ITEM_KINDS:
        return isinstance(value, StringItemsValue)
    if kind in {ExtractionFieldKind.DATES, ExtractionFieldKind.DEADLINES}:
        return isinstance(value, DatesValue)
    if kind is ExtractionFieldKind.AMOUNTS:
        return isinstance(value, AmountsValue)
    return kind is ExtractionFieldKind.REFERENCE_NUMBERS and isinstance(value, ReferencesValue)


def serialized_value(value: ExtractionValue) -> dict[str, object]:
    """Return JSON-compatible business data for the dedicated ExtractedField row only."""

    return value.model_dump(mode="json")
