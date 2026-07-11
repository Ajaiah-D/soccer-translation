"""Phase 2 orchestration: per-90 normalization + cross-source crosswalk + audit sample."""

from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

from src.common.config import data_path, load_settings, random_seed
from src.common.io import frame_hash, write_output
from src.common.logging import get_logger, log_lineage
from src.common.review_queue import add_review_item
from src.harmonize.crosswalk import match_records
from src.harmonize.metrics import (
    normalize_asa,
    normalize_fbref,
    normalize_understat,
    write_data_dictionary,
)

log = get_logger("harmonize.runner")


def _identity_blocks(player_seasons: pd.DataFrame, source: str) -> pd.DataFrame:
    """One row per source player: name, birth_year, the set of active seasons, and
    the set of league-system groups (mens/womens) the player appeared in."""
    from src.common.config import league_registry
    groups_by_league = {code: spec.get("group") for code, spec in league_registry().items()}
    sub = player_seasons[player_seasons["source"] == source]
    return (sub.groupby("source_player_id")
            .agg(player_name=("player_name", "first"),
                 birth_year=("birth_year", "first"),
                 seasons=("season", lambda s: frozenset(int(x) for x in s)),
                 groups=("league", lambda s: frozenset(
                     g for g in (groups_by_league.get(l) for l in s) if g)))
            .reset_index())


def build_player_seasons() -> pd.DataFrame:
    interim = data_path("data_interim")
    xgoals = pd.read_parquet(interim / "asa_player_xgoals.parquet")
    xpass = pd.read_parquet(interim / "asa_player_xpass.parquet")
    goals_added = pd.read_parquet(interim / "asa_player_goals_added.parquet")
    players = pd.read_parquet(interim / "asa_players.parquet")
    fbref = pd.read_parquet(interim / "fbref_player_season.parquet")
    understat_path = interim / "understat_league_players.parquet"
    understat = (pd.read_parquet(understat_path) if understat_path.exists()
                 else pd.DataFrame())

    asa_norm = normalize_asa(xgoals, xpass, goals_added, players)
    fbref_norm = normalize_fbref(fbref)
    understat_norm = normalize_understat(understat)
    combined = pd.concat([asa_norm, fbref_norm, understat_norm], ignore_index=True)
    combined = combined.sort_values(
        ["source", "source_player_id", "league", "season"]).reset_index(drop=True)
    return combined


EMPTY_MATCHES = pd.DataFrame(columns=["source_player_id", "matched_asa_id",
                                      "candidate_asa_id", "match_confidence",
                                      "match_status", "player_name", "source"])


def build_crosswalk(player_seasons: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (crosswalk, match_detail). Crosswalk: one row per source player id
    with the person_id it resolves to and the match confidence. Every non-ASA
    source is matched against the ASA identity backbone."""
    asa_ids = _identity_blocks(player_seasons, "asa")

    rows = []
    for _, r in asa_ids.iterrows():
        rows.append({"source": "asa", "source_player_id": r["source_player_id"],
                     "person_id": f"asa:{r['source_player_id']}",
                     "player_name": r["player_name"],
                     "match_confidence": 100.0, "match_status": "identity"})

    other_sources = sorted(set(player_seasons["source"]) - {"asa"})
    all_matches = []
    expected_rows = len(asa_ids)
    for source in other_sources:
        source_ids = _identity_blocks(player_seasons, source)
        expected_rows += len(source_ids)
        if not len(source_ids):
            continue
        matches = match_records(asa_ids, source_ids, "source_player_id", "source_player_id")
        matches = matches.rename(columns={
            "matched_source_player_id": "matched_asa_id",
            "candidate_source_player_id": "candidate_asa_id"})
        matches["source"] = source
        all_matches.append(matches)
        for _, m in matches.iterrows():
            person = (f"asa:{m['matched_asa_id']}" if m["match_status"] == "accepted"
                      else f"{source}:{m['source_player_id']}")
            rows.append({"source": source, "source_player_id": m["source_player_id"],
                         "person_id": person, "player_name": m["player_name"],
                         "match_confidence": m["match_confidence"],
                         "match_status": m["match_status"]})

    matches = (pd.concat(all_matches, ignore_index=True) if all_matches
               else EMPTY_MATCHES.copy())
    crosswalk = pd.DataFrame(rows).sort_values(
        ["source", "source_player_id"]).reset_index(drop=True)

    # reconciliation: nothing silently dropped
    assert len(crosswalk) == expected_rows, "crosswalk row count mismatch"
    n_low = int((matches["match_status"] == "low_confidence").sum()) if len(matches) else 0
    n_un = int((matches["match_status"] == "unmatched").sum()) if len(matches) else 0
    log_lineage("crosswalk", "kept-source-scoped", n_low + n_un,
                "players without an accepted ASA match keep source-scoped person_id")
    return crosswalk, matches


def write_audit_sample(matches: pd.DataFrame) -> None:
    cfg = load_settings()["crosswalk"]
    rng = np.random.default_rng(random_seed())
    accepted = matches[matches["match_status"] == "accepted"]
    low = matches[matches["match_status"] == "low_confidence"]
    n_rand = min(int(cfg["audit_random_n"]), len(accepted))
    idx = rng.choice(len(accepted), size=n_rand, replace=False) if n_rand else []
    sample = pd.concat([
        accepted.iloc[sorted(idx)].assign(audit_bucket="random_accepted"),
        low.head(int(cfg["audit_low_confidence_n"])).assign(audit_bucket="low_confidence"),
    ])
    out = data_path("data_outputs") / "crosswalk_audit_sample.csv"
    sample.to_csv(out, index=False)

    unmatched = matches[matches["match_status"] == "unmatched"]
    report = data_path("data_outputs") / "crosswalk_unmatched_report.md"
    report.write_text(
        "# Crosswalk unmatched report\n\n"
        f"- fbref records matched to ASA identity: {len(accepted)}\n"
        f"- low-confidence (NOT auto-accepted, in audit sample): {len(low)}\n"
        f"- unmatched (kept with fbref-scoped person_id): {len(unmatched)}\n\n"
        "Unmatched is expected to dominate: most Premier League players never "
        "played in an ASA league.\n",
        encoding="utf-8")


def run_phase2() -> None:
    player_seasons = build_player_seasons()
    write_output(player_seasons, "data_interim", "player_seasons.parquet")

    crosswalk, matches = build_crosswalk(player_seasons)
    write_output(crosswalk, "data_crosswalk", "player_crosswalk.parquet")
    (data_path("data_crosswalk") / "crosswalk.hash").write_text(
        frame_hash(crosswalk.astype(str)), encoding="utf-8")

    write_audit_sample(matches)
    write_data_dictionary()

    add_review_item(
        title="Crosswalk false-positive spot-check",
        severity="must-review-before-trusting-results",
        context=("Fuzzy matching can bind two different players; a single bad "
                 "high-usage match can poison a league factor. Spot-check the audit "
                 "sample (random accepted + low-confidence buckets) for false positives."),
        artifact="data/outputs/crosswalk_audit_sample.csv",
    )
    log.info("Phase 2 complete: %d player-seasons, %d crosswalk rows",
             len(player_seasons), len(crosswalk))
