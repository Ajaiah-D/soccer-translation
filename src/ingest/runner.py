"""Phase 1 orchestration: pull + cache + contract-validate all sources, then emit
data/outputs/coverage_report.md with every gap explicit (spec Phase 1 gate)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.common.config import asa_league_codes, data_path, fbref_league_codes, seasons
from src.common.contracts import validate_frame
from src.common.io import write_output
from src.common.logging import get_logger
from src.ingest import asa, fbref, transfermarkt
from src.ingest.contracts_def import CONTRACTS, write_contract_docs

log = get_logger("ingest.runner")

# metrics whose presence the coverage report must enumerate per league-season
COVERAGE_METRICS = ["g+", "xG", "xPass", "minutes", "position"]


def _coverage_cell(frames: dict[str, pd.DataFrame], league: str, season: int,
                   metric: str) -> str:
    """'ok (n=..)' or an explicit MISSING label — never a silent gap."""
    endpoint = {"g+": "player_goals_added", "xG": "player_xgoals",
                "xPass": "player_xpass", "minutes": "player_xgoals",
                "position": "player_xgoals"}[metric]
    df = frames[endpoint]
    if df.empty:
        return "MISSING (endpoint empty)"
    sub = df[(df["league"] == league) & (df["season"] == season)]
    if sub.empty:
        return "MISSING (no rows)"
    if metric == "minutes":
        return f"ok (n={len(sub)})" if sub["minutes_played"].notna().any() else "MISSING (all null)"
    if metric == "position":
        return f"ok (n={len(sub)})" if sub["general_position"].notna().any() else "MISSING (all null)"
    col = {"g+": "goals_added_raw_total", "xG": "xgoals",
           "xPass": "passes_completed_over_expected"}[metric]
    if col not in sub.columns or not sub[col].notna().any():
        return f"MISSING (column {col} absent/null)"
    return f"ok (n={len(sub)})"


def write_coverage_report(asa_frames: dict[str, pd.DataFrame],
                          fbref_df: pd.DataFrame) -> Path:
    lines = [
        "# Coverage report — metrics × leagues × seasons",
        "",
        "Every cell is either `ok (n=rows)` or an explicit `MISSING (...)` label.",
        "There are no silent gaps: a league-season absent from a source appears here as MISSING.",
        "",
        "## American pyramid (ASA)",
        "",
    ]
    for league in asa_league_codes():
        lines += [f"### {league}", "", "| season | " + " | ".join(COVERAGE_METRICS) + " |",
                  "|" + "---|" * (len(COVERAGE_METRICS) + 1)]
        for season in seasons("asa"):
            cells = [_coverage_cell(asa_frames, league, season, m) for m in COVERAGE_METRICS]
            lines.append(f"| {season} | " + " | ".join(cells) + " |")
        lines.append("")

    lines += ["## FBref comparison leagues", "",
              "| league | season | rows |", "|---|---|---|"]
    for league in fbref_league_codes():
        for season in seasons("fbref"):
            if fbref_df.empty:
                rows = "MISSING (source empty)"
            else:
                n = len(fbref_df[(fbref_df["league"] == league) & (fbref_df["season"] == season)])
                rows = f"ok (n={n})" if n else "MISSING (no rows)"
            lines.append(f"| {league} | {season} | {rows} |")

    lines += ["", "## Transfermarkt", "",
              f"Stub fixture rows: {len(transfermarkt.get_player_valuations())} "
              "(hand-entered; real feed requested via review queue).", ""]

    out = data_path("data_outputs") / "coverage_report.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def run_phase1(refresh: bool = False) -> None:
    log.info("Phase 1: pulling ASA (cached unless --refresh)")
    asa_frames = asa.pull_all(refresh=refresh)
    log.info("Phase 1: pulling FBref")
    fbref_df = fbref.pull_all(refresh=refresh)
    tm_df = transfermarkt.get_player_valuations()

    # contract validation — fail loudly on drift
    validate_frame(asa_frames["players"], CONTRACTS["asa_players"], "asa_players")
    validate_frame(asa_frames["player_xgoals"], CONTRACTS["asa_player_xgoals"], "asa_player_xgoals")
    validate_frame(asa_frames["player_xpass"], CONTRACTS["asa_player_xpass"], "asa_player_xpass")
    validate_frame(asa_frames["player_goals_added"], CONTRACTS["asa_player_goals_added"],
                   "asa_player_goals_added")
    if len(fbref_df):
        validate_frame(fbref_df, CONTRACTS["fbref_player_season"], "fbref_player_season")
    validate_frame(tm_df, CONTRACTS["transfermarkt"], "transfermarkt")

    # persist consolidated interim frames for Phase 2
    for name, df in asa_frames.items():
        write_output(df, "data_interim", f"asa_{name}.parquet")
    write_output(fbref_df, "data_interim", "fbref_player_season.parquet")
    write_output(tm_df, "data_interim", "transfermarkt.parquet")

    write_contract_docs()
    report = write_coverage_report(asa_frames, fbref_df)

    from src.common.review_queue import add_review_item
    add_review_item(
        title="Transfermarkt real feed request",
        severity="should-review",
        context=("The Transfermarkt source is a stub backed by a small hand-entered "
                 "fixture (interface documented in src/ingest/transfermarkt.py). "
                 "Market-value validation labels stay out of the proof-of-concept "
                 "until the owner provides the real scraper/feed."),
        artifact="src/ingest/transfermarkt.py",
    )
    log.info("Phase 1 complete: coverage report at %s", report)
