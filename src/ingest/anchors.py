"""External league-strength anchor: FiveThirtyEight SPI club ratings.

SPI rated ~40 leagues worldwide on one comparable scale (2016-2023, defunct since);
the full match file survives as a permanent Internet Archive snapshot, pinned below
for reproducibility. Each match row carries both clubs' SPI at match time, so a
league-season's strength is the match-weighted mean club SPI.

Role in this project: VALIDATION ANCHOR, never a production input. The mover-based
factors remain the research contribution; the anchor is an independent yardstick to
compare them against, and the only strength estimate available for anchor-only
leagues (EFL Championship, 2. Bundesliga) that lack open per-player data.

Known limits (reported in diagnostics, not hidden):
- coverage ends early 2023: the 2023-2025 tail of our window has no anchor;
- SPI is a club-form model with its own assumptions; ratios of league means are an
  index for ordering and rough magnitude, not a rate-conversion factor.
"""

from __future__ import annotations

import io

import pandas as pd
import requests

from src.common.config import load_leagues
from src.common.io import cached_pull
from src.common.logging import get_logger

log = get_logger("ingest.anchors")

# permanent snapshot of the final published SPI match file (2016-2023)
SPI_SNAPSHOT_URL = ("https://web.archive.org/web/20230625093532id_/"
                    "https://projects.fivethirtyeight.com/soccer-api/club/spi_matches.csv")


def spi_league_names() -> dict[str, str]:
    """Canonical code -> SPI league name, for every league SPI covers."""
    return {code: spec["spi"]
            for code, spec in load_leagues()["leagues"].items()
            if spec.get("spi")}


def anchor_only_leagues() -> set[str]:
    return {code for code, spec in load_leagues()["leagues"].items()
            if spec.get("anchor_only")}


def pull_spi_matches(refresh: bool = False) -> pd.DataFrame:
    """The SPI match file, filtered to configured leagues, cached."""

    def fetch() -> pd.DataFrame:
        resp = requests.get(SPI_SNAPSHOT_URL, timeout=180)
        resp.raise_for_status()
        df = pd.read_csv(io.BytesIO(resp.content))
        name_to_code = {v: k for k, v in spi_league_names().items()}
        df = df[df["league"].isin(name_to_code)].copy()
        df["league_code"] = df["league"].map(name_to_code)
        keep = ["season", "date", "league_code", "league", "team1", "team2",
                "spi1", "spi2"]
        return df[keep].reset_index(drop=True)

    return cached_pull("spi", "matches", {"snapshot": "20230625"}, fetch,
                       refresh=refresh)


def league_season_strength(spi_matches: pd.DataFrame) -> pd.DataFrame:
    """Match-weighted mean club SPI per league-season (both clubs of every match)."""
    if spi_matches.empty:
        return pd.DataFrame()
    long = pd.concat([
        spi_matches[["season", "league_code", "spi1"]].rename(columns={"spi1": "spi"}),
        spi_matches[["season", "league_code", "spi2"]].rename(columns={"spi2": "spi"}),
    ], ignore_index=True).dropna(subset=["spi"])
    return (long.groupby(["league_code", "season"], as_index=False)
            .agg(mean_spi=("spi", "mean"), n_ratings=("spi", "size")))


def league_anchor_table(seasons_window: tuple[int, int] | None = None,
                        refresh: bool = False) -> pd.DataFrame:
    """One row per league: mean SPI over the (optionally windowed) seasons, with the
    season range actually covered - the caller normalizes to the anchor league."""
    per_season = league_season_strength(pull_spi_matches(refresh=refresh))
    if per_season.empty:
        return per_season
    if seasons_window:
        lo, hi = seasons_window
        per_season = per_season[(per_season["season"] >= lo) & (per_season["season"] <= hi)]
    return (per_season.groupby("league_code", as_index=False)
            .agg(mean_spi=("mean_spi", "mean"),
                 seasons_covered=("season", lambda s: f"{s.min()}-{s.max()}"),
                 n_ratings=("n_ratings", "sum")))
