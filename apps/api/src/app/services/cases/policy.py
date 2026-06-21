"""Pure Case lifecycle policy with no HTTP, SQLAlchemy, or audit dependencies."""

from __future__ import annotations

from app.services.errors import InvalidCommandError

_TRANSITIONS: dict[str, frozenset[str]] = {
    "new": frozenset({"processing"}),
    "processing": frozenset(
        {"waiting_for_human_review", "needs_more_evidence", "completed", "failed"}
    ),
    "waiting_for_human_review": frozenset({"approved", "rejected", "needs_more_evidence"}),
    "needs_more_evidence": frozenset({"processing"}),
    "approved": frozenset({"completed"}),
    "rejected": frozenset(),
    "completed": frozenset(),
    "failed": frozenset({"processing"}),
    "archived": frozenset(),
}

_APPROVAL_STATUSES = frozenset(
    {"waiting_for_human_review", "approved", "rejected", "needs_more_evidence"}
)


def validate_case_transition(current_status: str, target_status: str) -> None:
    """Reject all non-table lifecycle changes before any persistence is staged."""

    if target_status == "archived" or target_status not in _TRANSITIONS.get(
        current_status, frozenset()
    ):
        raise InvalidCommandError("The requested case status transition is not allowed.")


def is_approval_status(status: str) -> bool:
    """Return whether a target status crosses the special reviewer boundary."""

    return status in _APPROVAL_STATUSES
