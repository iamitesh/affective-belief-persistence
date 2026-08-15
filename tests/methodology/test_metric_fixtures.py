from __future__ import annotations

from itertools import pairwise

import pytest


def _rate(values: list[int]) -> float:
    if not values:
        raise ValueError("a rate needs an eligible denominator")
    return sum(values) / len(values)


def _allocation(spent: list[int], budgets: list[int]) -> float:
    if len(spent) != len(budgets) or not budgets or sum(budgets) == 0:
        raise ValueError("allocation inputs must have the same nonzero denominator")
    return sum(spent) / sum(budgets)


def _positive_excess_auc(focal: list[float], neutral: list[float]) -> float:
    if len(focal) != len(neutral) or not focal:
        raise ValueError("paired nonempty curves are required")
    return sum(max(0.0, a - b) for a, b in zip(focal, neutral, strict=True)) / len(focal)


def _first_two_day_recovery(excess: list[float], threshold: float = 0.10) -> int | None:
    for index, (current, following) in enumerate(pairwise(excess), start=1):
        if current <= threshold and following <= threshold:
            return index
    return None


def test_component_metric_ranges_and_frozen_fixture_values() -> None:
    partner_choice_rate = _rate([1, 0, 1, 1])
    partner_allocation_rate = _allocation([4, 0], [5, 5])
    persistence_auc = _positive_excess_auc([0.6, 0.4, 0.2], [0.1, 0.1, 0.1])

    assert partner_choice_rate == pytest.approx(0.75)
    assert partner_allocation_rate == pytest.approx(0.40)
    assert persistence_auc == pytest.approx(0.30)
    assert all(0.0 <= value <= 1.0 for value in [partner_choice_rate, partner_allocation_rate])


def test_recovery_uses_two_consecutive_days() -> None:
    assert _first_two_day_recovery([0.3, 0.1, 0.08, 0.2]) == 2
    assert _first_two_day_recovery([0.1, 0.2, 0.1]) is None


def test_h5_and_h6_fixtures_point_in_preregistered_direction() -> None:
    reframing_rate = _rate([1, 1, 0, 1])
    blocking_rate = _rate([1, 0, 0, 0])
    h5_difference = reframing_rate - blocking_rate
    h6_gap = 0.50 - 0.10

    assert reframing_rate == pytest.approx(0.75)
    assert h5_difference == pytest.approx(0.50)
    assert h6_gap == pytest.approx(0.40)
    assert h5_difference > 0 and h6_gap > 0


def test_metric_helpers_reject_invalid_denominators() -> None:
    with pytest.raises(ValueError):
        _rate([])
    with pytest.raises(ValueError):
        _allocation([1], [0])
    with pytest.raises(ValueError):
        _positive_excess_auc([], [])
