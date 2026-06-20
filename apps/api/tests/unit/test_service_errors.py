"""Unit coverage for stable service errors and audit payload validation."""

import pytest
from app.services.audit.service import JSONValue, _safe_json
from app.services.errors import ConflictError, InvalidCommandError, NotFoundError


def test_service_errors_serialize_only_stable_safe_fields() -> None:
    error = ConflictError("Case")

    assert error.as_dict() == {
        "code": "conflict",
        "message": "Case conflicts with existing data.",
    }
    assert NotFoundError("Document").code == "not_found"


@pytest.mark.parametrize("key", ["token", "password", "request_body", "credentials"])
def test_audit_payload_rejects_sensitive_fields(key: str) -> None:
    with pytest.raises(InvalidCommandError) as error:
        _safe_json({key: "not allowed"})

    assert error.value.code == "invalid_command"


def test_audit_payload_accepts_json_safe_data_and_copies_it() -> None:
    original: dict[str, JSONValue] = {
        "summary": ["synthetic", {"count": 2}],
        "approved": True,
    }

    cleaned = _safe_json(original)

    assert cleaned == original
    assert cleaned is not original
