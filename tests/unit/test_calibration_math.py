"""Phase 4 gate: statistical guards — shrinkage, chaining recovery, bootstrap seed."""

import numpy as np
import pandas as pd
import pytest

from src.calibration.league_strength import (
    bootstrap_strengths,
    chain_strengths,
    log_ratios,
    pairwise_factors,
)


def _ratios_frame(pairs_with_ratios):
    return pd.DataFrame(pairs_with_ratios,
                        columns=["person_id", "from_league", "to_league", "log_ratio"])


@pytest.mark.gate_phase4
def test_shrinkage_pulls_small_n_toward_one():
    """n=1 with a huge observed ratio must NOT be trusted: factor lands near 1.0."""
    ratios = _ratios_frame([("p1", "A", "B", np.log(3.0))])
    pairs = pairwise_factors(ratios, shrinkage_k=4)
    raw = float(np.exp(pairs["mean_log_ratio"].iloc[0]))
    shrunk = float(pairs["factor"].iloc[0])
    assert raw == pytest.approx(3.0)
    assert 1.0 < shrunk < 1.35  # 3.0^(1/5) ~ 1.246


@pytest.mark.gate_phase4
def test_shrinkage_vanishes_with_large_n():
    ratios = _ratios_frame([(f"p{i}", "A", "B", np.log(1.5)) for i in range(400)])
    pairs = pairwise_factors(ratios, shrinkage_k=4)
    assert float(pairs["factor"].iloc[0]) == pytest.approx(1.5, rel=0.02)


@pytest.mark.gate_phase4
def test_chaining_recovers_synthetic_strengths():
    """Exact log-ratios generated from known strengths must be recovered by WLS."""
    s_true = {"MLS": 0.0, "USLC": -0.4, "USL1": -0.9}
    rows = []
    i = 0
    for a in s_true:
        for b in s_true:
            if a == b:
                continue
            for _ in range(400):  # large n so shrinkage (n/(n+k)) is negligible
                rows.append((f"p{i}", a, b, s_true[a] - s_true[b]))
                i += 1
    pairs = pairwise_factors(_ratios_frame(rows), shrinkage_k=4)
    s_hat = chain_strengths(pairs, anchor="MLS")
    for league, s in s_true.items():
        assert s_hat[league] == pytest.approx(s, abs=0.02)


@pytest.mark.gate_phase4
def test_chaining_transits_through_intermediate_league():
    """A<->B and B<->C observed, A<->C never: chaining must still order A vs C."""
    rows = ([(f"x{i}", "A", "B", 0.3) for i in range(30)]
            + [(f"y{i}", "B", "C", 0.5) for i in range(30)])
    pairs = pairwise_factors(_ratios_frame(rows), shrinkage_k=4)
    s_hat = chain_strengths(pairs, anchor="A")
    assert s_hat["A"] > s_hat["B"] > s_hat["C"]


@pytest.mark.gate_phase4
def test_bootstrap_reproducible_under_seed():
    rng = np.random.default_rng(0)
    rows = [(f"p{i}", "A", "B", float(rng.normal(0.2, 0.3))) for i in range(40)]
    ratios = _ratios_frame(rows)
    b1 = bootstrap_strengths(ratios, 4, "A", iterations=50, seed=42)
    b2 = bootstrap_strengths(ratios, 4, "A", iterations=50, seed=42)
    pd.testing.assert_frame_equal(b1, b2)


@pytest.mark.gate_phase4
def test_log_ratios_excludes_nonpositive_sides(tmp_path, monkeypatch):
    monkeypatch.setattr("src.common.logging.data_path", lambda key: tmp_path)
    moves = pd.DataFrame({
        "person_id": ["p1", "p2", "p3"],
        "from_league": ["A"] * 3, "to_league": ["B"] * 3,
        "from_xg_xa_per90": [0.5, 0.0, -0.1],
        "to_xg_xa_per90": [0.4, 0.3, 0.2],
    })
    out = log_ratios(moves, "xg_xa_per90")
    assert list(out["person_id"]) == ["p1"]
