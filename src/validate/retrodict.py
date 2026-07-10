"""Phase 5: proof-of-concept validation — retrodict held-out movers.

Honesty guarantees:
- Movers are split 50/50 (seeded). League strengths are RE-ESTIMATED on the
  calibration half only; the held-out movers' post-move data cannot influence the
  factors used to project them.
- Features for a held-out mover are exclusively pre-move: from_-metrics, leagues,
  seasons. build_features() takes a frame with the to_-outcome columns scrambled and
  must produce identical projections (functional leakage test, Phase 5 hard gate).
- The skill estimate is compared against a permutation baseline (shuffled outcomes).
- The verdict is derived from the numbers by an explicit rule and routed to the human
  review queue for ratification.

Definitions (config validation.*):
- projected post-move rate: from_<primary_metric> * S_from / S_to  (train-half strengths)
- success: to_minutes/from_minutes >= success_min_minutes_share AND
           actual to_<primary_metric> >= projected * (1 - success_max_metric_drop)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.common.config import anchor_league, data_path, load_settings, random_seed
from src.common.logging import get_logger
from src.common.review_queue import add_review_item
from src.calibration.league_strength import chain_strengths, log_ratios, pairwise_factors

log = get_logger("validate.retrodict")

FEATURE_COLUMNS = ["person_id", "player_name", "from_league", "to_league",
                   "from_season", "to_season", "from_minutes"]  # + from_<metric>


def split_movers(moves: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Seeded 50/50 split by PERSON (all moves of one person land on one side,
    so a multi-move player cannot leak across the split)."""
    frac = float(load_settings()["validation"]["holdout_fraction"])
    persons = np.array(sorted(moves["person_id"].unique()))
    rng = np.random.default_rng(random_seed())
    rng.shuffle(persons)
    n_holdout = int(round(len(persons) * frac))
    holdout_persons = set(persons[:n_holdout])
    holdout = moves[moves["person_id"].isin(holdout_persons)].reset_index(drop=True)
    train = moves[~moves["person_id"].isin(holdout_persons)].reset_index(drop=True)
    return train, holdout


def train_strengths(train_moves: pd.DataFrame, metric: str) -> dict[str, float]:
    cfg = load_settings()["calibration"]
    ratios = log_ratios(train_moves, metric)
    pairs = pairwise_factors(ratios, float(cfg["shrinkage_k"]))
    return chain_strengths(pairs, anchor_league())


def build_features(holdout: pd.DataFrame, strengths: dict[str, float],
                   metric: str) -> pd.DataFrame:
    """Pre-move-only feature frame + projection. Never reads any to_-outcome column
    (only to_league/to_season, which are known at transfer time)."""
    feats = holdout[FEATURE_COLUMNS + [f"from_{metric}"]].copy()
    s_from = feats["from_league"].map(strengths)
    s_to = feats["to_league"].map(strengths)
    # leagues absent from the train-half graph get no projection (explicit, not imputed)
    conv = np.exp(s_from - s_to)
    feats["conversion_factor"] = conv
    feats["projected"] = feats[f"from_{metric}"] * conv
    return feats


def label_outcomes(holdout: pd.DataFrame, feats: pd.DataFrame, metric: str) -> pd.DataFrame:
    cfg = load_settings()["validation"]
    out = feats.copy()
    out["actual"] = holdout[f"to_{metric}"].to_numpy()
    out["minutes_share"] = (holdout["to_minutes"] / holdout["from_minutes"]).to_numpy()
    out["success"] = (
        (out["minutes_share"] >= float(cfg["success_min_minutes_share"]))
        & (out["actual"] >= out["projected"] * (1 - float(cfg["success_max_metric_drop"])))
    )
    return out


def permutation_pvalue(x: np.ndarray, y: np.ndarray, stat, iterations: int,
                       seed: int) -> tuple[float, float]:
    """Two-sided permutation test: p = share of shuffled |stat| >= |observed|."""
    rng = np.random.default_rng(seed)
    observed = stat(x, y)
    hits = 0
    for _ in range(iterations):
        perm = rng.permutation(y)
        if abs(stat(x, perm)) >= abs(observed):
            hits += 1
    return float(observed), (hits + 1) / (iterations + 1)


def _spearman(x: np.ndarray, y: np.ndarray) -> float:
    xr = pd.Series(x).rank().to_numpy()
    yr = pd.Series(y).rank().to_numpy()
    if np.std(xr) == 0 or np.std(yr) == 0:
        return 0.0
    return float(np.corrcoef(xr, yr)[0, 1])


def decide_verdict(n: int, r: float, p_r: float, auc: float | None,
                   p_auc: float | None) -> tuple[str, str]:
    """Explicit verdict rule (the human ratifies via review queue):
    - signal: permutation p < 0.05 on the continuous skill AND r > 0
    - no-signal: n >= 30 and p >= 0.05
    - inconclusive-need-more-data: otherwise (small n dominates)
    """
    if p_r < 0.05 and r > 0:
        return "signal", (f"projected vs actual Spearman r={r:.3f} beats shuffled "
                          f"labels (p={p_r:.4f}, n={n})")
    if n >= 30 and p_r >= 0.05:
        return "no signal", (f"with n={n} held-out moves, r={r:.3f} does not beat "
                             f"the permutation baseline (p={p_r:.4f})")
    return "inconclusive-need-more-data", (
        f"n={n} held-out moves is too small to separate r={r:.3f} (p={p_r:.4f}) from noise")


