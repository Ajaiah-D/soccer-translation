# Cross-League Player Value Translation: Technical Report

Method, engineering decisions, and known limits. Companion to `CLUB_BRIEF.md`;
every number here regenerates from `python -m uv run python -m src all`.

## 1. Question and design

**Question:** how does per-90 player production translate between leagues of the
American pyramid and selected European leagues, and do strength-adjusted pre-move
metrics predict post-move outcomes?

**Design:** a mover-based calibration. Players who logged qualifying seasons in
two leagues are natural experiments; the within-player change in production,
corrected for age and weighted by playing time, estimates the pairwise conversion
factor. Pairwise factors are chained into a single strength scale over the league
graph. Everything is validated by retrodicting held-out movers against a
permutation baseline.

## 2. Data

| source | role | coverage | access |
|---|---|---|---|
| American Soccer Analysis (itscalledsoccer) | American pyramid metrics: g+ (action value), xG, xA, xPass, minutes, positions, birth dates | MLS, USLC, USL1, MLS NEXT Pro, NWSL, USL Super League; 2018-2025 | public API, rate-limited, cached |
| Understat (JSON endpoint) | European xG/xA, goals, minutes | Big-5 top flights, 2018-2025 | plain HTTP, cached |
| FBref (cached snapshots) | identity (birth years) + goals for MLS/EPL; single-provider seam check | MLS + EPL 2018-2025 | one-time cached; live fetch opt-in (bot wall) |
| Wikidata (SPARQL) | birth years missing from Understat | 688 of 954 multi-league players | batched exact-label queries, cached |
| FiveThirtyEight SPI (pinned Internet Archive snapshot) | external validation anchor; strength context for anchor-only leagues (EFL Championship, 2. Bundesliga) | 2016-2023 | permanent snapshot URL |

Totals: 52,587 normalized player-seasons, 18,036 resolved identities, 1,871
qualifying moves by 1,460 players.

Integrity rules enforced in code: no imputation (missing stays missing;
all-NaN aggregates stay NaN, never 0); every dropped or excluded row is counted
in a lineage log; every raw pull is cached with a manifest (source, params,
timestamp, row count, content hash) and re-runs are fully offline.

## 3. Identity resolution

ASA player ids are the identity backbone. Other sources match to it by blocked
fuzzy matching:

- blocking: candidates must share a season, at least one name token, and a
  league-system group (a mens/womens hard block added after a real false
  positive: Amy Rodriguez, NWSL, matched Jay Rodriguez, Premier League, at name
  score 92 with no birth years available to veto);
- scoring: rapidfuzz token_sort_ratio on transliterated, suffix-stripped names,
  with birth-year agreement bonus and a 25-point penalty for a 2+ year gap;
- acceptance at score >= 88; scores 70-88 quarantined for human audit, never
  auto-used; below 70 never matched;
- precision >= 0.90 asserted on a labeled fixture of tricky pairs (accents,
  diacritics, sibling traps); the production audit sample was human-reviewed.

Understat uses one global player id across its leagues, so intra-European moves
link by id with no fuzzy step.

## 4. Mover definition

A move is a pair of qualifying seasons in different leagues, destination strictly
later, within 2 seasons. Thresholds are asymmetric by design:

- origin >= 900 minutes (a trustworthy pre-move baseline);
- destination >= 450 minutes (pulls partial failures into the sample; the old
  symmetric 900 rule silently excluded them and flattered strong destinations).

Both a season-gap cap (aging confound) and the asymmetry are config values with a
sensitivity table in the diagnostics comparing factor estimates under 450 vs 900
destination thresholds.

**Attrition metric:** per directed pair, the share of origin-qualified players
who appeared in the destination league within the window but never reached 450
minutes. These moves produce no ratio, so their frequency is reported instead of
hidden: 54% MLSNP->MLS, 43% USLC->MLS, 10-25% between European top flights.
Players who left covered leagues entirely are an acknowledged undercount.

## 5. Estimation

Per mover and metric (xG+xA per 90 primary for cross-league work; ASA g+ per 90
inside the American pyramid):

1. observed change = log(to_rate / from_rate); non-positive sides excluded and
   counted (a zero rate carries no multiplicative information);
2. age adjustment: subtract the expected aging change, from curves estimated on
   within-league consecutive qualifying season pairs drawn from the 52,587
   player-season base (6,428 pairs for xG+xA, 4,861 for g+; per-age bucket means
   of delta-log, shrunk toward 0 with n/(n+25)); movers lacking birth years keep raw
   deltas (config: keep vs exclude; excluding collapses the European graph and
   the age-asymmetry bias is concentrated in transatlantic edges, all of which
   have birth years);
3. precision weight = harmonic mean of the two seasons' minutes, in 90s;
4. directed pair factor = weighted mean log-ratio, shrunk toward 0 by
   n/(n+4) - small samples are pulled toward "no difference", never trusted raw;
5. chaining: weighted least squares on the league graph, model
   log f(A->B) = s_A - s_B, anchored at MLS (s=0), weights = pair weight sums;
   solved by lstsq (rank-deficiency safe for disconnected components);
6. uncertainty: 1,000 bootstrap resamples over movers, percentile CIs, fixed
   seed 42 end to end.

