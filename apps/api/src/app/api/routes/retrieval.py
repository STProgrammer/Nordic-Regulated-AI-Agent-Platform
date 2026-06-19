"""Retrieval API boundary.

Stable ownership boundary for retrieval search and source-grounded answer
endpoints. No operations are defined yet; retrieval and RAG answering are implemented
across Phases 13 and 15.
"""

from fastapi import APIRouter

PREFIX = "/retrieval"
TAG = "Retrieval"
DESCRIPTION = (
    "Retrieval and source-grounded answering boundary. Operations are added across "
    "Phases 13 and 15; no endpoints are implemented yet."
)

router = APIRouter()
