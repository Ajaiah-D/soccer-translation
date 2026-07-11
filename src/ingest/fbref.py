"""FBref ingest - CACHE-FIRST, live fetching OPT-IN.

FBref sits behind bot protection that can demand an interactive verification click,
which breaks unattended runs. The pipeline therefore treats FBref as a frozen,
already-cached historical source: pull_all() reads whatever slices exist in
data/raw and reports anything else as an explicit coverage gap. Live fetching (a
short real-browser session via src.ingest.fbref_direct) only happens when
config ingest.fbref_fetch_enabled is true.

Recurring data needs are covered by ASA and Understat, which run fully unattended.

Two legacy slices (MLS 2018, 2022) were cached by an earlier soccerdata-based path;
their column schema matches parse_standard_table's output, so the fbref_player_season
contract covers both.
"""

from __future__ import annotations

import pandas as pd

from src.common.config import data_path, fbref_league_codes, load_settings, seasons
from src.common.io import cache_key, cached_pull
from src.common.logging import get_logger
from src.ingest.fbref_direct import BrowserSession, parse_standard_table, season_url

log = get_logger("ingest.fbref")

ENDPOINTS = {
    "player_season_standard": ("stats", "stats_standard"),
    "player_season_shooting": ("shooting", "stats_shooting"),
}


def _slice_params(fbref_league: str, season: int) -> dict:
    return {"league": fbref_league, "season": season}


def _is_cached(fbref_league: str, season: int, endpoint: str = "player_season_standard") -> bool:
    key = cache_key("fbref", endpoint, _slice_params(fbref_league, season))
    fname = f"fbref__{endpoint}__{key}.parquet"
    return (data_path("data_raw") / fname).exists()


def _read_cached(fbref_league: str, season: int, endpoint: str) -> pd.DataFrame:
    """Read one cached slice without any fetch path (empty frame if not cached)."""
    if not _is_cached(fbref_league, season, endpoint):
        return pd.DataFrame()
    return cached_pull("fbref", endpoint, _slice_params(fbref_league, season),
                       lambda: pd.DataFrame(), refresh=False)


def _fetch_missing(plan: list[tuple[str, str, int]], endpoint: str, refresh: bool) -> None:
    """Opt-in live fetch of missing slices in one browser session (may require a
    single human verification click - see module docstring)."""
    page, table_id = ENDPOINTS[endpoint]
    to_fetch = [(canon, fbref_league, season) for canon, fbref_league, season in plan
                if refresh or not _is_cached(fbref_league, season, endpoint)]
    if not to_fetch:
        return
    log.info("fetching %d FBref %s pages in one browser session", len(to_fetch), page)
    with BrowserSession() as session:
        for canon, fbref_league, season in to_fetch:
            def fetch(canon=canon, season=season) -> pd.DataFrame:
                html = session.fetch(season_url(canon, season, page=page),
                                     table_marker=table_id)
                if not html:
                    log.warning("FBref %s %s %s unavailable - cached as explicit "
                                "empty gap", page, canon, season)
                    return pd.DataFrame()
                try:
                    return parse_standard_table(html, table_id=table_id)
                except Exception as exc:  # noqa: BLE001 - gap recorded, run continues
                    log.warning("FBref %s %s %s parse failed: %s - cached as empty gap",
                                page, canon, season, str(exc)[:120])
                    return pd.DataFrame()

            cached_pull("fbref", endpoint, _slice_params(fbref_league, season),
                        fetch, refresh=refresh)


def pull_all(refresh: bool = False) -> pd.DataFrame:
    """All configured FBref leagues x seasons from cache, concatenated with canonical
    league codes. Uncached slices are skipped (they show as MISSING in the coverage
    report) unless ingest.fbref_fetch_enabled is true."""
    plan: list[tuple[str, str, int]] = []  # (canon, fbref_league, season)
    for canon, fbref_league in fbref_league_codes().items():
        for season in seasons("fbref"):
            plan.append((canon, fbref_league, season))

    if bool(load_settings()["ingest"].get("fbref_fetch_enabled", False)):
        for endpoint in ENDPOINTS:
            _fetch_missing(plan, endpoint, refresh)
    else:
        missing = [(c, s) for c, l, s in plan if not _is_cached(l, s)]
        if missing:
            log.info("FBref live fetching disabled; %d uncached slices left as "
                     "explicit coverage gaps: %s", len(missing), missing)

    frames: list[pd.DataFrame] = []
    for canon, fbref_league, season in plan:
        df = _read_cached(fbref_league, season, "player_season_standard")
        if not len(df):
            continue
        shooting = _read_cached(fbref_league, season, "player_season_shooting")
        if len(shooting) and "expected_xg" in shooting.columns:
            xg_cols = [c for c in ["expected_xg", "expected_npxg"] if c in shooting.columns]
            df = df.drop(columns=[c for c in xg_cols if c in df.columns])
            df = df.merge(shooting[["player", "team", "born"] + xg_cols]
                          .drop_duplicates(["player", "team", "born"]),
                          on=["player", "team", "born"], how="left")
        frames.append(df.assign(league=canon, season=int(season)))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
