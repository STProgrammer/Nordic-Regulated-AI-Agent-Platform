"""Strict safe transport schemas for canonical deterministic evaluation history."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EvaluationRunStartRequest(BaseModel):
    """An intentionally empty body: dataset, organization, and execution knobs are server-owned."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class EvaluationReportExportRequest(BaseModel):
    """An intentionally empty body: format, template, and filename stay server-owned."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class EvaluationDatasetData(BaseModel):
    """Global identity only; corpus questions and fixtures are never exposed."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_id: UUID
    dataset_key: str = Field(pattern=r"^[a-z][a-z0-9-]{2,63}$")
    version: str = Field(pattern=r"^v[1-9][0-9]*$")
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    description: str = Field(min_length=1, max_length=240)


class EvaluationDatasetListData(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    items: tuple[EvaluationDatasetData, ...]


class EvaluationRunData(BaseModel):
    """Compact tenant-owned run state with only safe aggregate values."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evaluation_run_id: UUID
    dataset_key: str = Field(pattern=r"^[a-z][a-z0-9-]{2,63}$")
    dataset_version: str = Field(pattern=r"^v[1-9][0-9]*$")
    dataset_content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    status: Literal["queued", "running", "completed", "failed"]
    started_at: datetime
    finished_at: datetime | None
    pass_fail: Literal["pending", "pass", "fail"]
    metrics: EvaluationMetricsData


class EvaluationFailureCodeCountData(BaseModel):
    """One closed, content-free regression code count."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: Literal[
        "retrieval_mismatch",
        "citation_mismatch",
        "criterion_mismatch",
        "refusal_mismatch",
        "risk_mismatch",
        "routing_mismatch",
    ]
    count: int = Field(ge=1)


class EvaluationMetricsData(BaseModel):
    """Allowlisted aggregate values; null means no measurement was recorded."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    case_total: int = Field(ge=0)
    passed_case_total: int = Field(ge=0)
    failed_case_total: int = Field(ge=0)
    retrieval_mean: float | None = Field(default=None, ge=0, le=1)
    citation_mean: float | None = Field(default=None, ge=0, le=1)
    structural_faithfulness_mean: float | None = Field(default=None, ge=0, le=1)
    refusal_mean: float | None = Field(default=None, ge=0, le=1)
    risk_mean: float | None = Field(default=None, ge=0, le=1)
    routing_mean: float | None = Field(default=None, ge=0, le=1)
    average_latency_ms: int | None = Field(default=None, ge=0)
    latency_sample_count: int = Field(ge=0)
    total_cost_estimate: float | None = Field(default=None, ge=0)
    cost_sample_count: int = Field(ge=0)
    failure_code_counts: tuple[EvaluationFailureCodeCountData, ...] = ()
    run_failure_code: (
        Literal[
            "dispatch_unavailable",
            "dataset_not_available",
            "dataset_identity_mismatch",
            "dataset_cases_unavailable",
            "deterministic_runner_failed",
            "worker_runtime_unavailable",
        ]
        | None
    ) = None


class EvaluationResultData(BaseModel):
    """Per-case metrics without question, prompt, text, or source material."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evaluation_result_id: UUID
    case_key: str = Field(pattern=r"^[a-z][a-z0-9_]{2,63}$")
    retrieval_score: float | None = Field(default=None, ge=0, le=1)
    citation_score: float | None = Field(default=None, ge=0, le=1)
    structural_faithfulness_score: float | None = Field(default=None, ge=0, le=1)
    refusal_score: float | None = Field(default=None, ge=0, le=1)
    risk_score: float | None = Field(default=None, ge=0, le=1)
    routing_score: float | None = Field(default=None, ge=0, le=1)
    latency_ms: int | None = Field(default=None, ge=0)
    cost_estimate: float | None = Field(default=None, ge=0)
    passed: bool
    failure_codes: tuple[
        Literal[
            "retrieval_mismatch",
            "citation_mismatch",
            "criterion_mismatch",
            "refusal_mismatch",
            "risk_mismatch",
            "routing_mismatch",
        ],
        ...,
    ] = ()


class EvaluationRunDetailData(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    run: EvaluationRunData
    results: tuple[EvaluationResultData, ...]


class EvaluationRunListData(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    items: tuple[EvaluationRunData, ...]
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
    total: int = Field(ge=0)
    has_more: bool
