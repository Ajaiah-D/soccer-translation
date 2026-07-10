"""FBref ingest via soccerdata, isolated to a project-local SOCCERDATA_DIR so the
custom league registration (MLS) and soccerdata's own scrape cache never touch
machine-global state. Our cached_pull layer sits on top, so re-runs read
data/raw parquet without importing/scraping at all.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd

from src.common.config import PROJECT_ROOT, fbref_league_codes, seasons
from src.common.io import cached_pull
from src.common.logging import get_logger

log = get_logger("ingest.fbref")

SOCCERDATA_DIR = PROJECT_ROOT / ".soccerdata"

# Leagues beyond soccerdata's built-ins, registered via its league_dict.json.
CUSTOM_LEAGUES = {
    "USA-Major League Soccer": {
        "FBref": "Major League Soccer",
        "season_start": "Feb",
        "season_end": "Nov",
    },
}


def _configure_soccerdata() -> None:
    """Point soccerdata at the project-local dir and register custom leagues.
    Must run before `import soccerdata`."""
    os.environ["SOCCERDATA_DIR"] = str(SOCCERDATA_DIR)
    config_dir = SOCCERDATA_DIR / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    league_dict_path = config_dir / "league_dict.json"
    existing = {}
    if league_dict_path.exists():
        existing = json.loads(league_dict_path.read_text(encoding="utf-8"))
    if any(k not in existing for k in CUSTOM_LEAGUES):
        existing.update(CUSTOM_LEAGUES)
        league_dict_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")


def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    """soccerdata returns MultiIndex columns like ('Performance','Gls'); flatten to
    snake_case 'performance_gls'."""
    df = df.reset_index()
    df.columns = [
        "_".join(str(part) for part in col if part and not str(part).startswith("Unnamed"))
        .strip().lower().replace(" ", "_")
        if isinstance(col, tuple) else str(col).strip().lower().replace(" ", "_")
        for col in df.columns
    ]
    return df


def pull_player_season_stats(fbref_league: str, season: int,
                             refresh: bool = False) -> pd.DataFrame:
    """Standard player season stats (minutes, goals, assists, xG, xAG, position, age)
    for one league-season, cached."""

    def fetch() -> pd.DataFrame:
        _configure_soccerdata()
        import soccerdata as sd
        fb = sd.FBref(leagues=fbref_league, seasons=season)
        df = fb.read_player_season_stats(stat_type="standard")
        df = _flatten_columns(df)
        # parquet-safe: stringify any residual object columns holding non-scalars
        for col in df.columns:
            if df[col].dtype == object:
                df[col] = df[col].astype(str)
        return df

    return cached_pull("fbref", "player_season_standard",
                       {"league": fbref_league, "season": season},
                       fetch, refresh=refresh)


def pull_all(refresh: bool = False) -> pd.DataFrame:
    """All configured FBref leagues × seasons, concatenated with canonical league codes.
    A league-season that fails to scrape is recorded as an explicit gap (empty cache
    entry) rather than aborting the run."""
    frames: list[pd.DataFrame] = []
    for canon, fbref_league in fbref_league_codes().items():
        for season in seasons("fbref"):
            try:
                df = pull_player_season_stats(fbref_league, season, refresh=refresh)
            except Exception as exc:  # noqa: BLE001 - gap is recorded, run continues
                log.warning("FBref %s %s failed: %s — recorded as coverage gap",
                            fbref_league, season, exc)
                df = cached_pull("fbref", "player_season_standard",
                                 {"league": fbref_league, "season": season},
                                 lambda: pd.DataFrame(), refresh=False)
            if len(df):
                frames.append(df.assign(league=canon, season=int(season)))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
