# Extension points (seams for Stages 3 / 4 / 6)

These stages are **explicitly out of scope** for this run (spec §1) and unlock only
after the Phase 5 review-queue item is ratified by the human. The seams below are the
interfaces they consume.

## Stage 3 — stylistic-translation model

Consumes:
- `data/interim/person_seasons.parquet` — one row per person × league × season, unified
  per-90 schema (see `docs/data_dictionary.md`). Style features (pass profiles, touch
  shares) extend this frame; `share_team_touches` and `pass_pct_over_expected` are the
  first two style-ish columns already present.
- `data/outputs/league_strength.parquet` — strength context per league × metric with CIs.

Contract to honor: add new metrics as new columns with a data-dictionary entry
(formula + source); never redefine existing columns.

## Stage 4 — valuation / projection ML model

Consumes:
- `data/interim/movers.parquet` — one row per move with `from_*`/`to_*` metric vectors.
- `src/validate/retrodict.py::build_features(holdout, strengths, metric)` — the
  leakage-safe feature builder. Any richer model MUST route its features through this
  function (or one with the same scrambling-invariance test) so the Phase 5 leakage
  gate keeps applying.
- `src/ingest/transfermarkt.py::get_player_valuations()` — swap the fixture for the
  real feed behind the same signature to obtain market-value labels.

## Stage 6 — Streamlit app

Consumes read-only artifacts:
- `data/outputs/league_strength.parquet` (factors + CIs)
- `data/interim/person_seasons.parquet` (player pages)
- `data/outputs/proof_of_concept.md` (methodology honesty page)

Conversion of a per-90 rate from league A to B:
`rate * strength[A] / strength[B]` (per metric; CIs travel with the estimate).

## Runner seams

- Each phase is `src.<module>.run_phaseN()` invoked by `python -m src phaseN`; new
  stages should follow the same pattern and add a `gate_phaseN` pytest marker.
