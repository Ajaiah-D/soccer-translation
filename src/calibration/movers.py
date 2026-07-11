"""Phase 3: identify players with qualifying seasons in >=2 leagues and assemble
pre/post metric vectors for every move.

Definitions (all from config/settings.yaml, movers.*):
- qualifying season: minutes >= min_minutes_qualifying in one league-season
- move: consecutive qualifying seasons in DIFFERENT leagues, destination season
  strictly later than origin and within max_season_gap seasons
"""

from __future__ import annotations

import pandas as pd

from src.common.config import data_path, load_settings
from src.common.logging import get_logger, log_lineage
from src.common.review_queue import add_review_item
from src.harmonize.metrics import METRIC_COLUMNS

log = get_logger("calibration.movers")


def resolve_persons(player_seasons: pd.DataFrame, crosswalk: pd.DataFrame) -> pd.DataFrame:
    """Attach person_id and collapse to one row per person-league-season.
    Where ASA and FBref both cover the same person-league-season (MLS), ASA wins
    (richer metric set, g+/xPass)."""
    merged = player_seasons.merge(
        crosswalk[["source", "source_player_id", "person_id"]],
        on=["source", "source_player_id"], how="left", validate="many_to_one")
    assert merged["person_id"].notna().all(), "every player-season must resolve to a person"

    # birth_year is person-level: broadcast the first known value across sources so
    # e.g. Understat rows (no birth dates) inherit the ASA/FBref birth year
    known_by = (merged.dropna(subset=["birth_year"])
                .groupby("person_id")["birth_year"].first())
    merged["birth_year"] = merged["birth_year"].fillna(
        merged["person_id"].map(known_by))

    before = len(merged)
    # preference when two sources cover the same person-league-season:
    # asa (richest metrics) > understat (has xG/xA) > fbref (identity/minutes only)
    merged["_source_rank"] = merged["source"].map({"asa": 0, "understat": 1}).fillna(2)
    merged = (merged.sort_values(["person_id", "league", "season", "_source_rank"])
              .drop_duplicates(["person_id", "league", "season"], keep="first")
              .drop(columns="_source_rank"))
    dropped = before - len(merged)
    if dropped:
        log_lineage("resolve_persons", "deduplicated", dropped,
                    "same person-league-season covered by both sources; ASA row kept")
    return merged


def find_moves(person_seasons: pd.DataFrame) -> pd.DataFrame:
    """One row per qualifying move with from_/to_ metric vectors.
    Origin seasons need min_minutes_qualifying; destination seasons only
    min_minutes_destination (lower, so partial failures stay in the sample -
    downstream estimation weights by minutes)."""
    cfg = load_settings()["movers"]
    min_from = float(cfg["min_minutes_qualifying"])
    min_to = float(cfg["min_minutes_destination"])
    max_gap = int(cfg["max_season_gap"])

    qualifying = person_seasons[person_seasons["minutes"] >= min_to].copy()
    log_lineage("find_moves", "filtered-below-destination-threshold",
                int(len(person_seasons) - len(qualifying)),
                f"minutes < {min_to} (config movers.min_minutes_destination)")

    qualifying = qualifying.sort_values(["person_id", "season", "league"])
    moves = []
    for person_id, grp in qualifying.groupby("person_id"):
        rows = grp.to_dict(orient="records")
        for a, b in zip(rows, rows[1:]):
            if (b["league"] != a["league"]
                    and a["minutes"] >= min_from
                    and a["season"] < b["season"] <= a["season"] + max_gap):
                birth_year = a.get("birth_year") or b.get("birth_year")
                move = {
                    "person_id": person_id,
                    "player_name": a["player_name"] or b["player_name"],
                    "from_league": a["league"], "to_league": b["league"],
                    "from_season": int(a["season"]), "to_season": int(b["season"]),
                    "from_minutes": float(a["minutes"]), "to_minutes": float(b["minutes"]),
                    "position": a.get("position"),
                    "birth_year": float(birth_year) if pd.notna(birth_year) else None,
                }
                for m in METRIC_COLUMNS:
                    move[f"from_{m}"] = a.get(m)
                    move[f"to_{m}"] = b.get(m)
                moves.append(move)
    return pd.DataFrame(moves).sort_values(
        ["person_id", "from_season", "to_season"]).reset_index(drop=True)


def compute_attrition(person_seasons: pd.DataFrame) -> pd.DataFrame:
    """Survivorship quantification: per directed league pair, players with a
    qualifying origin season who APPEARED in the destination league within the gap
    window but never reached the destination-minutes threshold there. These moves
    produce no ratio (their failure is invisible to the factors), so their count is
    reported next to the mover count. Players who left coverage entirely cannot be
    counted and are noted as a further undercount."""
    cfg = load_settings()["movers"]
    min_from = float(cfg["min_minutes_qualifying"])
    min_to = float(cfg["min_minutes_destination"])
    max_gap = int(cfg["max_season_gap"])

    origins = person_seasons[person_seasons["minutes"] >= min_from]
    rows = []
    by_person = dict(tuple(person_seasons.groupby("person_id")))
    for _, o in origins.iterrows():
        ps = by_person[o["person_id"]]
        window = ps[(ps["season"] > o["season"])
                    & (ps["season"] <= o["season"] + max_gap)
                    & (ps["league"] != o["league"])]
        for league, grp in window.groupby("league"):
            best = grp["minutes"].max()
            if best < min_to:
                rows.append({"from_league": o["league"], "to_league": league,
                             "person_id": o["person_id"]})
    if not rows:
        return pd.DataFrame(columns=["from_league", "to_league", "n_attrition"])
    att = pd.DataFrame(rows).drop_duplicates()
    return (att.groupby(["from_league", "to_league"]).size()
            .rename("n_attrition").reset_index())


