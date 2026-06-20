"""Offline contracts for the Phase-18 Evidence graph and its default-deny state."""

from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

from agent_orchestrator.graphs.evidence_graph import (
    EVIDENCE_NODE_NAMES,
    EvidenceCandidate,
    EvidenceCandidates,
    EvidenceCaseInput,
    EvidenceGraph,
    EvidenceGraphDependencies,
    EvidencePackage,
)
from agent_orchestrator.graphs.evidence_types import (
    EvidenceOutcome,
    EvidenceReason,
    EvidenceWorkflowState,
)
from agent_orchestrator.types import ModelUsage, RetryPolicy, RuntimeStatus, WorkflowContext


class MemoryPersistence:
    def __init__(self) -> None:
        self.node_names: list[str] = []
        self.completed_snapshot: dict[str, object] | None = None
        self.status: RuntimeStatus | None = None

    async def claim_run(self, context: WorkflowContext) -> bool:
        return True

    async def start_node(
        self,
        context: WorkflowContext,
        *,
        node_name: str,
        input_summary: dict[str, object],
        retry_count: int,
    ) -> UUID:
        self.node_names.append(node_name)
        return uuid4()

    async def finish_node(
        self,
        context: WorkflowContext,
        *,
        node_run_id: UUID,
        status: RuntimeStatus,
        output_summary: dict[str, object],
        duration_ms: int,
        retry_count: int,
        error_code: str | None = None,
    ) -> None:
        return None

    async def complete_run(
        self,
        context: WorkflowContext,
        *,
        status: RuntimeStatus,
        state_snapshot: dict[str, object],
        duration_ms: int,
    ) -> None:
        self.status = status
        self.completed_snapshot = state_snapshot

    async def fail_run(
        self,
        context: WorkflowContext,
        *,
        state_snapshot: dict[str, object],
        duration_ms: int,
        error_code: str,
    ) -> None:
        raise AssertionError(error_code)

    async def record_model_usage(self, context: WorkflowContext, usage: ModelUsage) -> None:
        return None


def _context() -> WorkflowContext:
    return WorkflowContext(
        workflow_run_id=uuid4(),
        organization_id=uuid4(),
        case_id=uuid4(),
        initiated_by_user_id=uuid4(),
        workflow_name="evidence",
        workflow_version="phase18-v1",
    )


def _candidate(*, excerpt: str, rank: int = 1) -> EvidenceCandidate:
    return EvidenceCandidate(
        document_id=uuid4(),
        chunk_id=uuid4(),
        source_status="approved",
        rank=rank,
        rank_score=1.0 / rank,
        retrieval_methods=("semantic", "keyword"),
        excerpt=excerpt,
    )


def test_evidence_graph_runs_all_nodes_and_snapshots_only_safe_source_references() -> None:
    async def run() -> tuple[MemoryPersistence, EvidenceWorkflowState, EvidencePackage]:
        persistence = MemoryPersistence()
        persisted: EvidencePackage | None = None

        async def persist(
            _context: WorkflowContext, _state: EvidenceWorkflowState, package: EvidencePackage
        ) -> None:
            nonlocal persisted
            persisted = package

        source = _candidate(excerpt="Approved synthetic evidence " * 20)
        graph = EvidenceGraph(
            EvidenceGraphDependencies(
                case_input=EvidenceCaseInput(
                    title="Private case title",
                    description="Private case description with demo@example.invalid",
                ),
                retrieve_candidates=lambda _query: _candidates(source),
                persistence=persistence,
                persist_result=persist,
                maximum_sources=5,
                maximum_excerpt_characters=5000,
                minimum_sources=1,
                minimum_excerpt_characters=20,
                retry_policy=RetryPolicy(maximum_retries=1),
            )
        )
        context = _context()
        result = await graph.run(context, EvidenceWorkflowState(context=context))
        assert result.outcome.status is RuntimeStatus.COMPLETED
        assert persisted is not None
        return persistence, result.state, persisted

    persistence, state, package = asyncio.run(run())
    assert persistence.node_names == list(EVIDENCE_NODE_NAMES)
    assert persistence.status is RuntimeStatus.COMPLETED
    assert state.evidence_outcome is EvidenceOutcome.COMPLETED
    assert package.sources[0].citation_label == "S1"
    assert persistence.completed_snapshot is not None
    snapshot = persistence.completed_snapshot
    assert "Private case title" not in str(snapshot)
    assert "demo@example.invalid" not in str(snapshot)
    assert "Approved synthetic evidence" not in str(snapshot)
    assert snapshot["citation_labels"] == ["S1"]
    presentation_sources = snapshot["evidence_sources"]
    assert isinstance(presentation_sources, list)
    assert isinstance(presentation_sources[0], dict)
    assert presentation_sources[0]["citation_label"] == "S1"


def test_weak_or_contradictory_evidence_routes_to_needs_more_evidence() -> None:
    async def run(excerpt: str, *, minimum: int) -> tuple[RuntimeStatus, EvidencePackage]:
        persistence = MemoryPersistence()
        package: EvidencePackage | None = None

        async def persist(
            _context: WorkflowContext, _state: EvidenceWorkflowState, result: EvidencePackage
        ) -> None:
            nonlocal package
            package = result

        graph = EvidenceGraph(
            EvidenceGraphDependencies(
                case_input=EvidenceCaseInput(
                    title="Synthetic", description="Synthetic description"
                ),
                retrieve_candidates=lambda _query: _candidates(_candidate(excerpt=excerpt)),
                persistence=persistence,
                persist_result=persist,
                maximum_sources=5,
                maximum_excerpt_characters=5000,
                minimum_sources=1,
                minimum_excerpt_characters=minimum,
                retry_policy=RetryPolicy(),
            )
        )
        context = _context()
        await graph.run(context, EvidenceWorkflowState(context=context))
        assert persistence.status is not None
        assert package is not None
        return persistence.status, package

    weak_status, weak = asyncio.run(run("short", minimum=200))
    contradictory_status, contradictory = asyncio.run(
        run("Approved evidence [[contradiction]]" * 20, minimum=20)
    )
    assert weak_status is RuntimeStatus.NEEDS_MORE_EVIDENCE
    assert EvidenceReason.INSUFFICIENT_EVIDENCE in weak.reasons
    assert contradictory_status is RuntimeStatus.NEEDS_MORE_EVIDENCE
    assert EvidenceReason.CONTRADICTORY_EVIDENCE in contradictory.reasons


async def _candidates(source: EvidenceCandidate) -> EvidenceCandidates:
    return EvidenceCandidates(vector=(source,), keyword=(source,))
