"""Users and roles API boundary.

Stable ownership boundary for user and role management endpoints. No operations are
defined yet; user and role management is implemented in Phase 6.
"""

from fastapi import APIRouter

PREFIX = "/users"
TAG = "Users"
DESCRIPTION = (
    "User and role management boundary. Operations are added in Phase 6; no "
    "endpoints are implemented yet."
)

router = APIRouter()
