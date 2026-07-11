"""Aging curves and age adjustment for mover deltas (methodology fix).

Problem being fixed: movers do not change leagues at random career points.
Europe->MLS movers are mostly past peak (their age-driven decline reads as "MLS is
hard"); MLS->Europe movers are mostly pre-peak (their development reads as "Europe
is easy"). Both biases inflate MLS relative to Europe.

Fix: estimate the expected year-over-year change in a metric as a function of age
from WITHIN-LEAGUE consecutive season pairs (no league change, so no league effect),
then subtract the expected age-driven change from each mover's observed log-ratio.
Curves are estimated from this project's own person-season data (tens of thousands
of pairs), shrunk toward zero where an age bucket is thin.

Movers without a known birth year cannot be adjusted; they are EXCLUDED from the
age-adjusted calibration and counted (config calibration.age_adjust).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.common.config import load_settings
from src.common.logging import get_logger, log_lineage

log = get_logger("calibration.aging")

AGE_MIN, AGE_MAX = 17, 40


def within_league_pairs(person_seasons: pd.DataFrame, metric: str) -> pd.DataFrame:
    """Consecutive same-league qualifying season pairs with known age and positive
    metric on both sides: the raw material for the aging curve."""
    cfg = load_settings()["movers"]
    min_minutes = float(cfg["min_minutes_qualifying"])
    ps = person_seasons[(person_seasons["minutes"] >= min_minutes)
                        & person_seasons["birth_year"].notna()
                        & (person_seasons[metric] > 0)].copy()
    ps = ps.sort_values(["person_id", "league", "season"])
    prev = ps.groupby(["person_id", "league"]).shift(1)
    mask = (prev["season"] == ps["season"] - 1) & (prev[metric] > 0)
    pairs = pd.DataFrame({
        "person_id": ps["person_id"],
        "league": ps["league"],
        # age in the LATTER season of the pair; the delta is attributed to turning this age
        "age": (ps["season"] - ps["birth_year"]).astype(int),
        "delta_log": np.log(ps[metric] / prev[metric]),
    })[mask.fillna(False)]
    return pairs[(pairs["age"] >= AGE_MIN) & (pairs["age"] <= AGE_MAX)].reset_index(drop=True)


def estimate_aging_curve(pairs: pd.DataFrame) -> pd.DataFrame:
    """Expected delta-log(metric) per integer age, shrunk toward 0 by n/(n+k).
    Age buckets outside observed data get 0 (no adjustment rather than extrapolation)."""
    k = float(load_settings()["calibration"].get("aging_shrinkage_k", 25))
    if pairs.empty:
        return pd.DataFrame({"age": [], "expected_delta_log": [], "n": []})
    grp = pairs.groupby("age")["delta_log"].agg(["mean", "count"]).reset_index()
    grp["expected_delta_log"] = grp["mean"] * grp["count"] / (grp["count"] + k)
    return grp.rename(columns={"count": "n"})[["age", "expected_delta_log", "n"]]


def expected_age_change(curve: pd.DataFrame, from_age: float, to_age: float) -> float:
    """Cumulative expected delta-log between two ages: the sum of per-year expected
    changes for every birthday crossed. Ages without curve support contribute 0."""
    if pd.isna(from_age) or pd.isna(to_age):
        return float("nan")
    lookup = dict(zip(curve["age"], curve["expected_delta_log"]))
    return float(sum(lookup.get(age, 0.0)
                     for age in range(int(from_age) + 1, int(to_age) + 1)))


def age_adjust_log_ratios(ratios: pd.DataFrame, moves: pd.DataFrame,
                          curve: pd.DataFrame, metric: str) -> pd.DataFrame:
    """Subtract expected aging change from each mover's log-ratio.

    Movers without a known birth year follow calibration.age_adjust_unknown:
    - 'keep' (default): retained with their raw delta - counted, never silent.
      Rationale: the age-asymmetry bias is concentrated in transatlantic moves
      (all of which have ASA birth years); the age-unknown movers are almost all
      intra-European, where move-age profiles are roughly symmetric in both
      directions, so their aggregate aging bias largely cancels within each pair.
    - 'exclude': dropped and counted (maximally conservative, thins the graph).
    """
    mode = str(load_settings()["calibration"].get("age_adjust_unknown", "keep"))
    ages = moves[["person_id", "from_league", "to_league", "from_season", "to_season",
                  "birth_year"]].copy()
    merged = ratios.merge(ages, on=["person_id", "from_league", "to_league"], how="left")
    merged = merged.drop_duplicates(subset=["person_id", "from_league", "to_league",
                                            "log_ratio"])
    merged["from_age"] = merged["from_season"] - merged["birth_year"]
    merged["to_age"] = merged["to_season"] - merged["birth_year"]

    known = merged[merged["birth_year"].notna()].copy()
    unknown = merged[merged["birth_year"].isna()].copy()
    known["expected_aging"] = [
        expected_age_change(curve, fa, ta)
        for fa, ta in zip(known["from_age"], known["to_age"])]
    known["log_ratio"] = known["log_ratio"] - known["expected_aging"]

    if len(unknown):
        if mode == "keep":
            log_lineage("age_adjust", "kept-unadjusted-unknown-age", int(len(unknown)),
                        f"no birth year for {metric} mover; raw delta retained "
                        "(config age_adjust_unknown=keep)")
            out = pd.concat([known, unknown], ignore_index=True)
        else:
            log_lineage("age_adjust", "excluded-unknown-age", int(len(unknown)),
                        f"no birth year available for {metric} mover (cannot age-adjust)")
            out = known
    else:
        out = known
    keep = ["person_id", "from_league", "to_league", "log_ratio"]
    if "weight" in out.columns:
        keep.append("weight")
    return out[keep].reset_index(drop=True)
