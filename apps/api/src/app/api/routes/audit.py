"""Audit API boundary.

Stable ownership boundary for audit event and trace endpoints. No operations are
defined yet; the audit trail is implemented in Phase 23.
"""

from fastapi import APIRouter

PREFIX = "/audit"
TAG = "Audit"
DESCRIPTION = (
    "Audit event and workflow trace boundary. Operations are added in Phase 23; no "
    "endpoints are implemented yet."
)

router = APIRouter()