Why multiplicative log-ratios: production rates are ratio-scaled and the spec of
the problem is a conversion factor; log space makes chaining additive and
shrinkage symmetric. The cost - zeros drop out - is exactly what the attrition
metric and destination-threshold sensitivity exist to expose.

## 6. Bias controls and what each one moved

| control | mechanism it kills | effect observed |
|---|---|---|
| age adjustment | Europe->MLS movers are past peak (decline read as "MLS hard"); MLS->Europe movers pre-peak (growth read as "Europe easy") | GER1/FRA1 rose above MLS; priors flipped to satisfied |
| destination 450 + minutes weighting | survivorship: failed moves invisible at 900 | Big-5 factors rose further; ENG1>MLS and ESP1>MLS became confident |
| shrinkage (n/(n+4)) | small-sample ratio noise | thin pairs sit near 1.0 with wide CIs instead of wild values |
| mens/womens block + season/token blocking | identity false positives poisoning factors | removed a fabricated NWSL->EPL edge |
| single-provider seam check | ASA-xG vs Understat-xG model bias in transatlantic edges | FBref-goals-both-sides factors agree with mixed-source (1.45 vs 1.40 ENG1->MLS); seam not driving results |
| prior monotonicity gate | silent absurdities | a confident violation of a footballing prior halts the pipeline; wide-CI violations surface in diagnostics |

## 7. Validation (the honest part)

- 50/50 split by person (a multi-move player cannot straddle the split).
- Strengths AND aging curves re-estimated on the train half only; held-out
  persons' seasons touch nothing.
- Leakage is enforced by a functional test: scrambling every post-move outcome
  column must produce byte-identical features, or the gate fails.
- Projection = pre-move rate x S_from / S_to. Skill = Spearman r between
  projected and actual for held-out movers, against a 2,000-shuffle permutation
  baseline.

Current result: r = 0.580, n = 372 usable held-out moves, permutation
p = 0.0005; strength adjustment cuts MAE 14% versus naive carry-over (0.052 vs
0.061). The binary "success" classifier is at chance (AUC 0.43) - sticking in a
new league depends on more than pre-move production, which is a finding, not a
failure: rate translation is predictable, opportunity is not.

## 8. External anchor

Mean club SPI per league (match-weighted, 2018-2022 window), normalized to MLS,
from a pinned Internet Archive snapshot of FiveThirtyEight's final match file.
Orderings agree with the mover-based scale. Magnitudes intentionally differ:
SPI measures club quality (Big-5 at 1.6-1.9x MLS); mover factors measure
individual production translation, which is flatter because players and roles
adapt. The anchor also provides the only strength context for the Championship
(1.20x MLS club quality) and 2. Bundesliga (0.88x), which lack open per-player
data. UEFA coefficients were evaluated and rejected: they cover only continental
qualifiers and would substitute an external opinion for the measurement this
project exists to make.

## 9. Current strengths (xG+xA per 90, bootstrap 90% CIs)

| league | strength | CI | moves touching |
|---|---|---|---|
| ENG1 | 1.36 | 1.14-1.64 | 491 |
| ESP1 | 1.25 | 1.05-1.50 | 347 |
| ITA1 | 1.15 | 0.96-1.40 | 356 |
| FRA1 | 1.12 | 0.93-1.34 | 391 |
| GER1 | 1.11 | 0.93-1.32 | 272 |
| MLS | 1.00 | anchor | 331 |
| USLC | 0.71 | 0.66-0.78 | 554 |
| USL1 | 0.68 | 0.62-0.75 | 314 |
| MLSNP | 0.58 | 0.54-0.64 | 380 |

All eight configured footballing priors satisfied; ENG1>MLS and ESP1>MLS with
CIs excluding zero.

## 10. Known limits

1. Transatlantic n (~130 direct moves) caps precision there; CIs are the claim.
2. Total failures abroad (never 450 minutes) stay outside the ratios; the
   attrition table quantifies frequency but not magnitude. An explicit selection
   model is the next methodological step.
3. Intra-European movers without resolvable birth years (28%) carry unadjusted
   deltas; defensible because intra-Europe move ages are roughly symmetric, but
   it is an approximation.
4. The anchor ends in early 2023; the 2023-2025 tail is mover-only.
5. Factors are league-average; team context, role, and style are unmodeled
   (deliberately - they are the next stage of the project, not this one).
6. Second-tier European leagues have no open per-player source; they appear via
   the anchor only.

## 11. Reproducibility and code map

Deterministic end to end: seed 42, hash-checked crosswalk, cached pulls with a
manifest, pinned uv lockfile, 51 tests including per-phase acceptance gates
(`python -m uv run python -m src all` runs phases and gates in order).

| component | where |
|---|---|
| ingest (ASA, Understat, FBref, SPI anchor, Wikidata) | `src/ingest/` |
| identity + per-90 normalization | `src/harmonize/` |
| movers, attrition, aging, factors, chaining | `src/calibration/` |
| holdout validation, leakage test, permutation | `src/validate/` |
| decisions log / review queue / run report | `DECISIONS.md`, `REVIEW_QUEUE.md`, `RUN_REPORT.md` |
| per-run diagnostics (curves, seam check, anchor, sensitivity) | `data/outputs/calibration_diagnostics.md` |

Every methodological choice above has a numbered entry in `DECISIONS.md` with
alternatives considered and a reversibility flag.
