# Cross-League Player Value Translation Engine

A reproducible pipeline that estimates how player performance translates between
leagues of the American soccer pyramid (and selected comparison leagues), calibrated
from players who actually moved, and validated by retrodicting held-out movers.

## What it does

1. **Ingest** (Phase 1): player-season metrics from American Soccer Analysis
   (goals added, xG, xPass for MLS / USL Championship / USL League One / MLS NEXT Pro /
   NWSL / USL Super League), FBref standard stats (MLS + Premier League), and a
   Transfermarkt stub. All pulls cached to `data/raw/` with a manifest; re-runs are
   fully offline.
2. **Harmonize** (Phase 2): one player identity across sources (blocked fuzzy matching
   with a confidence score and a human audit sample) and all metrics normalized to a
   common per-90 schema (`docs/data_dictionary.md`).
3. **Movers** (Phase 3): players with 900+ minute seasons in two different leagues
   within a 2-season window.
4. **Calibrate** (Phase 4): pairwise league conversion factors from mover log-ratios,
   shrunk toward 1.0 for small samples, chained to MLS = 1.0 by weighted least squares,
   with bootstrap confidence intervals.
5. **Validate** (Phase 5): held-out movers are projected using factors re-estimated on
   the training half only; skill is tested against a permutation baseline and an
   explicit verdict (signal / no signal / inconclusive) is proposed for human review.

## Quickstart

```
# setup (uses uv; installs pinned deps from uv.lock)
python -m uv sync

# run everything (phases 1-5 + gates + run report)
python -m uv run python -m src all

# or per phase
python -m uv run python -m src phase1   # add --refresh to re-pull sources
python -m uv run python -m src phase2
...

# tests
python -m uv run pytest
```

On POSIX systems `make setup`, `make all`, `make phase1` ... wrap the same commands.

## Key outputs

| artifact | what it is |
|---|---|
| `RUN_REPORT.md` | top-level aggregation of every phase artifact + review queue |
| `data/outputs/coverage_report.md` | metric x league x season coverage, gaps explicit |
| `data/crosswalk/player_crosswalk.parquet` | cross-source identity with confidence |
| `data/outputs/crosswalk_audit_sample.csv` | match sample for human spot-check |
| `data/interim/movers.parquet` | qualifying moves with pre/post metric vectors |
| `data/outputs/league_strength.parquet` | league factors + bootstrap CIs |
| `data/outputs/calibration_diagnostics.md` | n per pair, shrinkage, prior checks |
| `data/outputs/proof_of_concept.md` | held-out retrodiction + verdict |
| `DECISIONS.md` / `REVIEW_QUEUE.md` | decision log / human review queue |

## Honesty guarantees

- No silent imputation; dropped or excluded rows are counted in a lineage log.
- Small samples are shrunk toward "no effect" and flagged, never hidden.
- The validation re-estimates factors without the held-out movers (no label leakage,
  enforced by a test that scrambles outcomes and asserts identical features).
- The proof-of-concept must beat shuffled labels, not just "look good".
