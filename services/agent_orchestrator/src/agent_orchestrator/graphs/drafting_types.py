"""Closed Drafting output/state models; draft content is deliberately never durable graph state."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from agent_orchestrator.state.case_state import CaseWorkflowState


class DraftKind(StrEnum):
    RESPONSE = "response"
    INTERNAL_RECOMMENDATION = "internal_recommendation"
    SUMMARY = "summary"
    ACTION_PLAN = "action_plan"


class OutputLanguage(StrEnum):
    NB = "nb"
    EN = "en"


class DraftProviderOutput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    draft: Annotated[str, Field(min_length=1, max_length=8_000)]
    language: OutputLanguage


class DraftingWorkflowState(CaseWorkflowState):
    model_config = ConfigDict(frozen=True, extra="forbid")

    draft_kind: DraftKind = DraftKind.RESPONSE
    draft_available: bool = False
    citation_count: Annotated[int, Field(ge=0, le=20)] = 0
    unsupported_claims_detected: bool = False
    node_count: Annotated[int, Field(ge=0, le=6)] = 0
    memory_enabled: bool = False
    memory_considered_count: Annotated[int, Field(ge=0, le=4)] = 0
    memory_applied_count: Annotated[int, Field(ge=0, le=4)] = 0
    memory_outcome_codes: tuple[str, ...] = ()
