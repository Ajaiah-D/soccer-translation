"""Phase 5 hard gate: zero label leakage + permutation machinery + verdict rule."""

import numpy as np
import pandas as pd
import pytest

from src.validate.retrodict import (
    FEATURE_COLUMNS,
    _spearman,
    build_features,
    decide_verdict,
    label_outcomes,
    permutation_pvalue,
    split_movers,
)

METRIC = "goals_added_raw_per90"


def _synthetic_moves(n=40, seed=7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    leagues = ["MLS", "USLC", "USL1"]
    rows = []
    for i in range(n):
        a, b = rng.choice(leagues, size=2, replace=False)
        rows.append({
            "person_id": f"p{i}", "player_name": f"Player {i}",
            "from_league": a, "to_league": b,
            "from_season": 2019, "to_season": 2020,
            "from_minutes": float(rng.integers(900, 3000)),
            "to_minutes": float(rng.integers(0, 3000)),
            f"from_{METRIC}": float(rng.uniform(0.05, 0.6)),
            f"to_{METRIC}": float(rng.uniform(0.05, 0.6)),
        })
    return pd.DataFrame(rows)


@pytest.mark.gate_phase5
def test_features_never_read_outcomes():
    """Scrambling every post-move outcome column must not change the features."""
    moves = _synthetic_moves()
    strengths = {"MLS": 0.0, "USLC": -0.3, "USL1": -0.6}
    feats_clean = build_features(moves, strengths, METRIC)

    scrambled = moves.copy()
    rng = np.random.default_rng(0)
    for col in ["to_minutes", f"to_{METRIC}"]:
        scrambled[col] = rng.permutation(scrambled[col].to_numpy())
    feats_scrambled = build_features(scrambled, strengths, METRIC)

    pd.testing.assert_frame_equal(feats_clean, feats_scrambled)


@pytest.mark.gate_phase5
def test_feature_columns_contain_no_outcome():
    moves = _synthetic_moves()
    strengths = {"MLS": 0.0, "USLC": -0.3, "USL1": -0.6}
    feats = build_features(moves, strengths, METRIC)
    forbidden = {"to_minutes", f"to_{METRIC}", "actual", "minutes_share", "success"}
    assert not (set(feats.columns) & forbidden)
    # to_league / to_season are allowed: both are known at transfer time
    assert set(FEATURE_COLUMNS).issubset(feats.columns)


@pytest.mark.gate_phase5
def test_split_is_by_person_and_seeded():
    moves = pd.concat([_synthetic_moves(), _synthetic_moves()], ignore_index=True)  # 2 moves/person
    t1, h1 = split_movers(moves)
    t2, h2 = split_movers(moves)
    pd.testing.assert_frame_equal(t1, t2)
    assert not (set(t1["person_id"]) & set(h1["person_id"]))
    assert len(t1) + len(h1) == len(moves)


@pytest.mark.gate_phase5
def test_permutation_detects_signal_and_noise():
    rng = np.random.default_rng(1)
    x = rng.normal(size=200)
    y_signal = x + rng.normal(scale=0.3, size=200)
    y_noise = rng.normal(size=200)
    r_sig, p_sig = permutation_pvalue(x, y_signal, _spearman, 300, seed=42)
    r_noise, p_noise = permutation_pvalue(x, y_noise, _spearman, 300, seed=42)
    assert r_sig > 0.8 and p_sig < 0.01
    assert p_noise > 0.05


@pytest.mark.gate_phase5
def test_verdict_rule_three_values_only():
    assert decide_verdict(50, 0.5, 0.001, None, None)[0] == "signal"
    assert decide_verdict(50, 0.05, 0.60, None, None)[0] == "no signal"
    assert decide_verdict(8, 0.3, 0.30, None, None)[0] == "inconclusive-need-more-data"


@pytest.mark.gate_phase5
def test_success_label_definition():
    moves = _synthetic_moves(n=4, seed=3)
    strengths = {"MLS": 0.0, "USLC": -0.3, "USL1": -0.6}
    feats = build_features(moves, strengths, METRIC)
    labeled = label_outcomes(moves, feats, METRIC)
    exp_minutes_ok = moves["to_minutes"] / moves["from_minutes"] >= 0.5
    exp_metric_ok = moves[f"to_{METRIC}"] >= labeled["projected"] * 0.75
    assert (labeled["success"] == (exp_minutes_ok & exp_metric_ok)).all()
