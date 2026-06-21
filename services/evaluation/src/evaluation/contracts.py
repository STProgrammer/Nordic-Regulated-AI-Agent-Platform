"""Strict synthetic-only contracts for deterministic evaluation datasets."""

from __future__ import annotations

import hashlib
import json
import re
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal

from agent_orchestrator.graphs.intake_types import IntakeCaseType, SuggestedWorkflow
from pydantic import BaseModel, ConfigDict, Field, model_validator

_KEY = r"^[a-z][a-z0-9_]{2,63}$"
_DATASET_KEY = r"^[a-z][a-z0-9-]{2,63}$"
_VERSION = r"^v[1-9][0-9]*$"
_EMAIL = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b", re.IGNORECASE)
_NORWEGIAN_IDENTIFIER = re.compile(r"\b\d{6}[ -]?\d{5}\b")
_PHONE = re.compile(r"(?<!\d)(?:\+?47[ -]?)?\d{3}[ -]?\d{2}[ -]?\d{3}(?!\d)")
_URL_OR_STORAGE = re.compile(r"(?:https?://|www\.|azure://|s3://|blob://)", re.IGNORECASE)
_SECRET = re.compile(r"\b(?:api[ _-]?key|password|secret|access[ _-]?token)\b", re.IGNORECASE)

LogicalKey = Annotated[str, Field(pattern=_KEY, min_length=3, max_length=64)]
CANONICAL_DATASET_KEYS = ("nordic-regulated-core-v1",)


class EvaluationLocale(StrEnum):
    """The closed language set required for the canonical corpus."""

    NB = "nb"
    EN = "en"


class EvaluationDomain(StrEnum):
    """Synthetic domain labels, deliberately separate from tenant data."""

    PUBLIC_SECTOR = "public_sector"
    BANKING = "banking"
    ENERGY = "energy"
    INTERNAL_POLICY = "internal_policy"


class ExpectedRiskOutcome(StrEnum):
    """Final-risk result or a policy-controlled lack of final assessment."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    NEEDS_MORE_EVIDENCE = "needs_more_evidence"


class EvaluationFixture(BaseModel):
    """Server-owned bounded test signals; no production source or model input exists here."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    retrieved_source_keys: tuple[LogicalKey, ...] = Field(default=(), max_length=8)
    citation_source_keys: tuple[LogicalKey, ...] = Field(default=(), max_length=8)
    supported_answer_criterion_ids: tuple[LogicalKey, ...] = Field(default=(), max_length=8)
    case_type: IntakeCaseType
    low_confidence: bool = False
    pii_detected: bool = False
    sensitive_domain: bool = False
    weak_evidence: bool = False
    contradictory_evidence: bool = False
    missing_required_source: bool = False
    high_impact_action: bool = False
    policy_conflict: bool = False
    prompt_injection_detected: bool = False

    @model_validator(mode="after")
    def validate_logical_source_relationships(self) -> EvaluationFixture:
        _require_unique(self.retrieved_source_keys, "retrieved_source_keys")
        _require_unique(self.citation_source_keys, "citation_source_keys")
        _require_unique(self.supported_answer_criterion_ids, "supported_answer_criterion_ids")
        if not set(self.citation_source_keys).issubset(self.retrieved_source_keys):
            raise ValueError("Fixture citations must refer to retrieved logical sources.")
        return self


