"""Read-side redaction regression tests for the workflow trace projection."""

from app.services.workflows.trace import _final_state
from app.services.workflows.trace_safety import controlled_code, sanitize_metadata

_SENTINEL = "phase23-legacy-secret-must-never-appear"


def test_trace_safety_drops_nested_secret_paths_and_invalid_values() -> None:
    metadata = sanitize_metadata(
        {
            "labels": {"status": "completed", "Authorization": _SENTINEL},
            "provider_response": _SENTINEL,
            "safe_count": 2,
            "nested": {"cookie_value": _SENTINEL},
        }
    )

    assert metadata == {"labels": {"status": "completed"}, "safe_count": 2, "nested": {}}
    assert _SENTINEL not in repr(metadata)
    assert controlled_code("provider_failed") == "provider_failed"
    assert controlled_code(_SENTINEL) is None


def test_trace_final_state_is_an_explicit_allowlist_even_for_unsafe_legacy_rows() -> None:
    final_state = _final_state(
        {
            "status": "completed",
            "reason_codes": ["weak_evidence", "bad code with spaces"],
            "evidence_source_count": 2,
            "draft": _SENTINEL,
            "prompt_content": _SENTINEL,
            "evidence_sources": [{"excerpt": _SENTINEL}],
        }
    )

    assert final_state == {
        "status": "completed",
        "reason_codes": ["weak_evidence"],
        "evidence_source_count": 2,
    }
    assert _SENTINEL not in repr(final_state)
