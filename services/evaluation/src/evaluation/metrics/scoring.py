"""Metric primitives with no provider, database, or network dependency."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SetScore:
    """Precision/recall and exact-pass state for an allowlisted logical-key set."""

    precision: float
    recall: float
    passed: bool

    @property
    def average(self) -> float:
        return (self.precision + self.recall) / 2


def score_expected_set(expected: tuple[str, ...], actual: tuple[str, ...]) -> SetScore:
    """Score logical keys deterministically, treating an empty/empty set as complete."""

    expected_set = frozenset(expected)
    actual_set = frozenset(actual)
    if not expected_set and not actual_set:
        return SetScore(precision=1.0, recall=1.0, passed=True)
    true_positives = len(expected_set.intersection(actual_set))
    precision = true_positives / len(actual_set) if actual_set else 0.0
    recall = true_positives / len(expected_set) if expected_set else 0.0
    return SetScore(precision=precision, recall=recall, passed=expected_set == actual_set)


def exact_boolean_score(expected: bool, actual: bool) -> tuple[float, bool]:
    """Return one only for exact deterministic behavior, never a semantic judgement."""

    passed = expected is actual
    return (1.0 if passed else 0.0, passed)
