"""Focused contract tests for the checked-in synthetic evaluation corpus."""

from __future__ import annotations

from copy import deepcopy

import pytest
from evaluation.contracts import (
    EvaluationDataset,
    EvaluationDomain,
    EvaluationLocale,
    canonical_dataset_path,
    dataset_content_hash,
    load_canonical_dataset,
)
from pydantic import ValidationError


def test_canonical_dataset_is_complete_synthetic_and_hash_stable() -> None:
    dataset = load_canonical_dataset("nordic-regulated-core-v1")

    assert canonical_dataset_path(dataset.dataset_key).is_file()
    assert {case.locale for case in dataset.cases} == {EvaluationLocale.NB, EvaluationLocale.EN}
    assert {case.domain for case in dataset.cases} == set(EvaluationDomain)
    assert dataset_content_hash(dataset) == dataset_content_hash(
        load_canonical_dataset("nordic-regulated-core-v1")
    )
    assert tuple(case.case_key for case in dataset.cases) == (
        "public_policy_guidance_nb",
        "banking_review_en",
        "energy_weak_evidence_nb",
        "internal_sensitive_route_en",
    )


def test_dataset_rejects_unknown_extra_and_duplicate_case_keys() -> None:
    raw = load_canonical_dataset("nordic-regulated-core-v1").model_dump(mode="json")
    raw["unexpected"] = "not-allowed"
    with pytest.raises(ValidationError, match="unexpected"):
        EvaluationDataset.model_validate(raw)

    duplicate = deepcopy(load_canonical_dataset("nordic-regulated-core-v1").model_dump(mode="json"))
    duplicate["cases"][1]["case_key"] = duplicate["cases"][0]["case_key"]
    with pytest.raises(ValidationError, match="case_key"):
        EvaluationDataset.model_validate(duplicate)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("query", "Please contact training@example.test for this exercise.", "sensitive"),
        ("expected_citation_keys", ["unknown_source"], "Expected citations"),
    ],
)
def test_dataset_rejects_sensitive_text_and_inconsistent_references(
    field: str, value: object, message: str
) -> None:
    raw = deepcopy(load_canonical_dataset("nordic-regulated-core-v1").model_dump(mode="json"))
    raw["cases"][0][field] = value

    with pytest.raises(ValidationError, match=message):
        EvaluationDataset.model_validate(raw)


def test_dataset_rejects_missing_required_coverage() -> None:
    raw = deepcopy(load_canonical_dataset("nordic-regulated-core-v1").model_dump(mode="json"))
    raw["cases"][-1]["domain"] = "energy"

    with pytest.raises(ValidationError, match="all required evaluation domains"):
        EvaluationDataset.model_validate(raw)
