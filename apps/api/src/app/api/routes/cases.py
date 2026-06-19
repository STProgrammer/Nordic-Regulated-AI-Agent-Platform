"""Cases API boundary.

Stable ownership boundary for case submission, listing, detail, and status
endpoints. No operations are defined yet; case management is implemented in Phase 8.
"""

from fastapi import APIRouter

PREFIX = "/cases"
TAG = "Cases"
DESCRIPTION = (
    "Case management boundary. Operations are added in Phase 8; no endpoints are implemented yet."
)

router = APIRouter()
