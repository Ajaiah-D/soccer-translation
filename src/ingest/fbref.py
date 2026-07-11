"""FBref ingest. Fetching is done by src.ingest.fbref_direct (a short real-browser
session per batch of missing pages - see that module for why); results are cached
through src.common.io.cached_pull so re-runs are fully offline.

Two legacy slices (MLS 2018, 2022) were cached by an earlier soccerdata-based path;
their column schema matches parse_standard_table's output, so the fbref_player_season
contract covers both.
"""

from __future__ import annotations

import pandas as pd

from src.common.config import data_path, fbref_league_codes, load_leagues, seasons
from src.common.io import cache_key, cached_pull
from src.common.logging import get_logger
from src.ingest.fbref_direct import fetch_pages, parse_standard_table, season_url

log = get_logger("ingest.fbref")


def _slice_params(fbref_league: str, season: int) -> dict:
    return {"league": fbref_league, "season": season}


def _is_cached(fbref_league: str, season: int) -> bool:
    key = cache_key("fbref", "player_season_standard", _slice_params(fbref_league, season))
    fname = f"fbref__player_season_standard__{key}.parquet"
    return (data_path("data_raw") / fname).exists()


def pull_all(refresh: bool = False) -> pd.DataFrame:
    """All configured FBref leagues x seasons, concatenated with canonical league
    codes. Missing (or refresh-requested) slices are fetched in ONE browser session;
    a slice whose page cannot be fetched/parsed is cached as an explicit empty gap."""
    plan: list[tuple[str, str, int]] = []  # (canon, fbref_league, season)
    for canon, fbref_league in fbref_league_codes().items():
        for season in seasons("fbref"):
            plan.append((canon, fbref_league, season))

    to_fetch = [(canon, fbref_league, season) for canon, fbref_league, season in plan
                if refresh or not _is_cached(fbref_league, season)]
    pages: dict[str, str | None] = {}
    if to_fetch:
        urls = [season_url(canon, season) for canon, _, season in to_fetch]
        log.info("fetching %d FBref pages in one browser session", len(urls))
        pages = fetch_pages(urls)

    frames: list[pd.DataFrame] = []
    for canon, fbref_league, season in plan:
        def fetch(canon=canon, season=season) -> pd.DataFrame:
            html = pages.get(season_url(canon, season))
            if not html:
                log.warning("FBref %s %s unavailable - cached as explicit empty gap",
                            canon, season)
                return pd.DataFrame()
            try:
                return parse_standard_table(html)
            except Exception as exc:  # noqa: BLE001 - gap is recorded, run continues
                log.warning("FBref %s %s parse failed: %s - cached as empty gap",
                            canon, season, str(exc)[:120])
                return pd.DataFrame()

        df = cached_pull("fbref", "player_season_standard",
                         _slice_params(fbref_league, season), fetch, refresh=refresh)
        if len(df):
            frames.append(df.assign(league=canon, season=int(season)))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
