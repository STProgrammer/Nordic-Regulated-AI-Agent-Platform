"""Focused runner tests prove pure exact-threshold behavior."""

from __future__ import annotations

import socket

import pytest
from evaluation.contracts import load_canonical_dataset
from evaluation.runners.deterministic import (
    DeterministicScenarioExecutor,
    EvaluationFailureCode,
    evaluate_dataset,
)


def test_canonical_runner_reuses_closed_policy_outcomes_and_passes() -> None:
    report = evaluate_dataset(load_canonical_dataset("nordic-regulated-core-v1"))

    assert report.passed
    assert report.total_cases == 4
    assert report.metric_pass_counts == {
        "retrieval": 4,
        "citation": 4,
        "structural_faithfulness": 4,
        "refusal": 4,
        "risk": 4,
        "routing": 4,
    }
    assert tuple(result.case_key for result in report.results) == tuple(
        sorted(result.case_key for result in report.results)
    )
    assert all(not result.failure_codes for result in report.results)


def test_controlled_mismatch_fails_with_closed_codes() -> None:
    dataset = load_canonical_dataset("nordic-regulated-core-v1")
    first = dataset.cases[0].model_copy(
        update={
            "expected_source_keys": ("different_source",),
            "expected_citation_keys": ("different_source",),
        }
    )
    altered = dataset.model_copy(update={"cases": (first, *dataset.cases[1:])})

    report = evaluate_dataset(altered)
    result = next(item for item in report.results if item.case_key == first.case_key)

    assert not report.passed
    assert result.failure_codes == (
        EvaluationFailureCode.RETRIEVAL_MISMATCH,
        EvaluationFailureCode.CITATION_MISMATCH,
    )


def test_runner_never_reaches_the_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_network(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("the deterministic evaluator must not open a network connection")

    monkeypatch.setattr(socket, "create_connection", fail_network)

    report = evaluate_dataset(
        load_canonical_dataset("nordic-regulated-core-v1"), executor=DeterministicScenarioExecutor()
    )

    assert report.passed
