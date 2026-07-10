"""Unit tests for the g+ nested-payload flattener (pure function, no network)."""

import pandas as pd
import pytest

from src.ingest.asa import flatten_goals_added


def _nested_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "player_id": ["p1"],
            "team_id": ["t1"],
            "season_name": ["2023"],
            "general_position": ["W"],
            "minutes_played": [931],
            "data": [[
                {"action_type": "Dribbling", "goals_added_raw": -0.005,
                 "goals_added_above_avg": -0.0813, "count_actions": 138},
                {"action_type": "Shooting", "goals_added_raw": 0.3301,
                 "goals_added_above_avg": -0.0896, "count_actions": 11},
            ]],
        }
    )


@pytest.mark.gate_phase1
def test_flatten_widens_action_types():
    out = flatten_goals_added(_nested_frame())
    assert "data" not in out.columns
    assert out.loc[0, "ga_raw_dribbling"] == -0.005
    assert out.loc[0, "ga_count_shooting"] == 11


@pytest.mark.gate_phase1
def test_flatten_totals_are_sums():
    out = flatten_goals_added(_nested_frame())
    assert out.loc[0, "goals_added_raw_total"] == pytest.approx(-0.005 + 0.3301)
    assert out.loc[0, "goals_added_above_avg_total"] == pytest.approx(-0.0813 - 0.0896)


@pytest.mark.gate_phase1
def test_flatten_empty_frame_passthrough():
    empty = pd.DataFrame()
    assert flatten_goals_added(empty).empty
