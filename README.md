# Cross-League Player Value Translation Engine

A reproducible pipeline that estimates how player performance translates between
leagues of the American soccer pyramid (and selected comparison leagues), calibrated
from players who actually moved, and validated by retrodicting held-out movers.

## What it does

1. **Ingest** (Phase 1): player-season data, 2018-2025, from:
   - **American Soccer Analysis** via `itscalledsoccer` (goals added, xG, xPass for
     MLS / USL Championship / USL League One / MLS NEXT Pro / NWSL / USL Super League).
   - **Understat** JSON endpoint for xG/xA in the Big-5 European leagues (Premier
     League, Bundesliga, La Liga, Serie A, Ligue 1). Plain HTTP, runs unattended (D-014, D-019).
   - **FBref**, cache-first: already-cached slices (MLS, Premier League) are always used.
     Live fetching uses a short Selenium/Chrome session and is **opt-in** with
     `ingest.fbref_fetch_enabled` in `config/settings.yaml` (default `false`), because
     FBref's bot protection can ask for a manual verification click (D-013, D-017).
   - **Transfermarkt**: a stub that serves a hand-entered fixture
     (`tests/fixtures/transfermarkt_fixture.csv`) until a real feed exists. It does not
     affect the proof-of-concept verdict.

   All pulls are cached to `data/raw/` with a manifest, so re-runs are fully offline.
   Seasons, leagues and rate limits live in `config/settings.yaml` and `config/leagues.yaml`.
2. **Harmonize** (Phase 2): one player identity across sources (blocked fuzzy matching
   with a confidence score and a human audit sample) and all metrics normalized to a
   common per-90 schema (`docs/data_dictionary.md`). Players with no birth year
   (Understat has none) who could be movers get one from **Wikidata** (cached SPARQL
   lookups; names that match several players are skipped, never guessed; D-025).
3. **Movers** (Phase 3): players with 900+ minutes in the origin season and 450+ in
   the destination season, in two different leagues within a 2-season window (D-023).
4. **Calibrate** (Phase 4): pairwise league conversion factors from age-adjusted mover
   log-ratios, shrunk toward 1.0 for small samples, chained to MLS = 1.0 by weighted
   least squares, with bootstrap confidence intervals. Results are compared against
   **FiveThirtyEight SPI** club ratings, read from a pinned Internet Archive snapshot.
   SPI is only used to check the results, never as an input. It is also the only
   strength estimate for EFL Championship and 2. Bundesliga (D-020, D-022).
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

**Fresh clone:** `data/raw/manifest.json` is committed, but the parquet files it lists
are gitignored, so a fresh clone has the manifest without the data. The manifest stays
committed as a record of where every pull came from. `phase1` re-pulls the ASA and
Understat entries, and the Phase 1 manifest gate (`tests/data/test_artifact_gates.py`)
only checks files for the sources Phase 1 pulls: ASA and Understat, plus FBref when
`ingest.fbref_fetch_enabled` is `true` (D-027). It still checks that every entry has
the required fields. The other entries' files are rebuilt elsewhere: Wikidata in
Phase 2, SPI in Phase 4, API-Football by `apif`, and FBref only when live fetching is
on. So on a fresh clone, running `phase1` is enough for its gate to pass. Phases 2 and 4
re-pull their Wikidata and SPI files over the network when they are missing.

### API-Football catalog (wide league coverage, daily backfill)

Needs a free key from dashboard.api-football.com in a gitignored `.env` file
(`API_FOOTBALL_KEY=...`). The free plan allows 100 requests/day, seasons
2022-2024, and pages 1-3 only, so players are pulled per team and the catalog
fills over about four weeks; every run resumes where the last one stopped.

```
python -m uv run python -m src apif          # spend today's quota on uncached pages
python -m uv run python -m src apif-status   # progress, from cache only (no network)
scripts\apif_daily.cmd                        # same as apif, logged to logs\ (for Task Scheduler)
```

