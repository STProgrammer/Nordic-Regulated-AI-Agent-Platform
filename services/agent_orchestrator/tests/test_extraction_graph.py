"""Offline contracts for the Evidence-backed Phase-19 Extraction graph."""

from __future__ import annotations

import asyncio
from typing import cast
from uuid import UUID, uuid4

from agent_orchestrator.graphs.extraction_graph import (
    EXTRACTION_NODE_NAMES,
    ExtractionCaseInput,
    ExtractionEvidenceSource,
    ExtractionGraph,
    ExtractionGraphDependencies,
)
from agent_orchestrator.graphs.extraction_types import (
    ConfidenceBand,
    ExtractionFieldKind,
    ExtractionWorkflowState,
    ReferencesValue,
    ValidatedExtractionField,
    validate_extraction_value,
)
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
        assert prompt_name == "extraction_fields"
        return EffectivePrompt(
            prompt_id=uuid4(),
            name=prompt_name,
            version="test-v1",
            organization_id=None,
            content="trusted synthetic extraction prompt",
        )


def _context() -> WorkflowContext:
    return WorkflowContext(
        workflow_run_id=uuid4(),
        organization_id=uuid4(),
        case_id=uuid4(),
        initiated_by_user_id=uuid4(),
        workflow_name="extraction",
        workflow_version="phase19-v1",
    )


def test_extraction_graph_uses_only_cited_evidence_and_never_snapshots_values() -> None:
    async def run() -> tuple[MemoryPersistence, tuple[ValidatedExtractionField, ...]]:
        persistence = MemoryPersistence()
        persisted: tuple[ValidatedExtractionField, ...] = ()
        context = _context()
        source = ExtractionEvidenceSource(
            citation_label="S1", chunk_id=uuid4(), excerpt="Private evidence"
        )

        async def persist(
            _context: WorkflowContext,
            _state: ExtractionWorkflowState,
            fields: tuple[ValidatedExtractionField, ...],
        ) -> None:
            nonlocal persisted
            persisted = fields

        graph = ExtractionGraph(
            ExtractionGraphDependencies(
                case_input=ExtractionCaseInput(
                    title="Private case title",
                    description="Private case description",
                    case_type="compliance_review",
                    domain="public_sector",
                    language="nb",
                ),
                evidence_sources=(source,),
                prompt_loader=FixturePromptLoader(),
                model_provider=DeterministicModelProvider(
                    {
                        "extraction_fields": {
                            "fields": [
                                {
                                    "kind": "reference_numbers",
                                    "value": {"references": ["ref-42"]},
                                    "source_citation": "S1",
                                    "confidence": 0.9,
                                }
                            ]
                        }
                    }
                ),
                persistence=persistence,
                persist_fields=persist,
                confidence_threshold=0.8,
                retry_policy=RetryPolicy(),
            )
        )
        result = await graph.run(context, ExtractionWorkflowState(context=context))
        assert result.outcome.status is RuntimeStatus.COMPLETED
        return persistence, persisted

    persistence, fields = asyncio.run(run())
    assert persistence.node_names == list(EXTRACTION_NODE_NAMES)
    assert len(fields) == 1
    assert fields[0].kind is ExtractionFieldKind.REFERENCE_NUMBERS
    assert fields[0].confidence_band is ConfidenceBand.HIGH
    assert isinstance(fields[0].value, ReferencesValue)
    assert fields[0].value.references == ("REF-42",)
    assert persistence.snapshot is not None
    assert "Private case" not in str(persistence.snapshot)
    assert "Private evidence" not in str(persistence.snapshot)
    assert "REF-42" not in str(persistence.snapshot)


def test_closed_field_values_reject_unknown_or_mismatched_shapes() -> None:
    assert validate_extraction_value(
        ExtractionFieldKind.DATES, {"dates": ["2030-01-02"]}
    ).model_dump(mode="json") == {"dates": ["2030-01-02"]}
    for kind, value in (
        (ExtractionFieldKind.REFERENCE_NUMBERS, {"references": ["bad reference with spaces"]}),
        (ExtractionFieldKind.AMOUNTS, {"amounts": [{"amount": "1.00", "currency": "nok"}]}),
        (ExtractionFieldKind.PEOPLE, {"unknown": ["Ada"]}),
    ):
        try:
            validate_extraction_value(kind, cast(dict[str, object], value))
        except ValueError:
            continue
        raise AssertionError("invalid closed value was accepted")
