"""Admin API boundary.

Stable ownership boundary for administrative settings, health, and model-usage
endpoints. No operations are defined yet; administrative endpoints are implemented
by their owning later phases.
"""

from fastapi import APIRouter

PREFIX = "/admin"
TAG = "Admin"
DESCRIPTION = (
    "Administrative settings and operations boundary. Operations are added by their "
    "owning later phases; no endpoints are implemented yet."
)

router = APIRouter()
