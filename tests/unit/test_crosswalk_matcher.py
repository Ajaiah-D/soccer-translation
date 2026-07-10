"""Phase 2 gate: matcher precision on the labeled fixture + determinism + name norm."""

import hashlib

import pandas as pd
import pytest

from src.common.config import load_settings
from src.harmonize.crosswalk import match_records, normalize_name, score_match
from tests.fixtures.crosswalk_labeled_fixture import LEFT, RIGHT, TRUE_MATCH


@pytest.mark.gate_phase2
def test_normalize_name_variants():
    assert normalize_name("Lucas Zelarayán") == "lucas zelarayan"
    assert normalize_name("Đorđe Mihailović") == "djordje mihailovic"
    assert normalize_name("Luiz Fernando Jr.") == "luiz fernando"
    assert normalize_name("Raúl Ruidíaz") == "raul ruidiaz"


@pytest.mark.gate_phase2
def test_score_penalizes_birth_year_gap():
    same = score_match("Diego Chara", "Diego Chará", 1986, 1986)
    trap = score_match("Diego Chara", "Yimmi Chará", 1986, 1991)
    assert same > 95
    assert trap < 70


@pytest.mark.gate_phase2
def test_fixture_precision_meets_target():
    """Of the matches the matcher ACCEPTS, >= configured share must be correct."""
    target = float(load_settings()["crosswalk"]["fixture_precision_target"])
    result = match_records(LEFT, RIGHT, "player_id", "right_id")
    accepted = result[result["match_status"] == "accepted"]
    assert len(accepted) >= 15, "matcher should accept the bulk of true pairs"
    correct = sum(
        TRUE_MATCH[row["right_id"]] == row["matched_player_id"]
        for _, row in accepted.iterrows()
    )
    precision = correct / len(accepted)
    assert precision >= target, f"precision {precision:.2f} < target {target}"


@pytest.mark.gate_phase2
def test_matcher_is_deterministic():
    a = match_records(LEFT, RIGHT, "player_id", "right_id")
    b = match_records(LEFT, RIGHT, "player_id", "right_id")
    ha = hashlib.sha256(pd.util.hash_pandas_object(a.astype(str), index=False).values.tobytes()).hexdigest()
    hb = hashlib.sha256(pd.util.hash_pandas_object(b.astype(str), index=False).values.tobytes()).hexdigest()
    assert ha == hb
