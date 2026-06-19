"""Evaluations API boundary.

Stable ownership boundary for evaluation dataset, run, and result endpoints. No
operations are defined yet; evaluation is implemented across Phases 25 and 26.
"""

from fastapi import APIRouter

PREFIX = "/evaluations"
TAG = "Evaluations"
DESCRIPTION = (
    "AI evaluation dataset and run boundary. Operations are added across Phases 25 "
    "and 26; no endpoints are implemented yet."
)

router = APIRouter()