What it pulls: per-player season stats (minutes, position, shots, key passes, tackles,
interceptions, duels, dribbles, birth dates) for the 16 leagues in `config/leagues.yaml`
that have an `api_football` id: the Big 5, Portugal, Netherlands, Belgium, Championship,
Brazil, Argentina, MLS, Austria, Switzerland, Denmark and Scotland. That is 48
league-seasons, about 2,600 requests. Each run reads the day's remaining quota from
`/status` and keeps `api_football.daily_reserve` (5) requests unused, so a full day's
run makes about 95 requests. Every response is cached and listed in the manifest. API
errors are never cached, so a refused request is retried on a later run. Progress is
written to `data/outputs/api_football_catalog.md`.

On this machine a daily Windows Task Scheduler job, **"soccer-translation apif
backfill"**, runs `scripts\apif_daily.cmd` every evening and appends to
`logs\apif_daily.log`.

**Status (DECISIONS.md D-026):** "The catalog is not yet wired into
harmonize/calibration." The backfill only fills the raw cache. None of its data reaches
Phases 2-5, the league factors or `RUN_REPORT.md`. Leagues that only API-Football
covers (POR1, NED1, BEL1, BRA1, ARG1, AUT1, SUI1, DEN1, SCO1) are not calibrated, and
ENG2 is still anchor-only. Known limits: no xG or progression metrics, positions are
only G/D/M/F, and the free plan cannot reach 2025+ seasons.

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
| `data/outputs/api_football_catalog.md` | API-Football backfill progress (not part of phases 1-5) |
| `docs/CLUB_BRIEF.md` / `docs/TECHNICAL_REPORT.md` | write-ups for scouts / technical readers |
| `DECISIONS.md` / `REVIEW_QUEUE.md` | decision log / human review queue |

### Two calibration metrics: why the factors don't match

Phase 4 calculates factors separately for each metric in `calibration.metrics`, so the
same league has a different factor under each metric:

- **`xg_xa_per90`** (xG + xA per 90): available for every calibrated league, US and
  European. `docs/CLUB_BRIEF.md` and the portfolio website use this metric, e.g.
  **USLC 0.71**, USL1 0.68, MLSNP 0.58, ENG1 1.36.
- **`goals_added_raw_per90`** (ASA goals added per 90): ASA-only, so it covers the US
  leagues only. This is `validation.primary_metric`, so `RUN_REPORT.md`'s "Key numbers"
  line uses it, e.g. **USLC 0.79**, USL1 0.73, MLSNP 0.64.

The two sets measure different things and do not conflict. When you quote a factor,
name its metric. These are the numbers from the current run; rerunning the pipeline
can change them.

## Headline result (current run)

- **1,871 qualifying moves** by 1,460 players, 2018-2025, across nine leagues: the
  five European top flights plus MLS, USL Championship, USL League One and MLS NEXT Pro.
- **League strengths** (`xg_xa_per90`, MLS = 1.00): Premier League 1.36, La Liga 1.25,
  Serie A 1.15, Ligue 1 1.12, Bundesliga 1.11, USLC 0.71, USL1 0.68, MLS NEXT Pro 0.58.
- **Validation:** on 372 held-out moves, projected vs actual output has Spearman
  r = 0.580 (permutation p = 0.0005), and the strength adjustment cuts mean absolute
  error from 0.0606 to 0.0520 against an unadjusted projection. The held-out test uses
  `goals_added_raw_per90`, which only exists for the US leagues, so it validates the
  American-pyramid factors. The European factors are checked against SPI ordering, not
  against held-out movers.
- **Limit:** the projection ranks movers well but is not a good yes/no predictor of
  who will succeed (success-classification AUC 0.43, not better than chance).
- **Moves that fail:** 54% of MLS NEXT Pro players who moved up to MLS never reached 450
  minutes there (`data/outputs/movers_summary.md`).

Sources: `RUN_REPORT.md`, `data/outputs/proof_of_concept.md`, `docs/CLUB_BRIEF.md`.

## Honesty guarantees

- No silent imputation; dropped or excluded rows are counted in a lineage log.
- Small samples are shrunk toward "no effect" and flagged, never hidden.
- The validation re-estimates factors without the held-out movers (no label leakage,
  enforced by a test that scrambles outcomes and asserts identical features).
- The proof-of-concept must beat shuffled labels, not just "look good".
