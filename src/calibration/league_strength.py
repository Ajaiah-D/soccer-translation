"""Phase 4: league-strength calibration.

Method (documented for the diagnostics report):
1. Per mover and metric, the observed change is the log-ratio
   log(to_metric / from_metric); movers with a non-positive value on either side are
   excluded from that metric (counted, never silent).
2. Pairwise factor for a directed league pair (A→B): mean log-ratio, SHRUNK toward 0
   (= factor 1.0) by n/(n+k) — small samples are pulled toward "no change" (spec §7).
3. Chaining: weighted least squares on the league graph. Model
   log f_AB = s_A − s_B (a player moving to a weaker league produces more), anchored
   at s_anchor = 0. Weights = shrunk observation counts.
4. Uncertainty: bootstrap over movers (seeded); percentile CIs for every league
   strength and pairwise factor.

League strength S_L = exp(s_L); S higher = stronger league; anchor league = 1.0.
Conversion of a per-90 rate from league A to league B: rate * (S_A / S_B).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.common.config import anchor_league, data_path, load_settings, random_seed, strength_priors
from src.common.logging import get_logger, log_lineage
from src.common.review_queue import add_review_item

log = get_logger("calibration.league_strength")


def log_ratios(moves: pd.DataFrame, metric: str) -> pd.DataFrame:
    """Per-mover log-ratio for one metric; excludes non-positive sides (logged)."""
    f, t = f"from_{metric}", f"to_{metric}"
    usable = moves[(moves[f] > 0) & (moves[t] > 0)].copy()
    excluded = len(moves) - len(usable)
    if excluded:
        log_lineage("log_ratios", "excluded-from-metric", excluded,
                    f"non-positive {metric} on one side of the move (ratio undefined)")
    usable["log_ratio"] = np.log(usable[t] / usable[f])
    return usable[["person_id", "from_league", "to_league", "log_ratio"]]


def pairwise_factors(ratios: pd.DataFrame, shrinkage_k: float) -> pd.DataFrame:
    """Directed pairwise factors with shrinkage toward 1.0."""
    grp = ratios.groupby(["from_league", "to_league"])["log_ratio"]
    out = grp.agg(n="count", mean_log_ratio="mean").reset_index()
    out["shrunk_log_ratio"] = out["mean_log_ratio"] * out["n"] / (out["n"] + shrinkage_k)
    out["factor"] = np.exp(out["shrunk_log_ratio"])
    return out


def chain_strengths(pairs: pd.DataFrame, anchor: str) -> dict[str, float]:
    """WLS on log-factors over the league graph -> log-strength per league.
    log f_AB = s_A - s_B, s_anchor = 0, weights = n (post-shrinkage estimates)."""
    leagues = sorted(set(pairs["from_league"]) | set(pairs["to_league"]))
    if anchor not in leagues:
        leagues.append(anchor)
    free = [l for l in leagues if l != anchor]
    idx = {l: i for i, l in enumerate(free)}
    X = np.zeros((len(pairs), len(free)))
    y = pairs["shrunk_log_ratio"].to_numpy()
    w = pairs["n"].to_numpy(dtype=float)
    for row, (_, r) in enumerate(pairs.iterrows()):
        if r["from_league"] != anchor:
            X[row, idx[r["from_league"]]] = 1.0
        if r["to_league"] != anchor:
            X[row, idx[r["to_league"]]] = -1.0
    # solve weighted least squares; lstsq handles rank deficiency (disconnected graphs)
    Xw = X * np.sqrt(w)[:, None]
    yw = y * np.sqrt(w)
    coef, *_ = np.linalg.lstsq(Xw, yw, rcond=None)
    s = {anchor: 0.0}
    s.update({l: float(coef[i]) for l, i in idx.items()})
    return s


def bootstrap_strengths(ratios: pd.DataFrame, shrinkage_k: float, anchor: str,
                        iterations: int, seed: int) -> pd.DataFrame:
    """Bootstrap over movers: one strength sample per iteration per league."""
    rng = np.random.default_rng(seed)
    samples: list[dict[str, float]] = []
    n = len(ratios)
    for _ in range(iterations):
        resampled = ratios.iloc[rng.integers(0, n, size=n)]
        pairs = pairwise_factors(resampled, shrinkage_k)
        samples.append(chain_strengths(pairs, anchor))
    return pd.DataFrame(samples)


def check_priors(strengths: pd.DataFrame, boot: pd.DataFrame) -> list[dict]:
    """Compare chained strengths against footballing priors. A violation is
    'confident' when the bootstrap CI of the strength difference excludes 0."""
    cfg = load_settings()["calibration"]
    alpha = (1 - float(cfg["ci_level"])) / 2
    findings = []
    s = dict(zip(strengths["league"], strengths["log_strength"]))
    for stronger, weaker in strength_priors():
        if stronger not in s or weaker not in s:
            findings.append({"pair": (stronger, weaker), "status": "untestable",
                             "detail": "league missing from calibration graph"})
            continue
        ok = s[stronger] > s[weaker]
        if stronger in boot.columns and weaker in boot.columns:
            diff = boot[stronger].fillna(0) - boot[weaker].fillna(0)
            lo, hi = diff.quantile(alpha), diff.quantile(1 - alpha)
            confident = (lo > 0) or (hi < 0)
        else:
            lo = hi = float("nan")
            confident = False
        if ok:
            status = "satisfied"
        else:
            status = "VIOLATION-confident" if confident else "violation-wide-ci"
        findings.append({"pair": (stronger, weaker), "status": status,
                         "diff_ci": (float(lo), float(hi))})
    return findings


def run_phase4() -> None:
    cfg = load_settings()["calibration"]
    anchor = anchor_league()
    moves = pd.read_parquet(data_path("data_interim") / "movers.parquet")
    thin_floor = int(load_settings()["movers"]["thin_pair_floor"])

    all_factors, all_strengths, prior_findings = [], [], []
    for metric in cfg["metrics"]:
        ratios = log_ratios(moves, metric)
        if ratios.empty:
            log.warning("no usable ratios for %s", metric)
            continue
        pairs = pairwise_factors(ratios, float(cfg["shrinkage_k"]))
        pairs["metric"] = metric
        pairs["low_confidence"] = pairs["n"] < thin_floor
        strengths_point = chain_strengths(pairs, anchor)
        boot = bootstrap_strengths(ratios, float(cfg["shrinkage_k"]), anchor,
                                   int(cfg["bootstrap_iterations"]), random_seed())
        alpha = (1 - float(cfg["ci_level"])) / 2
        strengths = pd.DataFrame({
            "league": list(strengths_point),
            "log_strength": [strengths_point[l] for l in strengths_point]})
        strengths["strength"] = np.exp(strengths["log_strength"])
        strengths["ci_low"] = [float(np.exp(boot[l].quantile(alpha))) if l in boot else np.nan
                               for l in strengths["league"]]
        strengths["ci_high"] = [float(np.exp(boot[l].quantile(1 - alpha))) if l in boot else np.nan
                                for l in strengths["league"]]
        strengths["n_moves_touching"] = [
            int(pairs.loc[(pairs["from_league"] == l) | (pairs["to_league"] == l), "n"].sum())
            for l in strengths["league"]]
        strengths["low_confidence"] = strengths["n_moves_touching"] < thin_floor
        strengths["metric"] = metric
        all_factors.append(pairs)
        all_strengths.append(strengths)
        prior_findings.append((metric, check_priors(strengths, boot)))

    factors = pd.concat(all_factors, ignore_index=True)
    strengths = pd.concat(all_strengths, ignore_index=True)
    strengths.to_parquet(data_path("data_outputs") / "league_strength.parquet", index=False)
    factors.to_parquet(data_path("data_outputs") / "pairwise_factors.parquet", index=False)

    _write_diagnostics(factors, strengths, prior_findings)

    confident_violations = [
        (metric, f) for metric, findings in prior_findings
        for f in findings if f["status"] == "VIOLATION-confident"]
    if confident_violations:
        detail = "; ".join(f"{m}: {f['pair'][0]}>{f['pair'][1]} violated, diff CI {f['diff_ci']}"
                           for m, f in confident_violations)
        add_review_item(
            title="Confident league-ordering violation contradicts footballing prior",
            severity="must-review-before-trusting-results",
            context=(f"A narrow-CI ordering contradicts a strong prior: {detail}. "
                     "Treat as a red flag (possible crosswalk poisoning or selection "
                     "bias), not a discovery."),
            artifact="data/outputs/calibration_diagnostics.md")
        raise RuntimeError(f"Phase 4 gate: confident prior violation(s): {detail}")
    log.info("Phase 4 complete: %d league-metric strengths", len(strengths))


def _write_diagnostics(factors: pd.DataFrame, strengths: pd.DataFrame,
                       prior_findings: list) -> None:
    cfg = load_settings()["calibration"]
    lines = ["# Calibration diagnostics (Phase 4)", "",
             f"- shrinkage k = {cfg['shrinkage_k']} (mean log-ratio scaled by n/(n+k))",
             f"- bootstrap iterations = {cfg['bootstrap_iterations']}, "
             f"CI level = {cfg['ci_level']}, seed = {random_seed()}",
             f"- anchor: {anchor_league()} = 1.0", "",
             "## League strengths (per metric)", "",
             "| metric | league | strength | CI low | CI high | n touching | low-confidence |",
             "|---|---|---|---|---|---|---|"]
    for _, r in strengths.sort_values(["metric", "strength"], ascending=[True, False]).iterrows():
        flag = "⚠️ yes" if r["low_confidence"] else "no"
        lines.append(f"| {r['metric']} | {r['league']} | {r['strength']:.3f} | "
                     f"{r['ci_low']:.3f} | {r['ci_high']:.3f} | {r['n_moves_touching']} | {flag} |")
    lines += ["", "## Directed pairwise factors", "",
              "| metric | from | to | n | raw mean log-ratio | shrunk | factor | low-confidence |",
              "|---|---|---|---|---|---|---|---|"]
    for _, r in factors.sort_values(["metric", "n"], ascending=[True, False]).iterrows():
        flag = "⚠️ yes" if r["low_confidence"] else "no"
        lines.append(f"| {r['metric']} | {r['from_league']} | {r['to_league']} | {r['n']} | "
                     f"{r['mean_log_ratio']:.3f} | {r['shrunk_log_ratio']:.3f} | "
                     f"{r['factor']:.3f} | {flag} |")
    lines += ["", "## Prior checks (spec §7: violations surface, never hide)", ""]
    for metric, findings in prior_findings:
        lines.append(f"### {metric}")
        for f in findings:
            lines.append(f"- {f['pair'][0]} > {f['pair'][1]}: **{f['status']}**"
                         + (f" (diff CI {f['diff_ci'][0]:.3f}..{f['diff_ci'][1]:.3f})"
                            if "diff_ci" in f else f" — {f.get('detail','')}"))
        lines.append("")
    out = data_path("data_outputs") / "calibration_diagnostics.md"
    out.write_text("\n".join(lines), encoding="utf-8")
