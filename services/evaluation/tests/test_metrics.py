"""Focused tests for exact deterministic metric primitives."""

from __future__ import annotations

from evaluation.metrics import exact_boolean_score, score_expected_set


def test_set_scores_are_exact_and_expose_precision_and_recall() -> None:
    score = score_expected_set(("source_one", "source_two"), ("source_one", "source_extra"))

    assert score.precision == 0.5
    assert score.recall == 0.5
    assert score.average == 0.5
    assert not score.passed


def test_empty_sets_and_boolean_scoring_are_deterministic() -> None:
    assert score_expected_set((), ()).passed
    assert exact_boolean_score(True, True) == (1.0, True)
    assert exact_boolean_score(True, False) == (0.0, False)
