"""Unit tests for the direct FBref parser and URL builder (no network)."""

import pytest

from src.ingest.fbref_direct import parse_standard_table, season_url

# minimal FBref-style page: table hidden in an HTML comment, two-row header,
# a repeated in-table header row, and a multi-word nation code
FIXTURE_HTML = """
<html><body>
<div id="all_stats_standard">
<!--
<table id="stats_standard">
<thead>
<tr><th colspan="6"></th><th colspan="3">Playing Time</th><th colspan="2">Performance</th><th colspan="2">Expected</th><th></th></tr>
<tr><th>Rk</th><th>Player</th><th>Nation</th><th>Pos</th><th>Squad</th><th>Born</th><th>MP</th><th>Starts</th><th>Min</th><th>Gls</th><th>Ast</th><th>xG</th><th>xAG</th><th>Matches</th></tr>
</thead>
<tbody>
<tr><td>1</td><td>Carles Gil</td><td>es ESP</td><td>MF</td><td>New England</td><td>1992</td><td>34</td><td>34</td><td>3060</td><td>6</td><td>18</td><td>5.5</td><td>12.3</td><td>Matches</td></tr>
<tr><td>Rk</td><td>Player</td><td>Nation</td><td>Pos</td><td>Squad</td><td>Born</td><td>MP</td><td>Starts</td><td>Min</td><td>Gls</td><td>Ast</td><td>xG</td><td>xAG</td><td>Matches</td></tr>
<tr><td>2</td><td>Hany Mukhtar</td><td>de GER</td><td>MF,FW</td><td>Nashville</td><td>1995</td><td>33</td><td>32</td><td>2900</td><td>23</td><td>11</td><td>18.9</td><td>8.1</td><td>Matches</td></tr>
</tbody>
</table>
-->
</div>
</body></html>
"""


def test_parse_extracts_players_from_commented_table():
    df = parse_standard_table(FIXTURE_HTML)
    assert list(df["player"]) == ["Carles Gil", "Hany Mukhtar"]
    assert "matches" not in df.columns and "rk" not in df.columns


def test_parse_flattens_headers_to_contract_names():
    df = parse_standard_table(FIXTURE_HTML)
    for col in ["player", "nation", "pos", "team", "born",
                "playing_time_min", "performance_gls", "performance_ast",
                "expected_xg", "expected_xag"]:
        assert col in df.columns, f"missing {col}"


def test_parse_coerces_numbers_and_nation_codes():
    df = parse_standard_table(FIXTURE_HTML)
    assert df.loc[0, "playing_time_min"] == 3060
    assert df.loc[1, "expected_xg"] == pytest.approx(18.9)
    assert list(df["nation"]) == ["ESP", "GER"]


def test_season_url_styles():
    assert season_url("MLS", 2019) == \
        "https://fbref.com/en/comps/22/2019/stats/2019-Major-League-Soccer-Stats"
    assert season_url("ENG1", 2019) == \
        "https://fbref.com/en/comps/9/2019-2020/stats/2019-2020-Premier-League-Stats"
