"""ASA ingest via itscalledsoccer. All pulls rate-limited, retried with backoff, and
cached through src.common.io.cached_pull (cache hit = zero network calls).

The g+ endpoint returns a nested per-action-type list; flatten_goals_added() widens it
to parquet-safe columns before caching. See docs/asa_api_surface.md and
docs/metric_glossary.md.
"""

from __future__ import annotations

import time
from typing import Any, Callable

import pandas as pd

from src.common.config import asa_league_codes, load_settings, seasons
from src.common.io import cached_pull
from src.common.logging import get_logger

log = get_logger("ingest.asa")

GA_ACTION_TYPES = ["Dribbling", "Fouling", "Interrupting", "Passing", "Receiving", "Shooting"]

_client = None
_last_call_ts = 0.0


def _get_client():
    global _client
    if _client is None:
        from itscalledsoccer.client import AmericanSoccerAnalysis
        _client = AmericanSoccerAnalysis()
    return _client


def _throttled(fetch: Callable[[], pd.DataFrame]) -> pd.DataFrame:
    """Rate-limit + retry with exponential backoff around a live API call."""
    global _last_call_ts
    cfg = load_settings()["ingest"]
    wait = cfg["rate_limit_seconds"] - (time.monotonic() - _last_call_ts)
    if wait > 0:
        time.sleep(wait)
    last_exc: Exception | None = None
    for attempt in range(int(cfg["max_retries"])):
        try:
            result = fetch()
            _last_call_ts = time.monotonic()
            return result
        except Exception as exc:  # noqa: BLE001 - retried, then re-raised
            last_exc = exc
            backoff = float(cfg["backoff_base_seconds"]) * (2 ** attempt)
            log.warning("ASA call failed (attempt %d): %s — backing off %.1fs",
                        attempt + 1, exc, backoff)
            time.sleep(backoff)
    raise RuntimeError(f"ASA call failed after {cfg['max_retries']} retries") from last_exc


def flatten_goals_added(df: pd.DataFrame) -> pd.DataFrame:
    """Widen the nested g+ `data` column into per-action-type columns + totals.

    Output columns per action: ga_raw_<action>, ga_above_avg_<action>, ga_count_<action>
    plus goals_added_raw_total / goals_added_above_avg_total (sum across actions).
    """
    if df.empty or "data" not in df.columns:
        return df
    base = df.drop(columns=["data"]).reset_index(drop=True)
    wide_rows: list[dict[str, Any]] = []
    for actions in df["data"]:
        row: dict[str, Any] = {}
        for entry in (actions or []):
            a = entry["action_type"].lower()
            row[f"ga_raw_{a}"] = entry.get("goals_added_raw")
            row[f"ga_above_avg_{a}"] = entry.get("goals_added_above_avg")
            row[f"ga_count_{a}"] = entry.get("count_actions")
        wide_rows.append(row)
    wide = pd.DataFrame(wide_rows).reset_index(drop=True)
    out = pd.concat([base, wide], axis=1)
    raw_cols = [c for c in out.columns if c.startswith("ga_raw_")]
    avg_cols = [c for c in out.columns if c.startswith("ga_above_avg_")]
    out["goals_added_raw_total"] = out[raw_cols].sum(axis=1, min_count=1)
    out["goals_added_above_avg_total"] = out[avg_cols].sum(axis=1, min_count=1)
    return out


def _pull_player_season(endpoint: str, asa_code: str, season: int,
                        refresh: bool = False) -> pd.DataFrame:
    """One player-metric endpoint for one league-season, cached."""
    method = {
        "player_xgoals": "get_player_xgoals",
        "player_xpass": "get_player_xpass",
        "player_goals_added": "get_player_goals_added",
    }[endpoint]

    def fetch() -> pd.DataFrame:
        client = _get_client()
        df = _throttled(lambda: getattr(client, method)(
            leagues=asa_code, season_name=str(season), split_by_seasons=True))
        if endpoint == "player_goals_added":
            df = flatten_goals_added(df)
        return df

    return cached_pull("asa", endpoint, {"league": asa_code, "season": season},
                       fetch, refresh=refresh)


def pull_players(asa_code: str, refresh: bool = False) -> pd.DataFrame:
    """Identity table for one league (name, birth date, nationality, positions)."""
    def fetch() -> pd.DataFrame:
        client = _get_client()
        df = _throttled(lambda: client.get_players(leagues=asa_code))
        # season_name arrives as a list per player; keep a parquet-safe string form
        if "season_name" in df.columns:
            df["season_name"] = df["season_name"].apply(
                lambda v: ",".join(map(str, v)) if isinstance(v, (list, tuple)) else str(v))
        return df

    return cached_pull("asa", "players", {"league": asa_code}, fetch, refresh=refresh)


def pull_all(refresh: bool = False) -> dict[str, pd.DataFrame]:
    """Pull every configured league × season × endpoint. Returns concatenated frames
    keyed by endpoint, each with canonical `league` and integer `season` columns."""
    result: dict[str, list[pd.DataFrame]] = {
        "players": [], "player_xgoals": [], "player_xpass": [], "player_goals_added": [],
    }
    for canon, asa_code in asa_league_codes().items():
        players = pull_players(asa_code, refresh=refresh)
        if len(players):
            players = players.assign(league=canon)
            result["players"].append(players)
        for season in seasons("asa"):
            for endpoint in ["player_xgoals", "player_xpass", "player_goals_added"]:
                df = _pull_player_season(endpoint, asa_code, season, refresh=refresh)
                if len(df):
                    df = df.assign(league=canon, season=int(season))
                    result[endpoint].append(df)
    return {
        k: (pd.concat(v, ignore_index=True) if v else pd.DataFrame())
        for k, v in result.items()
    }
