"""The explicit eight-node Intake LangGraph and its trusted dependencies."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from agent_orchestrator.errors import ControlledWorkflowError
from agent_orchestrator.graphs.intake_policy import (
    choose_suggested_workflow,
    detect_injection_signals,
    detect_pii_signals,
    estimate_preliminary_risk,
)
from agent_orchestrator.graphs.intake_types import (
    ClassificationSource,
    ClassifierOutput,
    IntakeLanguage,
    IntakeWorkflowState,
    LanguageDetectionResult,
)
from agent_orchestrator.graphs.runtime import GraphNode, GraphRunResult, GraphRuntime
from agent_orchestrator.model_providers.base import StructuredModelProvider, StructuredModelRequest
from agent_orchestrator.persistence.ports import WorkflowPersistence
from agent_orchestrator.prompts.base import PromptLoader
from agent_orchestrator.types import RetryPolicy, WorkflowContext

LanguageDetector = Callable[[str], LanguageDetectionResult]
PersistIntakeResult = Callable[[WorkflowContext, IntakeWorkflowState], Awaitable[None]]


@dataclass(frozen=True)
class IntakeCaseInput:
    """Transient server-loaded case input; it is not part of graph state or snapshots."""

    title: str
    description: str


@dataclass(frozen=True)
class IntakeGraphDependencies:
    """Ports and transient input required by one private Intake graph execution."""

    case_input: IntakeCaseInput
    prompt_loader: PromptLoader
    model_provider: StructuredModelProvider
    persistence: WorkflowPersistence
    language_detector: LanguageDetector
    persist_result: PersistIntakeResult
    confidence_threshold: float
    retry_policy: RetryPolicy


INTAKE_NODE_NAMES: tuple[str, ...] = (
    "validate_case_input",
    "detect_language",
    "classify_case_type",
    "detect_pii",
    "detect_prompt_injection",
    "estimate_risk",
    "choose_workflow",
    "persist_intake_result",
)


class IntakeGraph:
    """Build and run the only Phase-17 business graph with explicit node order."""

    def __init__(self, dependencies: IntakeGraphDependencies) -> None:
        self._dependencies = dependencies
        self._runtime = GraphRuntime[IntakeWorkflowState](
            state_model=IntakeWorkflowState,
            persistence=dependencies.persistence,
            retry_policy=dependencies.retry_policy,
        )

    async def run(
        self, context: WorkflowContext, initial_state: IntakeWorkflowState
    ) -> GraphRunResult[IntakeWorkflowState]:
        """Run all eight Intake nodes; graph selection and input stay server-owned."""

        return await self._runtime.run(context, initial_state, self._nodes())

    def _nodes(self) -> tuple[GraphNode[IntakeWorkflowState], ...]:
        return (
            GraphNode("validate_case_input", self._validate_case_input),
            GraphNode("detect_language", self._detect_language),
            GraphNode("classify_case_type", self._classify_case_type),
            GraphNode("detect_pii", self._detect_pii),
            GraphNode("detect_prompt_injection", self._detect_prompt_injection),
            GraphNode("estimate_risk", self._estimate_risk),
            GraphNode("choose_workflow", self._choose_workflow),
            GraphNode("persist_intake_result", self._persist_intake_result),
        )

    async def _validate_case_input(self, state: IntakeWorkflowState) -> dict[str, object]:
        title = self._dependencies.case_input.title.strip()
        description = self._dependencies.case_input.description.strip()
        if not 1 <= len(title) <= 500 or not 1 <= len(description) <= 20_000:
            raise ControlledWorkflowError("invalid_case_input")
        return {"node_count": state.node_count + 1}

    async def _detect_language(self, state: IntakeWorkflowState) -> dict[str, object]:
        detected = self._dependencies.language_detector(self._case_text())
        confident = detected.language is not IntakeLanguage.UNKNOWN and detected.confidence >= 0.8
        return {
            "detected_language": detected.language,
            "detected_language_confident": confident,
            "language_mismatch": confident and detected.language != state.declared_language,
            "node_count": state.node_count + 1,
        }

    async def _classify_case_type(self, state: IntakeWorkflowState) -> dict[str, object]:
        prompt = await self._dependencies.prompt_loader.load_active(
            state.context.organization_id, "intake_classification"
        )
        completion = await self._dependencies.model_provider.complete(
            StructuredModelRequest(
                operation="intake_classification",
                prompt=prompt,
                input_payload={
                    "title": self._dependencies.case_input.title,
                    "description": self._dependencies.case_input.description,
                    "declared_language": state.declared_language.value,
                    "submitted_domain": state.submitted_domain.value,
                },
                output_model=ClassifierOutput,
            )
        )
        await self._dependencies.persistence.record_model_usage(state.context, completion.usage)
        classification = ClassifierOutput.model_validate(completion.output)
        return {
            "classification_case_type": classification.case_type,
            "recommended_domain": classification.recommended_domain,
            "classification_confidence": classification.confidence,
            "low_confidence": classification.confidence < self._dependencies.confidence_threshold,
            "classification_reason_codes": classification.reason_codes,
            "classification_source": ClassificationSource.MODEL,
            "node_count": state.node_count + 1,
        }

    async def _detect_pii(self, state: IntakeWorkflowState) -> dict[str, object]:
        categories = detect_pii_signals(self._case_text())
        return {
            "pii_detected": bool(categories),
            "pii_categories": categories,
            "node_count": state.node_count + 1,
        }

    async def _detect_prompt_injection(self, state: IntakeWorkflowState) -> dict[str, object]:
        categories = detect_injection_signals(self._case_text())
        return {
            "prompt_injection_detected": bool(categories),
            "prompt_injection_categories": categories,
            "node_count": state.node_count + 1,
        }

    async def _estimate_risk(self, state: IntakeWorkflowState) -> dict[str, object]:
        risk = estimate_preliminary_risk(
            priority=state.priority,
            detected_language=state.detected_language,
            low_confidence=state.low_confidence,
            pii_detected=state.pii_detected,
            prompt_injection_detected=state.prompt_injection_detected,
        )
        return {
            "preliminary_risk_level": risk.level,
            "preliminary_risk_reasons": risk.reason_codes,
            "approval_required": risk.approval_required,
            "node_count": state.node_count + 1,
        }

    async def _choose_workflow(self, state: IntakeWorkflowState) -> dict[str, object]:
        recommendation = choose_suggested_workflow(
            case_type=state.classification_case_type,
            domain=state.recommended_domain,
            low_confidence=state.low_confidence,
            pii_detected=state.pii_detected,
            prompt_injection_detected=state.prompt_injection_detected,
        )
        return {
            "suggested_workflow": recommendation.workflow,
            "suggested_workflow_reasons": recommendation.reason_codes,
            "node_count": state.node_count + 1,
        }

    async def _persist_intake_result(self, state: IntakeWorkflowState) -> dict[str, object]:
        final_state = state.model_copy(update={"node_count": state.node_count + 1})
        await self._dependencies.persist_result(state.context, final_state)
        return {"node_count": final_state.node_count}

    def _case_text(self) -> str:
        return f"{self._dependencies.case_input.title}\n{self._dependencies.case_input.description}"
