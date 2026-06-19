"""Documents API boundary.

Stable ownership boundary for document upload, retrieval, chunk, and reindex
endpoints. No operations are defined yet; document handling is implemented across
Phases 10 to 12.
"""

from fastapi import APIRouter

PREFIX = "/documents"
TAG = "Documents"
DESCRIPTION = (
    "Document upload, storage, and indexing boundary. Operations are added across "
    "Phases 10 to 12; no endpoints are implemented yet."
)

router = APIRouter()