def write_movers_summary(moves: pd.DataFrame,
                         attrition: pd.DataFrame | None = None) -> None:
    cfg = load_settings()["movers"]
    floor = int(cfg["thin_pair_floor"])
    pair_counts = (moves.groupby(["from_league", "to_league"]).size()
                   .rename("n_moves").reset_index()
                   .sort_values("n_moves", ascending=False))
    pair_counts["thin_sample_flag"] = pair_counts["n_moves"] < floor
    if attrition is not None and len(attrition):
        pair_counts = pair_counts.merge(attrition, on=["from_league", "to_league"],
                                        how="outer")
        pair_counts["n_moves"] = pair_counts["n_moves"].fillna(0).astype(int)
        pair_counts["n_attrition"] = pair_counts["n_attrition"].fillna(0).astype(int)
        pair_counts["thin_sample_flag"] = pair_counts["thin_sample_flag"].fillna(True)
        pair_counts["attrition_share"] = (
            pair_counts["n_attrition"]
            / (pair_counts["n_attrition"] + pair_counts["n_moves"]).clip(lower=1))
        pair_counts = pair_counts.sort_values("n_moves", ascending=False)

    lines = ["# Movers summary (Phase 3)", "",
             f"- total moves: **{len(moves)}** across {moves['person_id'].nunique()} players",
             f"- qualifying-season minutes threshold: {cfg['min_minutes_qualifying']}",
             f"- max season gap: {cfg['max_season_gap']}",
             f"- thin-pair floor (too thin to calibrate alone): {floor}", "",
             "## Moves per league pair", "",
             "Attrition = origin-qualified players who appeared in the destination "
             "league inside the gap window but never reached the destination-minutes "
             "threshold there: failed moves the factors cannot see (players who left "
             "covered leagues entirely are a further undercount).", "",
             "| from | to | n moves | n attrition | attrition share | thin? |",
             "|---|---|---|---|---|---|"]
    for _, r in pair_counts.iterrows():
        flag = "THIN" if r["thin_sample_flag"] else ""
        n_att = int(r.get("n_attrition", 0) or 0)
        share = r.get("attrition_share")
        share_s = f"{share:.0%}" if pd.notna(share) else "-"
        lines.append(f"| {r['from_league']} | {r['to_league']} | {r['n_moves']} "
                     f"| {n_att} | {share_s} | {flag} |")
    if len(moves):
        lines += ["", "## Minutes distribution (both sides of moves)", "",
                  f"- from_minutes: min {moves['from_minutes'].min():.0f}, "
                  f"median {moves['from_minutes'].median():.0f}, max {moves['from_minutes'].max():.0f}",
                  f"- to_minutes: min {moves['to_minutes'].min():.0f}, "
                  f"median {moves['to_minutes'].median():.0f}, max {moves['to_minutes'].max():.0f}"]
    out = data_path("data_outputs") / "movers_summary.md"
    out.write_text("\n".join(lines), encoding="utf-8")

    thin = pair_counts[pair_counts["thin_sample_flag"]]
    if len(thin):
        pairs = ", ".join(f"{r['from_league']}->{r['to_league']} (n={r['n_moves']})"
                          for _, r in thin.iterrows())
        add_review_item(
            title="Thin league-pair samples constrain calibration claims",
            severity="should-review",
            context=(f"League pairs below the thin-sample floor ({floor}): {pairs}. "
                     "Factors touching these pairs are shrunk hard toward 1.0 and "
                     "flagged low-confidence; treat their orderings as unproven."),
            artifact="data/outputs/movers_summary.md")


def run_phase3() -> None:
    interim = data_path("data_interim")
    player_seasons = pd.read_parquet(interim / "player_seasons.parquet")
    crosswalk = pd.read_parquet(data_path("data_crosswalk") / "player_crosswalk.parquet")

    person_seasons = resolve_persons(player_seasons, crosswalk)
    person_seasons.to_parquet(interim / "person_seasons.parquet", index=False)

    moves = find_moves(person_seasons)
    moves.to_parquet(interim / "movers.parquet", index=False)
    attrition = compute_attrition(person_seasons)
    attrition.to_parquet(interim / "attrition.parquet", index=False)
    write_movers_summary(moves, attrition)
    log.info("Phase 3 complete: %d moves, %d attrition pair-counts",
             len(moves), len(attrition))
