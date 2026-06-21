"""The fixed six-node, citation-gated Drafting LangGraph."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID

from agent_orchestrator.errors import InvalidModelOutputError
from agent_orchestrator.graphs.drafting_types import (
    DraftingWorkflowState,
    DraftProviderOutput,
    OutputLanguage,
)
from agent_orchestrator.graphs.runtime import GraphNode, GraphRunResult, GraphRuntime
from agent_orchestrator.model_providers.base import StructuredModelProvider, StructuredModelRequest
from agent_orchestrator.persistence.ports import WorkflowPersistence
from agent_orchestrator.prompts.base import EffectivePrompt, PromptLoader
from agent_orchestrator.types import ModelUsage, RetryPolicy, WorkflowContext

_CITATION = re.compile(r"\[S([1-9][0-9]*)\]")
_POSSIBLE_CITATION = re.compile(r"\[S[^\]]*\]")


@dataclass(frozen=True)
class DraftingCaseInput:
    title: str
    description: str
    language: OutputLanguage


@dataclass(frozen=True)
class DraftingEvidenceSource:
    citation_label: str
    chunk_id: UUID
    excerpt: str


@dataclass(frozen=True)
class ValidatedDraft:
    content: str
    language: OutputLanguage
    citation_labels: tuple[str, ...]
    prompt: EffectivePrompt
    usage: ModelUsage


PersistDraft = Callable[[WorkflowContext, DraftingWorkflowState, ValidatedDraft], Awaitable[None]]


@dataclass(frozen=True)
class DraftingGraphDependencies:
    case_input: DraftingCaseInput
    evidence_sources: tuple[DraftingEvidenceSource, ...]
    prompt_loader: PromptLoader
    model_provider: StructuredModelProvider
    persistence: WorkflowPersistence
    persist_draft: PersistDraft
    retry_policy: RetryPolicy


DRAFTING_NODE_NAMES: tuple[str, ...] = (
    "prepare_context",
    "draft_response",
    "validate_citations",
    "check_unsupported_claims",
    "improve_clarity",
    "persist_draft",
)


class DraftingGraph:
    def __init__(self, dependencies: DraftingGraphDependencies) -> None:
        self._dependencies = dependencies
        self._runtime = GraphRuntime[DraftingWorkflowState](
            state_model=DraftingWorkflowState,
            persistence=dependencies.persistence,
            retry_policy=dependencies.retry_policy,
        )
        self._output: DraftProviderOutput | None = None
        self._prompt: EffectivePrompt | None = None
        self._usage: ModelUsage | None = None
        self._labels: tuple[str, ...] = ()

    async def run(
        self, context: WorkflowContext, initial_state: DraftingWorkflowState
    ) -> GraphRunResult[DraftingWorkflowState]:
        return await self._runtime.run(context, initial_state, self._nodes())

    def _nodes(self) -> tuple[GraphNode[DraftingWorkflowState], ...]:
        return (
            GraphNode("prepare_context", self._prepare_context),
            GraphNode("draft_response", self._draft_response),
            GraphNode("validate_citations", self._validate_citations),
            GraphNode("check_unsupported_claims", self._check_unsupported_claims),
            GraphNode("improve_clarity", self._improve_clarity),
            GraphNode("persist_draft", self._persist_draft),
        )

    async def _prepare_context(self, state: DraftingWorkflowState) -> dict[str, object]:
        if not self._dependencies.evidence_sources:
            return _needs_more_evidence(state, "eligible_evidence_unavailable")
        return {"node_count": state.node_count + 1}

    async def _draft_response(self, state: DraftingWorkflowState) -> dict[str, object]:
        if state.status.value == "needs_more_evidence":
            return {"node_count": state.node_count + 1}
        prompt = await self._dependencies.prompt_loader.load_active(
            state.context.organization_id, "drafting_response"
        )
        completion = await self._dependencies.model_provider.complete(
            StructuredModelRequest(
                operation="drafting_response",
                prompt=prompt,
                input_payload={
                    "case": {
                        "title": self._dependencies.case_input.title,
                        "description": self._dependencies.case_input.description,
                    },
                    "language": self._dependencies.case_input.language.value,
                    "sources": [
                        {"citation_label": source.citation_label, "excerpt": source.excerpt}
                        for source in self._dependencies.evidence_sources
                    ],
                },
                output_model=DraftProviderOutput,
            )
        )
        await self._dependencies.persistence.record_model_usage(state.context, completion.usage)
        candidate = DraftProviderOutput.model_validate(completion.output)
        if candidate.language is not self._dependencies.case_input.language:
            raise InvalidModelOutputError()
        self._output, self._prompt, self._usage = candidate, prompt, completion.usage
        return {"node_count": state.node_count + 1}

    async def _validate_citations(self, state: DraftingWorkflowState) -> dict[str, object]:
        if state.status.value == "needs_more_evidence":
            return {"node_count": state.node_count + 1}
        if self._output is None:
            raise InvalidModelOutputError()
        labels = tuple(f"S{number}" for number in _CITATION.findall(self._output.draft))
        possible_labels = tuple(_POSSIBLE_CITATION.findall(self._output.draft))
        allowed = {source.citation_label for source in self._dependencies.evidence_sources}
        if (
            not labels
            or len(set(labels)) != len(labels)
            or len(possible_labels) != len(labels)
            or not set(labels).issubset(allowed)
        ):
            return _needs_more_evidence(state, "citation_validation_failed")
        self._labels = labels
        return {"citation_count": len(labels), "node_count": state.node_count + 1}

    async def _check_unsupported_claims(self, state: DraftingWorkflowState) -> dict[str, object]:
        if state.status.value == "needs_more_evidence":
            return {"node_count": state.node_count + 1}
        if self._output is None:
            raise InvalidModelOutputError()
        # A conservative deterministic entailment proxy: each cited claim segment must occur in
        # its cited Evidence excerpt. Later evaluation work owns richer semantic assessment.
        unsupported = not _claims_are_source_supported(
            self._output.draft, self._dependencies.evidence_sources
        )
        if unsupported:
            return _needs_more_evidence(state, "unsupported_claims_detected")
        return {"unsupported_claims_detected": False, "node_count": state.node_count + 1}

    async def _improve_clarity(self, state: DraftingWorkflowState) -> dict[str, object]:
        # No free-form second pass: preserving the accepted text guarantees citation correspondence.
        return {"node_count": state.node_count + 1}

    async def _persist_draft(self, state: DraftingWorkflowState) -> dict[str, object]:
        if state.status.value == "needs_more_evidence":
            return {"node_count": state.node_count + 1, "draft_available": False}
        if self._output is None or self._prompt is None or self._usage is None:
            raise InvalidModelOutputError()
        final = state.model_copy(
            update={"node_count": state.node_count + 1, "draft_available": True}
        )
        await self._dependencies.persist_draft(
            state.context,
            final,
            ValidatedDraft(
                self._output.draft,
                self._output.language,
                self._labels,
                self._prompt,
                self._usage,
            ),
        )
        return {"node_count": final.node_count, "draft_available": True}


def _needs_more_evidence(state: DraftingWorkflowState, reason: str) -> dict[str, object]:
    """Keep closure reason codes and no draft text in the durable graph state."""

    return {
        "status": "needs_more_evidence",
        "reason_codes": (reason,),
        "draft_available": False,
        "node_count": state.node_count + 1,
    }


def _claims_are_source_supported(draft: str, sources: tuple[DraftingEvidenceSource, ...]) -> bool:
    """Require each run-local cited text segment to occur in its selected source excerpt."""

    by_label = {source.citation_label: _normalized(source.excerpt) for source in sources}
    previous_end = 0
    for match in _CITATION.finditer(draft):
        label = f"S{match.group(1)}"
        claim = _normalized(draft[previous_end : match.start()])
        source = by_label.get(label)
        if not claim or source is None or claim not in source:
            return False
        previous_end = match.end()
    return not _normalized(draft[previous_end:])


def _normalized(value: str) -> str:
    return " ".join(re.findall(r"\w+", value.casefold()))
