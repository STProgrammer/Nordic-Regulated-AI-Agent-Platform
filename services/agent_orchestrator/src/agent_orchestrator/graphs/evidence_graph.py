"""The explicit, typed, server-owned ten-node Evidence LangGraph."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from agent_orchestrator.errors import ControlledWorkflowError
from agent_orchestrator.graphs.evidence_types import (
    EvidenceOutcome,
    EvidencePresentationSource,
    EvidenceReason,
    EvidenceWorkflowState,
)
from agent_orchestrator.graphs.runtime import GraphNode, GraphRunResult, GraphRuntime
from agent_orchestrator.persistence.ports import WorkflowPersistence
from agent_orchestrator.types import RetryPolicy, RuntimeStatus, WorkflowContext

_WHITESPACE = re.compile(r"\s+")
_CONTRADICTION_MARKERS = ("[[contradiction]]", "motstrid", "contradict")


@dataclass(frozen=True)
class EvidenceCaseInput:
    """Transient server-loaded case data; it must never be placed in graph state."""

    title: str
    description: str


@dataclass(frozen=True)
class EvidenceCandidate:
    """Trusted in-memory retrieval data that is deliberately excluded from durable state."""

    document_id: UUID
    chunk_id: UUID
    source_status: str
    rank: int
    rank_score: float
    retrieval_methods: tuple[str, ...]
    excerpt: str
    warning_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvidenceCandidates:
    """Separate candidate sets preserve the graph's explicit vector/keyword nodes."""

    vector: tuple[EvidenceCandidate, ...]
    keyword: tuple[EvidenceCandidate, ...]


@dataclass(frozen=True)
class EvidenceSource:
    """One selected source with its stable run-local citation label."""

    candidate: EvidenceCandidate
    citation_label: str
    excerpt: str


@dataclass(frozen=True)
class EvidencePackage:
    """Private package supplied only to the persistence callback for one graph run."""

    sources: tuple[EvidenceSource, ...]
    outcome: EvidenceOutcome
    reasons: tuple[EvidenceReason, ...]


class EvidenceRetriever(Protocol):
    """Trusted server adapter; callers cannot control query, scope, or source selection."""

    async def __call__(self, query: str) -> EvidenceCandidates: ...


PersistEvidenceResult = Callable[
    [WorkflowContext, EvidenceWorkflowState, EvidencePackage], Awaitable[None]
]


@dataclass(frozen=True)
class EvidenceGraphDependencies:
    """Ports and transient input for one private Evidence execution."""

    case_input: EvidenceCaseInput
    retrieve_candidates: EvidenceRetriever
    persistence: WorkflowPersistence
    persist_result: PersistEvidenceResult
    maximum_sources: int
    maximum_excerpt_characters: int
    minimum_sources: int
    minimum_excerpt_characters: int
    retry_policy: RetryPolicy


EVIDENCE_NODE_NAMES: tuple[str, ...] = (
    "rewrite_query",
    "retrieve_vector_candidates",
    "retrieve_keyword_candidates",
    "merge_candidates",
    "rerank_sources",
    "filter_by_permissions",
    "check_source_status",
    "evaluate_evidence_sufficiency",
    "detect_contradictions",
    "persist_evidence",
)


