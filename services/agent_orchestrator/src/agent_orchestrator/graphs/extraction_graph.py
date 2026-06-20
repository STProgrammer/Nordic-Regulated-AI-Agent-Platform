"""The explicit five-node, evidence-backed Extraction LangGraph."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID

from agent_orchestrator.errors import ControlledWorkflowError, InvalidModelOutputError
from agent_orchestrator.graphs.extraction_types import (
    ConfidenceBand,
    ExtractionProviderOutput,
    ExtractionWorkflowState,
    ValidatedExtractionField,
    validate_extraction_value,
)
from agent_orchestrator.graphs.runtime import GraphNode, GraphRunResult, GraphRuntime
from agent_orchestrator.model_providers.base import StructuredModelProvider, StructuredModelRequest
from agent_orchestrator.persistence.ports import WorkflowPersistence
from agent_orchestrator.prompts.base import PromptLoader
from agent_orchestrator.types import RetryPolicy, WorkflowContext


@dataclass(frozen=True)
class ExtractionCaseInput:
    """Transient server-loaded case fields; no browser data is part of an extraction graph."""

    title: str
    description: str
    case_type: str | None
    domain: str
    language: str


@dataclass(frozen=True)
class ExtractionEvidenceSource:
    """Trusted source text from one eligible Evidence run, kept out of graph state."""

    citation_label: str
    chunk_id: UUID
    excerpt: str


PersistExtractedFields = Callable[
    [WorkflowContext, ExtractionWorkflowState, tuple[ValidatedExtractionField, ...]],
    Awaitable[None],
]


@dataclass(frozen=True)
class ExtractionGraphDependencies:
    case_input: ExtractionCaseInput
    evidence_sources: tuple[ExtractionEvidenceSource, ...]
    prompt_loader: PromptLoader
    model_provider: StructuredModelProvider
    persistence: WorkflowPersistence
    persist_fields: PersistExtractedFields
    confidence_threshold: float
    retry_policy: RetryPolicy


EXTRACTION_NODE_NAMES: tuple[str, ...] = (
    "select_extraction_schema",
    "extract_fields",
    "validate_structured_output",
    "mark_low_confidence_fields",
    "persist_extracted_fields",
)


class ExtractionGraph:
    """Extract only typed, cited facts from a completed eligible Evidence package."""

    def __init__(self, dependencies: ExtractionGraphDependencies) -> None:
        self._dependencies = dependencies
        self._runtime = GraphRuntime[ExtractionWorkflowState](
            state_model=ExtractionWorkflowState,
            persistence=dependencies.persistence,
            retry_policy=dependencies.retry_policy,
        )
        self._provider_output: ExtractionProviderOutput | None = None
        self._validated: tuple[ValidatedExtractionField, ...] = ()

    async def run(
        self, context: WorkflowContext, initial_state: ExtractionWorkflowState
    ) -> GraphRunResult[ExtractionWorkflowState]:
        return await self._runtime.run(context, initial_state, self._nodes())

    def _nodes(self) -> tuple[GraphNode[ExtractionWorkflowState], ...]:
        return (
            GraphNode("select_extraction_schema", self._select_extraction_schema),
            GraphNode("extract_fields", self._extract_fields),
            GraphNode("validate_structured_output", self._validate_structured_output),
            GraphNode("mark_low_confidence_fields", self._mark_low_confidence_fields),
            GraphNode("persist_extracted_fields", self._persist_extracted_fields),
        )

    async def _select_extraction_schema(self, state: ExtractionWorkflowState) -> dict[str, object]:
        if not self._dependencies.evidence_sources:
            raise ControlledWorkflowError("eligible_evidence_unavailable")
        schema = _schema_name(self._dependencies.case_input)
        return {"extraction_schema": schema, "node_count": state.node_count + 1}

    async def _extract_fields(self, state: ExtractionWorkflowState) -> dict[str, object]:
        prompt = await self._dependencies.prompt_loader.load_active(
            state.context.organization_id, "extraction_fields"
        )
        completion = await self._dependencies.model_provider.complete(
            StructuredModelRequest(
                operation="extraction_fields",
                prompt=prompt,
                input_payload={
                    "case": {
                        "title": self._dependencies.case_input.title,
                        "description": self._dependencies.case_input.description,
                        "case_type": self._dependencies.case_input.case_type,
                        "domain": self._dependencies.case_input.domain,
                        "language": self._dependencies.case_input.language,
                    },
                    "schema": state.extraction_schema,
                    "sources": [
                        {"citation_label": source.citation_label, "excerpt": source.excerpt}
                        for source in self._dependencies.evidence_sources
                    ],
                },
                output_model=ExtractionProviderOutput,
            )
        )
        await self._dependencies.persistence.record_model_usage(state.context, completion.usage)
        self._provider_output = ExtractionProviderOutput.model_validate(completion.output)
        return {"node_count": state.node_count + 1}

    async def _validate_structured_output(
        self, state: ExtractionWorkflowState
    ) -> dict[str, object]:
        if self._provider_output is None:
            raise InvalidModelOutputError()
        source_chunks = {
            source.citation_label: source.chunk_id for source in self._dependencies.evidence_sources
        }
        validated: list[ValidatedExtractionField] = []
        seen: set[tuple[str, str]] = set()
        for field in self._provider_output.fields:
            chunk_id = source_chunks.get(field.source_citation)
            if chunk_id is None:
                raise InvalidModelOutputError()
            key = (field.kind.value, field.source_citation)
            if key in seen:
                raise InvalidModelOutputError()
            seen.add(key)
            try:
                value = validate_extraction_value(field.kind, field.value)
            except ValueError as error:
                raise InvalidModelOutputError() from error
            validated.append(
                ValidatedExtractionField(
                    kind=field.kind,
                    value=value,
                    source_citation=field.source_citation,
                    source_chunk_id=chunk_id,
                    confidence=field.confidence,
                    confidence_band=(
                        ConfidenceBand.HIGH
                        if field.confidence >= self._dependencies.confidence_threshold
                        else ConfidenceBand.LOW
                    ),
                )
            )
        self._validated = tuple(validated)
        return {"extracted_field_count": len(validated), "node_count": state.node_count + 1}

    async def _mark_low_confidence_fields(
        self, state: ExtractionWorkflowState
    ) -> dict[str, object]:
        low_count = sum(field.confidence_band is ConfidenceBand.LOW for field in self._validated)
        return {"low_confidence_field_count": low_count, "node_count": state.node_count + 1}

    async def _persist_extracted_fields(self, state: ExtractionWorkflowState) -> dict[str, object]:
        final_state = state.model_copy(update={"node_count": state.node_count + 1})
        await self._dependencies.persist_fields(state.context, final_state, self._validated)
        return {"node_count": final_state.node_count}


def _schema_name(case: ExtractionCaseInput) -> str:
    """Choose only a closed schema label from trusted stored case metadata."""

    case_type = (case.case_type or "unknown").strip().casefold()
    domain = case.domain.strip().casefold()
    if case_type == "compliance_review" or domain == "banking_compliance":
        return "compliance_v1"
    if case_type == "operational_incident" or domain == "energy_operations":
        return "operations_v1"
    if case_type == "document_intelligence":
        return "document_v1"
    return "conservative_v1"
