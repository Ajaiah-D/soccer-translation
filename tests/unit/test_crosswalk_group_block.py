"""Regression test: a women's-league player must never match a men's-league record.

Real case caught in production data: NWSL striker Amy Rodriguez fuzzy-matched (score
~92, no birth years available to penalize) to Jay Rodriguez, who played the same
seasons in the Premier League - fabricating an NWSL->ENG1 'move'. The league-system
group block eliminates this class of error.
"""

import pandas as pd
import pytest

from src.harmonize.crosswalk import match_records


def _frames():
    left = pd.DataFrame([
        ("asa_amy", "Amy Rodriguez", 1987, frozenset({2018, 2019}), frozenset({"womens"})),
    ], columns=["player_id", "player_name", "birth_year", "seasons", "groups"])
    right = pd.DataFrame([
        ("us_jay", "Jay Rodríguez", None, frozenset({2018, 2019}), frozenset({"mens"})),
    ], columns=["right_id", "player_name", "birth_year", "seasons", "groups"])
    return left, right


@pytest.mark.gate_phase2
def test_cross_system_match_is_blocked():
    left, right = _frames()
    result = match_records(left, right, "player_id", "right_id")
    assert result.loc[0, "match_status"] == "unmatched"
    assert result.loc[0, "matched_player_id"] is None


@pytest.mark.gate_phase2
def test_same_system_still_matches():
    left, right = _frames()
    right = right.copy()
    right["groups"] = [frozenset({"womens"})]
    right["player_name"] = ["Amy Rodríguez"]
    result = match_records(left, right, "player_id", "right_id")
    assert result.loc[0, "match_status"] == "accepted"


@pytest.mark.gate_phase2
def test_missing_groups_column_is_tolerated():
    left, right = _frames()
    result = match_records(left.drop(columns="groups"), right.drop(columns="groups"),
                           "player_id", "right_id")
    assert len(result) == 1  # no crash; falls back to name/season/birth-year rules
