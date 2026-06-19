"""Auth API boundary.

Stable ownership boundary for login, logout, and current-user endpoints. No
operations are defined yet; authentication and sessions are implemented in Phase 6.
"""

from fastapi import APIRouter

PREFIX = "/auth"
TAG = "Auth"
DESCRIPTION = (
    "Authentication and session boundary. Operations (login, logout, current user) "
    "are added in Phase 6; no endpoints are implemented yet."
)

router = APIRouter()
