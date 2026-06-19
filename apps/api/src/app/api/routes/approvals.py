"""Approvals API boundary.

Stable ownership boundary for the approval queue and approve/reject/request-more
endpoints. No operations are defined yet; the human approval workflow is implemented
in Phase 22.
"""

from fastapi import APIRouter

PREFIX = "/approvals"
TAG = "Approvals"
DESCRIPTION = (
    "Human approval workflow boundary. Operations are added in Phase 22; no "
    "endpoints are implemented yet."
)

router = APIRouter()
