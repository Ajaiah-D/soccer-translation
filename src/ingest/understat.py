"""Understat ingest: player-season xG/xA for European leagues via the site's JSON
endpoint (POST /main/getPlayersStats/ with league + season). Plain HTTP - no browser,
no interactive verification - so this path is fully repeatable, unlike FBref's
bot-protected pages. Results are cached through cached_pull like every other source.

Season convention matches ours: season 2023 = the 2023/24 European season.
Understat provides no birth dates or nationalities; the crosswalk relies on name +
season-overlap blocking for these records.
"""

from __future__ import annotations

import time

import pandas as pd
import requests

from src.common.config import load_leagues, load_settings, seasons
from src.common.io import cached_pull
from src.common.logging import get_logger

log = get_logger("ingest.understat")

ENDPOINT = "https://understat.com/main/getPlayersStats/"

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"),
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://understat.com/",
}

NUMERIC_COLUMNS = ["games", "time", "goals", "xG", "assists", "xA", "shots",
                   "key_passes", "npg", "npxG"]


def understat_league_codes() -> dict[str, str]:
    """Canonical code -> Understat league id, for leagues Understat covers."""
    return {code: spec["understat"]
            for code, spec in load_leagues()["leagues"].items()
            if spec.get("understat")}


def _fetch_league_season(understat_league: str, season: int) -> pd.DataFrame:
    cfg = load_settings()["ingest"]
    last_exc: Exception | None = None
    for attempt in range(int(cfg["max_retries"])):
        try:
            resp = requests.post(ENDPOINT, headers=HEADERS,
                                 data={"league": understat_league, "season": str(season)},
                                 timeout=30)
            resp.raise_for_status()
            payload = resp.json()
            players = payload.get("players", [])
            df = pd.DataFrame(players)
            for col in NUMERIC_COLUMNS:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            return df
        except Exception as exc:  # noqa: BLE001 - retried with backoff
            last_exc = exc
            backoff = float(cfg["backoff_base_seconds"]) * (2 ** attempt)
            log.warning("understat %s %s failed (attempt %d): %s - backing off %.1fs",
                        understat_league, season, attempt + 1, exc, backoff)
            time.sleep(backoff)
    raise RuntimeError(f"understat pull failed for {understat_league} {season}") from last_exc


def pull_all(refresh: bool = False) -> pd.DataFrame:
    """Every configured Understat league x season, concatenated with canonical
    league codes; rate-limited and cached."""
    cfg = load_settings()["ingest"]
    frames: list[pd.DataFrame] = []
    for canon, understat_league in understat_league_codes().items():
        for season in seasons("fbref"):  # same comparison-league season window
            def fetch(ul=understat_league, s=season) -> pd.DataFrame:
                time.sleep(float(cfg["rate_limit_seconds"]))
                return _fetch_league_season(ul, s)

            df = cached_pull("understat", "league_players",
                             {"league": understat_league, "season": season},
                             fetch, refresh=refresh)
            if len(df):
                frames.append(df.assign(league=canon, season=int(season)))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
