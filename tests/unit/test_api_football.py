"""Unit tests for the API-Football ingest (no network: fetchers are injected and the
cache is redirected to tmp_path)."""

import math

import pandas as pd
import pytest

from src.common.config import read_env_var
from src.common.io import cached_frame, cached_pull
from src.ingest.api_football import (
    ApiFootballError,
    Target,
    api_football_targets,
    backfill,
    catalog_status,
    daily_budget,
    flatten_players,
    parse_page,
    parse_teams,
    write_catalog_report,
)


def _stat(team_id, minutes, tackles=None):
    return {
        "team": {"id": team_id, "name": f"Team {team_id}"},
        "league": {"id": 39, "season": 2023},
        "games": {"appearences": 10, "lineups": 9, "minutes": minutes,
                  "position": "Defender", "rating": "6.9"},
        "tackles": {"total": tackles, "blocks": 2, "interceptions": 7},
        "passes": {"total": 400, "key": 3, "accuracy": 88},
    }


# one player with a single club, one who moved mid-season inside the league
PAYLOAD = {
    "errors": [],
    "paging": {"current": 1, "total": 3},
    "response": [
        {"player": {"id": 101, "name": "M. Akanji", "firstname": "Manuel",
                    "lastname": "Akanji", "birth": {"date": "1995-07-19"},
                    "nationality": "Switzerland"},
         "statistics": [_stat(50, 2100, tackles=31)]},
        {"player": {"id": 202, "name": "J. Doe", "firstname": "John",
                    "lastname": "Doe", "birth": {"date": None},
                    "nationality": "England"},
         "statistics": [_stat(60, 400, tackles=None), _stat(70, 900, tackles=12)]},
    ],
}


def test_flatten_gives_one_row_per_player_team_stint():
    df = flatten_players(PAYLOAD["response"])
    assert len(df) == 3
    assert list(df["player_id"]) == [101, 202, 202]
    assert list(df["team_id"]) == [50, 60, 70]


def test_flatten_names_nested_stats_by_group():
    df = flatten_players(PAYLOAD["response"])
    for col in ["player_name", "birth_date", "nationality", "games_minutes",
                "games_position", "tackles_total", "tackles_interceptions",
                "passes_key", "passes_accuracy"]:
        assert col in df.columns, f"missing {col}"
    assert df.loc[0, "birth_date"] == "1995-07-19"
    assert df.loc[0, "tackles_interceptions"] == 7


def test_flatten_keeps_missing_stats_missing_not_zero():
    df = flatten_players(PAYLOAD["response"])
    assert math.isnan(df.loc[1, "tackles_total"])
    assert df.loc[2, "tackles_total"] == 12


def test_parse_page_returns_rows_and_total_pages():
    df, total = parse_page(PAYLOAD)
    assert total == 3 and len(df) == 3


@pytest.mark.parametrize("errors", [
    {"plan": "Free plans do not have access to this season, try from 2022 to 2024."},
    {"requests": "You have reached the request limit for the day."},
    {"token": "Error/Missing application key."},
])
def test_parse_page_raises_on_api_errors(errors):
    with pytest.raises(ApiFootballError):
        parse_page({"errors": errors, "paging": {"current": 1, "total": 1},
                    "response": []})


def test_daily_budget_leaves_reserve_and_never_goes_negative():
    assert daily_budget({"current": 30, "limit_day": 100}, reserve=5) == 65
    assert daily_budget({"current": 98, "limit_day": 100}, reserve=5) == 0


def _fake_site(teams_by_target, pages_by_team, error_on=None):
    """Fetcher over an in-memory site. teams_by_target maps (league_id, season) to
    team ids; pages_by_team maps team id to its page count. Every call is recorded so
    tests can prove what hit the network."""
    calls = []

    def fetch(path, params):
        calls.append((path, dict(params)))
        if error_on and error_on(path, params):
            return {"errors": {"requests": "You have reached the request limit for the day."},
                    "paging": {"current": 1, "total": 1}, "response": []}
        if path == "teams":
            ids = teams_by_target[(params["league"], params["season"])]
            return {"errors": [], "paging": {"current": 1, "total": 1},
                    "response": [{"team": {"id": i, "name": f"Team {i}"}} for i in ids]}
        total = pages_by_team[params["team"]]
        return {"errors": [], "paging": {"current": params["page"], "total": total},
                "response": [{"player": {"id": params["team"] * 100 + params["page"],
                                         "name": "P"},
                              "statistics": [_stat(params["team"], 900)]}]}

    return fetch, calls


TARGETS = [Target("AAA", 1, 2023), Target("BBB", 2, 2023)]
SITE = ({(1, 2023): [10, 11], (2, 2023): [20]}, {10: 2, 11: 1, 20: 2})


def _pages(calls):
    return [(p["team"], p["page"]) if path == "players" else ("teams", p["league"])
            for path, p in calls]


@pytest.fixture
def tmp_cache(tmp_path, monkeypatch):
    monkeypatch.setattr("src.common.io.data_path", lambda key: tmp_path)
    return tmp_path


