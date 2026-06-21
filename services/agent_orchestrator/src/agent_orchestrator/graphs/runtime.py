"""LangGraph-backed runtime with safe persistence and bounded retries."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Literal, TypeVar, cast

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, ValidationError

from agent_orchestrator.errors import ControlledWorkflowError
from agent_orchestrator.observability import AgentTelemetry, get_agent_telemetry
from agent_orchestrator.persistence.ports import WorkflowPersistence
from agent_orchestrator.state.snapshots import node_summary, state_snapshot
from agent_orchestrator.types import RetryPolicy, RuntimeStatus, TerminalOutcome, WorkflowContext

StateModel = TypeVar("StateModel", bound=BaseModel)
NodeHandler = Callable[[StateModel], Awaitable[Mapping[str, object]]]


@dataclass(frozen=True)
class GraphNode[StateModel: BaseModel]:
    """One named, typed state transition in a server-built workflow graph."""

    name: str
    handler: NodeHandler[StateModel]


@dataclass(frozen=True)
class GraphRunResult[StateModel: BaseModel]:
    """Terminal state and a controlled outcome; no raw error details."""

    state: StateModel
    outcome: TerminalOutcome


class GraphRuntime[StateModel: BaseModel]:
    """Execute an ordered LangGraph while persisting its safe lifecycle projection."""

    def __init__(
        self,
        *,
        state_model: type[StateModel],
        persistence: WorkflowPersistence,
        retry_policy: RetryPolicy,
    ) -> None:
        self._state_model = state_model
        self._persistence = persistence
        self._retry_policy = retry_policy

    async def run(
        self,
        context: WorkflowContext,
        initial_state: StateModel,
        nodes: tuple[GraphNode[StateModel], ...],
        *,
        claim_mode: Literal["queued", "paused"] = "queued",
    ) -> GraphRunResult[StateModel]:
        """Claim one queued/paused run, execute explicit edges, and persist its outcome."""

        telemetry = get_agent_telemetry()
        with telemetry.span("workflow.run", {"workflow.name": context.workflow_name}):
            return await self._run(
                context,
                initial_state,
                nodes,
                claim_mode=claim_mode,
                telemetry=telemetry,
            )

    async def _run(
        self,
        context: WorkflowContext,
        initial_state: StateModel,
        nodes: tuple[GraphNode[StateModel], ...],
        *,
        claim_mode: Literal["queued", "paused"],
        telemetry: AgentTelemetry,
    ) -> GraphRunResult[StateModel]:
        """Execute the graph after the process has installed its telemetry adapter."""

        started = time.monotonic()
        claimed = (
            await self._persistence.claim_run(context)
            if claim_mode == "queued"
            else await self._persistence.claim_paused_run(context)
        )
        if not claimed:
            telemetry.workflow_run(workflow_name=context.workflow_name, outcome="failed")
            return GraphRunResult(
                state=initial_state,
                outcome=TerminalOutcome(status=RuntimeStatus.FAILED, error_code="run_not_claimed"),
            )
        graph = StateGraph(self._state_model)
        previous = START
        for node in nodes:
            # LangGraph's generic node overload cannot express a runtime-selected
            # Pydantic subclass despite the handler accepting that exact state model.
            graph.add_node(node.name, self._wrapped_node(context, node, telemetry))  # type: ignore[call-overload]
            graph.add_edge(previous, node.name)
            previous = node.name
        graph.add_edge(previous, END)
        try:
            compiled = graph.compile()
            final_raw = await compiled.ainvoke(initial_state)
            final_state = self._state_model.model_validate(final_raw)
        except ControlledWorkflowError as error:
            failed_state = _failed_state(initial_state)
            await self._persistence.fail_run(
                context,
                state_snapshot=_snapshot(context, failed_state),
                duration_ms=_duration_ms(started),
                error_code=error.code,
            )
            telemetry.workflow_run(workflow_name=context.workflow_name, outcome="failed")
            return GraphRunResult(
                state=failed_state,
                outcome=TerminalOutcome(status=RuntimeStatus.FAILED, error_code=error.code),
            )
        except ValidationError:
            failed_state = _failed_state(initial_state)
            await self._persistence.fail_run(
                context,
                state_snapshot=_snapshot(context, failed_state),
                duration_ms=_duration_ms(started),
                error_code="invalid_state_update",
            )
            telemetry.workflow_run(workflow_name=context.workflow_name, outcome="failed")
            return GraphRunResult(
                state=failed_state,
                outcome=TerminalOutcome(
                    status=RuntimeStatus.FAILED, error_code="invalid_state_update"
                ),
            )
        except Exception:
            failed_state = _failed_state(initial_state)
            await self._persistence.fail_run(
                context,
                state_snapshot=_snapshot(context, failed_state),
                duration_ms=_duration_ms(started),
                error_code="runtime_failure",
            )
            telemetry.workflow_run(workflow_name=context.workflow_name, outcome="failed")
            return GraphRunResult(
                state=failed_state,
                outcome=TerminalOutcome(status=RuntimeStatus.FAILED, error_code="runtime_failure"),
            )
        final_status = getattr(final_state, "status", RuntimeStatus.COMPLETED)
        if final_status is RuntimeStatus.WAITING_FOR_HUMAN_REVIEW:
            paused_state = final_state.model_copy(update={"status": final_status})
            await self._persistence.pause_run(
                context,
                state_snapshot=_snapshot(context, paused_state),
                duration_ms=_duration_ms(started),
            )
            telemetry.workflow_run(
                workflow_name=context.workflow_name,
                outcome=RuntimeStatus.WAITING_FOR_HUMAN_REVIEW.value,
            )
            return GraphRunResult(
                state=paused_state,
                outcome=TerminalOutcome(status=RuntimeStatus.WAITING_FOR_HUMAN_REVIEW),
            )
        terminal_status = (
            RuntimeStatus.NEEDS_MORE_EVIDENCE
            if final_status is RuntimeStatus.NEEDS_MORE_EVIDENCE
            else RuntimeStatus.COMPLETED
        )
        completed_state = final_state.model_copy(update={"status": terminal_status})
        await self._persistence.complete_run(
            context,
            status=terminal_status,
            state_snapshot=_snapshot(context, completed_state),
            duration_ms=_duration_ms(started),
        )
        telemetry.workflow_run(workflow_name=context.workflow_name, outcome=terminal_status.value)
        return GraphRunResult(
            state=completed_state,
            outcome=TerminalOutcome(
                status=cast(
                    Literal[
                        RuntimeStatus.COMPLETED,
                        RuntimeStatus.NEEDS_MORE_EVIDENCE,
                        RuntimeStatus.FAILED,
                    ],
                    terminal_status,
                )
            ),
        )

    def _wrapped_node(
        self, context: WorkflowContext, node: GraphNode[StateModel], telemetry: AgentTelemetry
    ) -> Callable[[StateModel], Awaitable[StateModel]]:
        async def wrapped(raw_state: StateModel) -> StateModel:
            state = self._state_model.model_validate(raw_state)
            retry_count = 0
            while True:
                node_run_id = await self._persistence.start_node(
                    context,
                    node_name=node.name,
                    input_summary=node_summary(state),
                    retry_count=retry_count,
                )
                started = time.monotonic()
                try:
                    with telemetry.span(
                        "workflow.node",
                        {"workflow.name": context.workflow_name, "workflow.node.name": node.name},
                    ):
                        update = dict(await node.handler(state))
                    candidate = self._state_model.model_validate(
                        {**state.model_dump(mode="python"), **update}
                    )
                except ControlledWorkflowError as error:
                    duration = _duration_ms(started)
                    await self._persistence.finish_node(
                        context,
                        node_run_id=node_run_id,
                        status=RuntimeStatus.FAILED,
                        output_summary=node_summary(state, outcome_code=error.code),
                        duration_ms=duration,
                        retry_count=retry_count,
                        error_code=error.code,
                    )
                    telemetry.workflow_node(
                        workflow_name=context.workflow_name,
                        node_name=node.name,
                        outcome="failed",
                        duration_ms=duration,
                    )
                    if (
                        error.retryable
                        and error.code in self._retry_policy.retryable_codes
                        and retry_count < self._retry_policy.maximum_retries
                    ):
                        retry_count += 1
                        continue
                    raise
                except ValidationError as error:
                    duration = _duration_ms(started)
                    await self._persistence.finish_node(
                        context,
                        node_run_id=node_run_id,
                        status=RuntimeStatus.FAILED,
                        output_summary=node_summary(state, outcome_code="invalid_state_update"),
                        duration_ms=duration,
                        retry_count=retry_count,
                        error_code="invalid_state_update",
                    )
                    telemetry.workflow_node(
                        workflow_name=context.workflow_name,
                        node_name=node.name,
                        outcome="failed",
                        duration_ms=duration,
                    )
                    raise ControlledWorkflowError("invalid_state_update") from error
                except Exception as error:
                    duration = _duration_ms(started)
                    await self._persistence.finish_node(
                        context,
                        node_run_id=node_run_id,
                        status=RuntimeStatus.FAILED,
                        output_summary=node_summary(state, outcome_code="node_failed"),
                        duration_ms=duration,
                        retry_count=retry_count,
                        error_code="node_failed",
                    )
                    telemetry.workflow_node(
                        workflow_name=context.workflow_name,
                        node_name=node.name,
                        outcome="failed",
                        duration_ms=duration,
                    )
                    raise ControlledWorkflowError("node_failed") from error
                duration = _duration_ms(started)
                await self._persistence.finish_node(
                    context,
                    node_run_id=node_run_id,
                    status=RuntimeStatus.COMPLETED,
                    output_summary=node_summary(candidate),
                    duration_ms=duration,
                    retry_count=retry_count,
                )
                telemetry.workflow_node(
                    workflow_name=context.workflow_name,
                    node_name=node.name,
                    outcome="completed",
                    duration_ms=duration,
                )
                return candidate

        return wrapped


def _duration_ms(started: float) -> int:
    return max(0, int((time.monotonic() - started) * 1000))


def _failed_state[StateT: BaseModel](state: StateT) -> StateT:
    """Set the shared status when a state model exposes it, otherwise preserve it."""

    if "status" in type(state).model_fields:
        return state.model_copy(update={"status": RuntimeStatus.FAILED})
    return state


def _snapshot(context: WorkflowContext, state: BaseModel) -> dict[str, object]:
    """Add runtime identity metadata through the same explicit snapshot allowlist."""

    return state_snapshot(
        {
            **state.model_dump(mode="json"),
            "workflow_name": context.workflow_name,
            "workflow_version": context.workflow_version,
        }
    )
