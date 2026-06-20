from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from app.api.schemas.cases import (
    CaseCreateRequest,
    CaseDomain,
    CaseLanguage,
    CasePriority,
    CaseUpdateRequest,
)
from app.services.cases.policy import validate_case_transition
from app.services.cases.service import CasePatch, _patch_event_data
from app.services.errors import InvalidCommandError
from pydantic import ValidationError


@pytest.mark.parametrize(
    ("current", "target"),
    [
        ("new", "processing"),
        ("processing", "waiting_for_human_review"),
        ("processing", "needs_more_evidence"),
        ("processing", "completed"),
        ("processing", "failed"),
        ("waiting_for_human_review", "approved"),
        ("waiting_for_human_review", "rejected"),
        ("waiting_for_human_review", "needs_more_evidence"),
        ("needs_more_evidence", "processing"),
        ("approved", "completed"),
        ("failed", "processing"),
    ],
)
def test_case_lifecycle_accepts_documented_transitions(current: str, target: str) -> None:
    validate_case_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        ("new", "new"),
        ("new", "approved"),
        ("completed", "processing"),
        ("rejected", "processing"),
        ("processing", "archived"),
    ],
)
def test_case_lifecycle_rejects_invalid_or_archive_patch_transitions(
    current: str, target: str
) -> None:
    with pytest.raises(InvalidCommandError):
        validate_case_transition(current, target)


def test_case_input_normalizes_content_and_forbids_system_fields() -> None:
    payload = CaseCreateRequest(
        title="  Synthetic case  ",
        description="  Synthetic description  ",
        domain=CaseDomain.PUBLIC_SECTOR,
        priority=CasePriority.NORMAL,
        language=CaseLanguage.NORWEGIAN_BOKMAL,
        due_date=date(2030, 1, 1),
        external_reference="  SYN-1  ",
    )
    assert payload.title == "Synthetic case"
    assert payload.external_reference == "SYN-1"

    with pytest.raises(ValidationError):
        CaseCreateRequest.model_validate(
            {
                "title": "Case",
                "description": "Description",
                "domain": "public_sector",
                "priority": "normal",
                "language": "nb",
                "organization_id": str(uuid4()),
            }
        )


def test_patch_distinguishes_explicit_null_from_omission() -> None:
    patch = CaseUpdateRequest(assigned_user_id=None, due_date=None)
    assert patch.model_fields_set == {"assigned_user_id", "due_date"}
    with pytest.raises(ValidationError):
        CaseUpdateRequest(title=None)


def test_case_audit_metadata_is_operational_only() -> None:
    patch = CasePatch(description="Updated private business text", assigned_user_id=None)
    data = _patch_event_data(patch, "CASE-SYNTHETIC", "processing", uuid4())

    assert data["case_number"] == "CASE-SYNTHETIC"
    assert data["changed_fields"] == ["description", "assigned_user_id"]
    assert "description" not in data
    assert "title" not in data
    assert "external_reference" not in data