def test_parse_teams_lists_team_ids_and_names():
    df = parse_teams({"errors": [], "response": [{"team": {"id": 50, "name": "Man City"}}]})
    assert list(df["team_id"]) == [50] and list(df["team_name"]) == ["Man City"]


def test_backfill_walks_teams_then_each_teams_pages(tmp_cache):
    fetch, calls = _fake_site(*SITE)
    result = backfill(fetch, TARGETS, budget=100, max_page=3)
    assert _pages(calls) == [("teams", 1), (10, 1), (10, 2), (11, 1),
                             ("teams", 2), (20, 1), (20, 2)]
    assert result.fetched == 7 and result.complete


def test_backfill_player_requests_carry_league_team_season_and_page(tmp_cache):
    fetch, calls = _fake_site(*SITE)
    backfill(fetch, TARGETS[:1], budget=100, max_page=3)
    assert calls[1] == ("players", {"league": 1, "season": 2023, "team": 10, "page": 1})


def test_backfill_stops_when_budget_is_spent(tmp_cache):
    fetch, calls = _fake_site(*SITE)
    result = backfill(fetch, TARGETS, budget=4, max_page=3)
    assert _pages(calls) == [("teams", 1), (10, 1), (10, 2), (11, 1)]
    assert result.fetched == 4 and not result.complete
    assert result.stopped_reason == "daily budget spent"


def test_backfill_resumes_without_refetching_cached_pages(tmp_cache):
    fetch, calls = _fake_site(*SITE)
    backfill(fetch, TARGETS, budget=4, max_page=3)
    calls.clear()
    result = backfill(fetch, TARGETS, budget=100, max_page=3)
    assert _pages(calls) == [("teams", 2), (20, 1), (20, 2)]
    assert result.fetched == 3 and result.complete


def test_backfill_never_requests_past_the_plan_page_cap(tmp_cache):
    fetch, calls = _fake_site({(1, 2023): [10]}, {10: 5})
    result = backfill(fetch, TARGETS[:1], budget=100, max_page=3)
    assert _pages(calls) == [("teams", 1), (10, 1), (10, 2), (10, 3)]
    assert result.complete


def test_backfill_stops_on_api_error_and_caches_nothing_for_that_page(tmp_cache):
    fetch, _ = _fake_site(*SITE, error_on=lambda path, p: path == "players")
    result = backfill(fetch, TARGETS, budget=100, max_page=3)
    assert result.fetched == 1 and not result.complete
    assert "request limit" in result.stopped_reason
    assert cached_frame("api_football", "players",
                        {"league": 1, "season": 2023, "team": 10, "page": 1}) is None


def test_catalog_status_reads_progress_from_cache_only(tmp_cache):
    fetch, _ = _fake_site({(1, 2023): [10, 11], (2, 2023): [20], (3, 2023): [30]},
                          {10: 5, 11: 1, 20: 2, 30: 1})
    targets = TARGETS + [Target("CCC", 3, 2023)]
    backfill(fetch, targets, budget=6, max_page=3)
    status = catalog_status(targets, max_page=3).set_index("league")
    # AAA: team 10 has 5 pages but the plan stops at 3, so it is done but truncated
    assert status.loc["AAA", ["teams_total", "teams_done", "teams_truncated"]].tolist() == [2, 2, 1]
    assert status.loc["BBB", ["teams_total", "teams_done", "teams_truncated"]].tolist() == [1, 0, 0]
    assert status.loc["CCC", "teams_done"] == 0 and pd.isna(status.loc["CCC", "teams_total"])


def test_cached_frame_is_none_on_miss_and_frame_on_hit(tmp_cache):
    assert cached_frame("src", "ep", {"k": 1}) is None
    cached_pull("src", "ep", {"k": 1}, lambda: pd.DataFrame({"a": [1]}))
    assert len(cached_frame("src", "ep", {"k": 1})) == 1


def test_targets_cover_every_configured_league_and_free_season():
    targets = api_football_targets()
    assert Target("POR1", 94, 2022) in targets
    assert Target("ENG1", 39, 2024) in targets
    assert len({t.league for t in targets}) == 16
    assert {t.season for t in targets} == {2022, 2023, 2024}


def test_read_env_var_prefers_environment_then_env_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("# comment\nSOME_KEY=from-file\n", encoding="utf-8")
    monkeypatch.delenv("SOME_KEY", raising=False)
    assert read_env_var("SOME_KEY", env_file) == "from-file"
    monkeypatch.setenv("SOME_KEY", "from-env")
    assert read_env_var("SOME_KEY", env_file) == "from-env"
    assert read_env_var("ABSENT_KEY", env_file) is None


def test_catalog_report_counts_complete_and_flags_truncated_squads(tmp_cache):
    status = pd.DataFrame({"league": ["AAA", "BBB", "CCC"], "league_id": [1, 2, 3],
                           "season": [2023] * 3,
                           "teams_total": pd.array([2, 1, None], dtype="Int64"),
                           "teams_done": [2, 0, 0], "teams_truncated": [1, 0, 0]})
    text = write_catalog_report(status, None).read_text(encoding="utf-8")
    assert "league-seasons complete: 1 of 3" in text
    assert "teams with squads past the page cap: 1" in text
    assert "| CCC | 2023 | 0 | ? | 0 |" in text
