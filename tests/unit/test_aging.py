"""Phase 4 gate: aging-curve estimation and mover age adjustment.

The methodology fix under test: players decline with age, movers change leagues at
non-random career points, so unadjusted mover deltas conflate aging with league
strength. The curve must recover a known synthetic decline, and the adjustment must
remove exactly that decline from a mover's delta.
"""

import numpy as np
import pandas as pd
import pytest

from src.calibration.aging import (
    age_adjust_log_ratios,
    estimate_aging_curve,
    expected_age_change,
    within_league_pairs,
)

METRIC = "goals_added_raw_per90"


def _synthetic_person_seasons(n_players=300, seed=3) -> pd.DataFrame:
    """Players age 22->34 in one league; metric multiplies by exp(-0.06) every year
    after turning 29, flat before. Enough players that bucket shrinkage is mild."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n_players):
        birth_year = 1990
        level = float(rng.uniform(0.2, 0.6))
        for season in range(2012, 2025):
            age = season - birth_year
            if age > 29:
                level *= float(np.exp(-0.06))
            rows.append({"person_id": f"p{i}", "league": "MLS", "season": season,
                         "minutes": 2000.0, "birth_year": birth_year,
                         METRIC: level * float(np.exp(rng.normal(0, 0.02)))})
    return pd.DataFrame(rows)


@pytest.mark.gate_phase4
def test_curve_recovers_synthetic_decline():
    ps = _synthetic_person_seasons()
    curve = estimate_aging_curve(within_league_pairs(ps, METRIC))
    by_age = dict(zip(curve["age"], curve["expected_delta_log"]))
    assert by_age[32] == pytest.approx(-0.06, abs=0.02)  # post-peak decline found
    assert abs(by_age[26]) < 0.02                        # flat pre-peak


@pytest.mark.gate_phase4
def test_expected_change_accumulates_across_years():
    curve = pd.DataFrame({"age": [30, 31, 32], "expected_delta_log": [-0.05, -0.06, -0.07],
                          "n": [100, 100, 100]})
    # moving between age-29 and age-32 seasons crosses birthdays 30, 31, 32
    assert expected_age_change(curve, 29, 32) == pytest.approx(-0.18)
    # ages outside the curve contribute no adjustment (no extrapolation)
    assert expected_age_change(curve, 24, 26) == 0.0
    assert np.isnan(expected_age_change(curve, np.nan, 30))


@pytest.mark.gate_phase4
def test_adjustment_removes_aging_from_mover_delta():
    """An old mover whose entire observed drop equals expected aging must come out
    with ~zero adjusted log-ratio (the league did not make them worse - age did)."""
    curve = pd.DataFrame({"age": [31, 32], "expected_delta_log": [-0.08, -0.08],
                          "n": [200, 200]})
    moves = pd.DataFrame([{
        "person_id": "p1", "from_league": "ENG1", "to_league": "MLS",
        "from_season": 2020, "to_season": 2022, "birth_year": 1990.0,
    }])
    ratios = pd.DataFrame([{"person_id": "p1", "from_league": "ENG1",
                            "to_league": "MLS", "log_ratio": -0.16}])
    adjusted = age_adjust_log_ratios(ratios, moves, curve, METRIC)
    assert adjusted.loc[0, "log_ratio"] == pytest.approx(0.0, abs=1e-9)


def _unknown_age_fixture():
    curve = pd.DataFrame({"age": [30], "expected_delta_log": [-0.05], "n": [50]})
    moves = pd.DataFrame([
        {"person_id": "p1", "from_league": "A", "to_league": "B",
         "from_season": 2020, "to_season": 2021, "birth_year": None},
        {"person_id": "p2", "from_league": "A", "to_league": "B",
         "from_season": 2020, "to_season": 2021, "birth_year": 1991.0},
    ])
    ratios = pd.DataFrame([
        {"person_id": "p1", "from_league": "A", "to_league": "B", "log_ratio": 0.1},
        {"person_id": "p2", "from_league": "A", "to_league": "B", "log_ratio": 0.1},
    ])
    return curve, moves, ratios


@pytest.mark.gate_phase4
def test_unknown_age_movers_follow_config(tmp_path, monkeypatch):
    monkeypatch.setattr("src.common.logging.data_path", lambda key: tmp_path)
    curve, moves, ratios = _unknown_age_fixture()

    from src.common.config import load_settings
    base = load_settings()["calibration"]

    monkeypatch.setitem(base, "age_adjust_unknown", "keep")
    kept = age_adjust_log_ratios(ratios, moves, curve, METRIC)
    assert sorted(kept["person_id"]) == ["p1", "p2"]
    # p1 retained with raw delta; p2 adjusted (age-30 birthday crossed: +0.05 back)
    assert kept.set_index("person_id").loc["p1", "log_ratio"] == pytest.approx(0.1)
    assert kept.set_index("person_id").loc["p2", "log_ratio"] == pytest.approx(0.15)

    monkeypatch.setitem(base, "age_adjust_unknown", "exclude")
    excluded = age_adjust_log_ratios(ratios, moves, curve, METRIC)
    assert list(excluded["person_id"]) == ["p2"]