class EvaluationCase(BaseModel):
    """One immutable, safe regression scenario and its closed expectations."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    case_key: LogicalKey
    locale: EvaluationLocale
    domain: EvaluationDomain
    query: Annotated[str, Field(min_length=10, max_length=400)]
    expected_answer_criterion_ids: tuple[LogicalKey, ...] = Field(min_length=1, max_length=8)
    expected_source_keys: tuple[LogicalKey, ...] = Field(default=(), max_length=8)
    expected_citation_keys: tuple[LogicalKey, ...] = Field(default=(), max_length=8)
    expect_refusal: bool
    expected_risk_outcome: ExpectedRiskOutcome
    expected_routing_outcome: SuggestedWorkflow
    fixture: EvaluationFixture

    @model_validator(mode="after")
    def validate_expected_relationships(self) -> EvaluationCase:
        _require_unique(self.expected_answer_criterion_ids, "expected_answer_criterion_ids")
        _require_unique(self.expected_source_keys, "expected_source_keys")
        _require_unique(self.expected_citation_keys, "expected_citation_keys")
        if not set(self.expected_citation_keys).issubset(self.expected_source_keys):
            raise ValueError("Expected citations must refer to expected logical sources.")
        if self.expect_refusal:
            if self.expected_source_keys or self.expected_citation_keys:
                raise ValueError("Refusal cases cannot expect source or citation output.")
        elif not self.expected_source_keys or not self.expected_citation_keys:
            raise ValueError("Grounded cases require expected sources and citations.")
        _screen_synthetic_text(self.query)
        return self


class EvaluationDataset(BaseModel):
    """Versioned canonical corpus; content hashing happens after strict validation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["v1"]
    dataset_key: Annotated[str, Field(pattern=_DATASET_KEY, min_length=3, max_length=64)]
    version: Annotated[str, Field(pattern=_VERSION, min_length=2, max_length=16)]
    description: Annotated[str, Field(min_length=10, max_length=240)]
    cases: tuple[EvaluationCase, ...] = Field(min_length=4, max_length=64)

    @model_validator(mode="after")
    def validate_corpus_coverage(self) -> EvaluationDataset:
        _screen_synthetic_text(self.description)
        _require_unique(tuple(case.case_key for case in self.cases), "case_key")
        locales = {case.locale for case in self.cases}
        domains = {case.domain for case in self.cases}
        if locales != {EvaluationLocale.NB, EvaluationLocale.EN}:
            raise ValueError("Dataset must cover Norwegian Bokmal and English.")
        if domains != set(EvaluationDomain):
            raise ValueError("Dataset must cover all required evaluation domains.")
        if not any(case.expect_refusal for case in self.cases):
            raise ValueError("Dataset must include a deterministic refusal case.")
        if not any(case.fixture.pii_detected for case in self.cases):
            raise ValueError("Dataset must include a PII/high-risk policy case.")
        if not any(
            case.expected_routing_outcome is SuggestedWorkflow.EVIDENCE_THEN_DRAFT
            for case in self.cases
        ):
            raise ValueError("Dataset must include a routing-sensitive policy case.")
        return self


def canonical_json(dataset: EvaluationDataset) -> str:
    """Return stable canonical JSON used for deterministic content addressing."""

    return json.dumps(
        dataset.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def dataset_content_hash(dataset: EvaluationDataset) -> str:
    """Return the SHA-256 identity of a validated corpus."""

    return hashlib.sha256(canonical_json(dataset).encode("utf-8")).hexdigest()


def load_dataset(path: Path) -> EvaluationDataset:
    """Load one checked-in JSON corpus; parsing failures remain fail-closed."""

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Evaluation corpus must be a JSON object.")
    return EvaluationDataset.model_validate(raw)


def canonical_dataset_path(dataset_key: str) -> Path:
    """Resolve only checked-in canonical datasets, never caller-owned paths."""

    if not re.fullmatch(_DATASET_KEY, dataset_key):
        raise ValueError("Dataset key is invalid.")
    root = Path(__file__).resolve().parents[4]
    return root / "sample-data" / "evaluation" / f"{dataset_key}.json"


def load_canonical_dataset(dataset_key: str) -> EvaluationDataset:
    """Load the named canonical corpus from the repository-owned dataset directory."""

    path = canonical_dataset_path(dataset_key)
    if not path.is_file():
        raise ValueError("Canonical dataset is unknown.")
    return load_dataset(path)


def _require_unique(values: tuple[str, ...], field_name: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{field_name} must not contain duplicates.")


def _screen_synthetic_text(value: str) -> None:
    if any(
        pattern.search(value)
        for pattern in (_EMAIL, _NORWEGIAN_IDENTIFIER, _PHONE, _URL_OR_STORAGE, _SECRET)
    ):
        raise ValueError(
            "Corpus text must be synthetic and must not include sensitive identifiers."
        )