def run_phase5() -> None:
    cfg = load_settings()["validation"]
    metric = str(cfg["primary_metric"])
    moves = pd.read_parquet(data_path("data_interim") / "movers.parquet")

    train, holdout = split_movers(moves)
    strengths = train_strengths(train, metric)

    feats = build_features(holdout, strengths, metric)
    labeled = label_outcomes(holdout, feats, metric)

    usable = labeled.dropna(subset=["projected", "actual"]).reset_index(drop=True)
    n_excluded = len(labeled) - len(usable)

    x = usable["projected"].to_numpy(dtype=float)
    y = usable["actual"].to_numpy(dtype=float)
    iters = int(cfg["permutation_iterations"])
    r, p_r = permutation_pvalue(x, y, _spearman, iters, random_seed())

    # secondary: does the strength-adjusted metric separate successes from failures?
    succ = usable["success"].to_numpy(dtype=bool)
    auc = p_auc = None
    if 0 < succ.sum() < len(succ):
        def _auc(xx, yy):
            order = pd.Series(xx).rank().to_numpy()
            pos, neg = order[yy.astype(bool)], order[~yy.astype(bool)]
            return float((pos[:, None] > neg[None, :]).mean())
        auc, p_auc = permutation_pvalue(x, succ, _auc, iters, random_seed())

    # naive baseline: unadjusted from-metric as the projection
    naive_mae = float(np.abs(usable[f"from_{metric}"] - usable["actual"]).mean())
    adj_mae = float(np.abs(usable["projected"] - usable["actual"]).mean())

    verdict, justification = decide_verdict(len(usable), r, p_r, auc, p_auc)

    _write_report(metric, train, holdout, usable, n_excluded, strengths,
                  r, p_r, auc, p_auc, naive_mae, adj_mae, verdict, justification)

    add_review_item(
        title="Proof-of-concept signal interpretation (verdict ratification)",
        severity="must-review-before-trusting-results",
        context=(f"Agent-proposed verdict: **{verdict}** — {justification}. "
                 "With thin mover samples, distinguishing real signal from noise is a "
                 "judgment call: the human ratifies or overrides this verdict before "
                 "any Stage 3/4/6 work is unlocked."),
        artifact="data/outputs/proof_of_concept.md")
    log.info("Phase 5 complete: verdict=%s (n=%d, r=%.3f, p=%.4f)",
             verdict, len(usable), r, p_r)


def _write_report(metric, train, holdout, usable, n_excluded, strengths,
                  r, p_r, auc, p_auc, naive_mae, adj_mae, verdict, justification) -> None:
    lines = [
        "# Proof-of-concept validation (Phase 5)", "",
        f"**Question:** do strength-adjusted pre-move `{metric}` values carry signal "
        "about post-move outcomes for held-out movers?", "",
        "## Setup", "",
        f"- moves total: {len(train) + len(holdout)} (train {len(train)}, "
        f"held-out {len(holdout)}, split by person, seed {random_seed()})",
        f"- league strengths re-estimated on the train half only "
        f"(no held-out post-move data touches the factors): "
        + ", ".join(f"{k}={np.exp(v):.3f}" for k, v in sorted(strengths.items())),
        f"- held-out moves usable (projection & actual both defined): **{len(usable)}** "
        f"({n_excluded} excluded for missing metric on either side — reported, not imputed)",
        "",
        "## Results", "",
        f"- Spearman r (projected vs actual): **{r:.3f}**",
        f"- permutation baseline ({load_settings()['validation']['permutation_iterations']} "
        f"shuffles): **p = {p_r:.4f}**",
        f"- success-classification AUC: "
        + (f"**{auc:.3f}** (permutation p = {p_auc:.4f})" if auc is not None
           else "not computable (all-success or all-failure holdout)"),
        f"- MAE, naive unadjusted projection: {naive_mae:.4f}",
        f"- MAE, strength-adjusted projection: {adj_mae:.4f} "
        + ("(adjustment helps)" if adj_mae < naive_mae else "(adjustment does NOT reduce error)"),
        "",
        "## Per-mover table (held-out)", "",
        "| player | move | seasons | projected | actual | minutes share | success |",
        "|---|---|---|---|---|---|---|",
    ]
    for _, m in usable.sort_values("projected", ascending=False).iterrows():
        lines.append(
            f"| {m['player_name']} | {m['from_league']}->{m['to_league']} | "
            f"{m['from_season']}->{m['to_season']} | {m['projected']:.3f} | "
            f"{m['actual']:.3f} | {m['minutes_share']:.2f} | "
            f"{'yes' if m['success'] else 'no'} |")
    lines += [
        "", "## Verdict", "",
        f"**{verdict}** — {justification}", "",
        "_This verdict is proposed by the agent and must be ratified by a human "
        "(see REVIEW_QUEUE.md) before Stage 3/4/6 work is unlocked._",
    ]
    out = data_path("data_outputs") / "proof_of_concept.md"
    out.write_text("\n".join(lines), encoding="utf-8")
