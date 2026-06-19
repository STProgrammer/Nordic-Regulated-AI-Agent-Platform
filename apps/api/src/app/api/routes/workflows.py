"""Workflows API boundary.

Stable ownership boundary for workflow run, trace, and cancel endpoints. No
operations are defined yet; workflow orchestration is implemented across the
LangGraph phases (Phase 16 onward).
"""

from fastapi import APIRouter

PREFIX = "/workflows"
TAG = "Workflows"
DESCRIPTION = (
    "Workflow run and trace boundary. Operations are added across the agent "
    "orchestration phases (Phase 16 onward); no endpoints are implemented yet."
)

router = APIRouter()
