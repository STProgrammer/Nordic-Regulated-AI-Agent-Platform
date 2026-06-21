"""Offline contracts for the Evidence-gated Phase-20 Drafting graph."""

from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

from agent_orchestrator.graphs.drafting_graph import (
    DRAFTING_NODE_NAMES,
    DraftingCaseInput,
    DraftingEvidenceSource,
    DraftingGraph,
    DraftingGraphDependencies,
    ValidatedDraft,
)
from agent_orchestrator.graphs.drafting_types import DraftingWorkflowState, OutputLanguage
from agent_orchestrator.model_providers.deterministic import DeterministicModelProvider
from agent_orchestrator.prompts.base import EffectivePrompt
from agent_orchestrator.types import ModelUsage, RetryPolicy, RuntimeStatus, WorkflowContext


class MemoryPersistence:
    def __init__(self) -> None:
        self.node_names: list[str] = []
        self.snapshot: dict[str, object] | None = None

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
        self.snapshot = state_snapshot

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


class FixturePromptLoader:
    async def load_active(self, organization_id: UUID, prompt_name: str) -> EffectivePrompt:
        assert prompt_name == "drafting_response"
        return EffectivePrompt(
            prompt_id=uuid4(),
            name=prompt_name,
            version="test-v1",
            organization_id=None,
            content="trusted synthetic drafting prompt",
        )


def _context() -> WorkflowContext:
    return WorkflowContext(
        workflow_run_id=uuid4(),
        organization_id=uuid4(),
        case_id=uuid4(),
        initiated_by_user_id=uuid4(),
        workflow_name="drafting",
        workflow_version="phase20-v1",
    )


def _graph(
    persistence: MemoryPersistence,
    draft: str,
    *,
    language: OutputLanguage = OutputLanguage.NB,
    persisted: list[ValidatedDraft] | None = None,
) -> DraftingGraph:
    async def persist(
        _context: WorkflowContext,
        _state: DraftingWorkflowState,
        value: ValidatedDraft,
    ) -> None:
        if persisted is not None:
            persisted.append(value)

    return DraftingGraph(
        DraftingGraphDependencies(
            case_input=DraftingCaseInput(
                title="Private case title",
                description="Private case description",
                language=language,
            ),
            evidence_sources=(
                DraftingEvidenceSource(
                    citation_label="S1", chunk_id=uuid4(), excerpt="Private approved evidence"
                ),
            ),
            prompt_loader=FixturePromptLoader(),
            model_provider=DeterministicModelProvider(
                {"drafting_response": {"draft": draft, "language": language.value}}
            ),
            persistence=persistence,
            persist_draft=persist,
            retry_policy=RetryPolicy(),
        )
    )


def test_drafting_graph_persists_only_cited_original_text_and_safe_snapshot() -> None:
    async def run() -> tuple[MemoryPersistence, list[ValidatedDraft]]:
        persistence = MemoryPersistence()
        persisted: list[ValidatedDraft] = []
        graph = _graph(persistence, "Private approved evidence [S1]", persisted=persisted)
        context = _context()
        result = await graph.run(context, DraftingWorkflowState(context=context))
        assert result.outcome.status is RuntimeStatus.COMPLETED
        return persistence, persisted

    persistence, persisted = asyncio.run(run())
    assert persistence.node_names == list(DRAFTING_NODE_NAMES)
    assert len(persisted) == 1
    assert persisted[0].citation_labels == ("S1",)
    assert persistence.snapshot is not None
    assert persistence.snapshot["draft_available"] is True
    assert "Private approved evidence" not in str(persistence.snapshot)
    assert "Private" not in str(persistence.snapshot)


def test_drafting_graph_rejects_unknown_citations_without_persisting_a_draft() -> None:
    async def run() -> tuple[MemoryPersistence, list[ValidatedDraft]]:
        persistence = MemoryPersistence()
        persisted: list[ValidatedDraft] = []
        graph = _graph(persistence, "Ustøttet utkast [S2]", persisted=persisted)
        context = _context()
        result = await graph.run(context, DraftingWorkflowState(context=context))
        assert result.outcome.status is RuntimeStatus.NEEDS_MORE_EVIDENCE
        return persistence, persisted

    persistence, persisted = asyncio.run(run())
    assert persistence.node_names == list(DRAFTING_NODE_NAMES)
    assert persisted == []
    assert persistence.snapshot is not None
    assert persistence.snapshot["draft_available"] is False
    assert persistence.snapshot["reason_codes"] == ["citation_validation_failed"]


def test_drafting_graph_rejects_claims_not_found_in_their_cited_source() -> None:
    async def run() -> tuple[MemoryPersistence, list[ValidatedDraft]]:
        persistence = MemoryPersistence()
        persisted: list[ValidatedDraft] = []
        graph = _graph(persistence, "Unsupported sentence [S1]", persisted=persisted)
        context = _context()
        result = await graph.run(context, DraftingWorkflowState(context=context))
        assert result.outcome.status is RuntimeStatus.NEEDS_MORE_EVIDENCE
        return persistence, persisted

    persistence, persisted = asyncio.run(run())
    assert persistence.node_names == list(DRAFTING_NODE_NAMES)
    assert persisted == []
    assert persistence.snapshot is not None
    assert persistence.snapshot["reason_codes"] == ["unsupported_claims_detected"]