class EvidenceGraph:
    """Run the fixed Evidence workflow without exposing retrieval controls or content state."""

    def __init__(self, dependencies: EvidenceGraphDependencies) -> None:
        if dependencies.minimum_sources > dependencies.maximum_sources:
            raise ValueError("minimum_sources must not exceed maximum_sources")
        self._dependencies = dependencies
        self._runtime = GraphRuntime[EvidenceWorkflowState](
            state_model=EvidenceWorkflowState,
            persistence=dependencies.persistence,
            retry_policy=dependencies.retry_policy,
        )
        self._candidates: EvidenceCandidates | None = None
        self._merged: tuple[EvidenceCandidate, ...] = ()
        self._ranked: tuple[EvidenceCandidate, ...] = ()
        self._approved: tuple[EvidenceCandidate, ...] = ()
        self._sources: tuple[EvidenceSource, ...] = ()
        self._reasons: tuple[EvidenceReason, ...] = ()

    async def run(
        self, context: WorkflowContext, initial_state: EvidenceWorkflowState
    ) -> GraphRunResult[EvidenceWorkflowState]:
        return await self._runtime.run(context, initial_state, self._nodes())

    def _nodes(self) -> tuple[GraphNode[EvidenceWorkflowState], ...]:
        return (
            GraphNode("rewrite_query", self._rewrite_query),
            GraphNode("retrieve_vector_candidates", self._retrieve_vector_candidates),
            GraphNode("retrieve_keyword_candidates", self._retrieve_keyword_candidates),
            GraphNode("merge_candidates", self._merge_candidates),
            GraphNode("rerank_sources", self._rerank_sources),
            GraphNode("filter_by_permissions", self._filter_by_permissions),
            GraphNode("check_source_status", self._check_source_status),
            GraphNode("evaluate_evidence_sufficiency", self._evaluate_evidence_sufficiency),
            GraphNode("detect_contradictions", self._detect_contradictions),
            GraphNode("persist_evidence", self._persist_evidence),
        )

    async def _rewrite_query(self, state: EvidenceWorkflowState) -> dict[str, object]:
        # Query content is kept only in the dependency closure and is never returned as state.
        if not _server_owned_query(self._dependencies.case_input):
            raise ControlledWorkflowError("invalid_case_input")
        return {"node_count": state.node_count + 1}

    async def _retrieve_vector_candidates(self, state: EvidenceWorkflowState) -> dict[str, object]:
        candidates = await self._load_candidates()
        return {
            "vector_candidate_count": len(candidates.vector),
            "node_count": state.node_count + 1,
        }

    async def _retrieve_keyword_candidates(self, state: EvidenceWorkflowState) -> dict[str, object]:
        candidates = await self._load_candidates()
        return {
            "keyword_candidate_count": len(candidates.keyword),
            "node_count": state.node_count + 1,
        }

    async def _merge_candidates(self, state: EvidenceWorkflowState) -> dict[str, object]:
        candidates = await self._load_candidates()
        by_chunk: dict[UUID, EvidenceCandidate] = {}
        for candidate in (*candidates.vector, *candidates.keyword):
            existing = by_chunk.get(candidate.chunk_id)
            if existing is None or _candidate_key(candidate) < _candidate_key(existing):
                by_chunk[candidate.chunk_id] = candidate
        self._merged = tuple(sorted(by_chunk.values(), key=_candidate_key))
        return {"merged_candidate_count": len(self._merged), "node_count": state.node_count + 1}

    async def _rerank_sources(self, state: EvidenceWorkflowState) -> dict[str, object]:
        # Existing hybrid retrieval has already fused both paths. This fixed tie-break retains
        # that order and prevents caller/model-controlled numeric reranking.
        self._ranked = tuple(sorted(self._merged, key=_candidate_key))[
            : self._dependencies.maximum_sources
        ]
        return {"reranked_source_count": len(self._ranked), "node_count": state.node_count + 1}

    async def _filter_by_permissions(self, state: EvidenceWorkflowState) -> dict[str, object]:
        # The adapter is the primary authorization boundary. The graph repeats the approved-only
        # guard so a malformed adapter result cannot become Evidence.
        permitted = tuple(
            candidate for candidate in self._ranked if candidate.source_status == "approved"
        )
        self._ranked = permitted
        return {"permitted_source_count": len(permitted), "node_count": state.node_count + 1}

    async def _check_source_status(self, state: EvidenceWorkflowState) -> dict[str, object]:
        self._approved = tuple(
            candidate
            for candidate in self._ranked
            if candidate.source_status == "approved" and bool(candidate.excerpt.strip())
        )
        return {"approved_source_count": len(self._approved), "node_count": state.node_count + 1}

    async def _evaluate_evidence_sufficiency(
        self, state: EvidenceWorkflowState
    ) -> dict[str, object]:
        remaining = self._dependencies.maximum_excerpt_characters
        selected: list[EvidenceSource] = []
        for candidate in self._approved:
            if remaining <= 0:
                break
            excerpt = candidate.excerpt[:remaining]
            if not excerpt:
                continue
            selected.append(
                EvidenceSource(
                    candidate=candidate,
                    citation_label=f"S{len(selected) + 1}",
                    excerpt=excerpt,
                )
            )
            remaining -= len(excerpt)
        self._sources = tuple(selected)
        excerpt_characters = sum(len(source.excerpt) for source in self._sources)
        reasons: list[EvidenceReason] = []
        if not self._sources:
            reasons.append(EvidenceReason.NO_ELIGIBLE_SOURCES)
        elif (
            len(self._sources) < self._dependencies.minimum_sources
            or excerpt_characters < self._dependencies.minimum_excerpt_characters
        ):
            reasons.append(EvidenceReason.INSUFFICIENT_EVIDENCE)
        self._reasons = tuple(reasons)
        return {
            "evidence_source_count": len(self._sources),
            "evidence_sufficient": not reasons,
            "citation_labels": tuple(source.citation_label for source in self._sources),
            "evidence_sources": tuple(
                EvidencePresentationSource(
                    citation_label=source.citation_label,
                    document_id=source.candidate.document_id,
                    chunk_id=source.candidate.chunk_id,
                    source_status=source.candidate.source_status,
                    warning_codes=source.candidate.warning_codes,
                )
                for source in self._sources
            ),
            "reason_codes": self._reasons,
            "node_count": state.node_count + 1,
        }

    async def _detect_contradictions(self, state: EvidenceWorkflowState) -> dict[str, object]:
        contradictory = any(
            marker in source.excerpt.casefold()
            for source in self._sources
            for marker in _CONTRADICTION_MARKERS
        )
        reasons = self._reasons + (
            (EvidenceReason.CONTRADICTORY_EVIDENCE,) if contradictory else ()
        )
        self._reasons = reasons
        return {
            "contradiction_detected": contradictory,
            "reason_codes": reasons,
            "node_count": state.node_count + 1,
        }

    async def _persist_evidence(self, state: EvidenceWorkflowState) -> dict[str, object]:
        final_state = state.model_copy(update={"node_count": state.node_count + 1})
        outcome = (
            EvidenceOutcome.COMPLETED if not self._reasons else EvidenceOutcome.NEEDS_MORE_EVIDENCE
        )
        final_state = final_state.model_copy(
            update={
                "evidence_outcome": outcome,
                "status": (
                    RuntimeStatus.COMPLETED
                    if outcome is EvidenceOutcome.COMPLETED
                    else RuntimeStatus.NEEDS_MORE_EVIDENCE
                ),
            }
        )
        await self._dependencies.persist_result(
            state.context,
            final_state,
            EvidencePackage(sources=self._sources, outcome=outcome, reasons=self._reasons),
        )
        return {
            "node_count": final_state.node_count,
            "evidence_outcome": final_state.evidence_outcome,
            "status": final_state.status,
        }

    async def _load_candidates(self) -> EvidenceCandidates:
        if self._candidates is None:
            self._candidates = await self._dependencies.retrieve_candidates(
                _server_owned_query(self._dependencies.case_input)
            )
        return self._candidates


def _server_owned_query(case_input: EvidenceCaseInput) -> str:
    """Bound query construction while treating all case content as untrusted reference text."""

    text = _WHITESPACE.sub(" ", f"{case_input.title} {case_input.description}").strip()
    return text[:2_000]


def _candidate_key(candidate: EvidenceCandidate) -> tuple[int, str, str]:
    return (candidate.rank, str(candidate.document_id), str(candidate.chunk_id))
