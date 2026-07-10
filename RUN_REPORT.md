# RUN REPORT - Cross-League Player Value Translation Engine

_Generated 2026-07-10 05:16 UTC by `python -m src report`._

## Key numbers

- normalized player-seasons: **21791** ({'asa': 20415, 'fbref': 1376})
- qualifying moves: **689** across 576 players
- league strengths (goals_added_raw_per90, anchor MLS=1.0): MLS 1.00, USLC 0.82, USL1 0.76, MLSNP 0.64
- proof-of-concept verdict: **signal** - projected vs actual Spearman r=0.530 beats shuffled labels (p=0.0005, n=303)

## Artifacts by phase

| phase | artifact | path | exists |
|---|---|---|---|
| Phase 1 | Coverage report | `data/outputs/coverage_report.md` | yes |
| Phase 1 | ASA API surface | `docs/asa_api_surface.md` | yes |
| Phase 1 | Metric glossary (incl. g+) | `docs/metric_glossary.md` | yes |
| Phase 1 | Data contracts | `docs/contracts/` | yes |
| Phase 2 | Player crosswalk | `data/crosswalk/player_crosswalk.parquet` | yes |
| Phase 2 | Crosswalk audit sample (HUMAN REVIEW) | `data/outputs/crosswalk_audit_sample.csv` | yes |
| Phase 2 | Unmatched report | `data/outputs/crosswalk_unmatched_report.md` | yes |
| Phase 2 | Data dictionary | `docs/data_dictionary.md` | yes |
| Phase 3 | Mover set | `data/interim/movers.parquet` | yes |
| Phase 3 | Movers summary | `data/outputs/movers_summary.md` | yes |
| Phase 4 | League strengths (+CI) | `data/outputs/league_strength.parquet` | yes |
| Phase 4 | Calibration diagnostics | `data/outputs/calibration_diagnostics.md` | yes |
| Phase 5 | Proof-of-concept verdict (HUMAN REVIEW) | `data/outputs/proof_of_concept.md` | yes |
| All | Decision log | `DECISIONS.md` | yes |
| All | Review queue | `REVIEW_QUEUE.md` | yes |
| All | Data lineage log | `data/outputs/data_lineage.jsonl` | yes |

## Human review queue (verbatim)

# REVIEW_QUEUE.md - human review queue (items a reviewer should check before trusting results)

Severity levels: `info` | `should-review` | `must-review-before-trusting-results`

Items are appended, never removed. The two guaranteed entries (crosswalk audit,
proof-of-concept signal) are added by Phases 2 and 5.

---

## Crosswalk false-positive spot-check

- **Severity:** `must-review-before-trusting-results`
- **Added:** 2026-07-10
- **Artifact:** data/outputs/crosswalk_audit_sample.csv

Fuzzy matching can bind two different players; a single bad high-usage match can poison a league factor. Spot-check the audit sample (random accepted + low-confidence buckets) for false positives.

## Thin league-pair samples constrain calibration claims

- **Severity:** `should-review`
- **Added:** 2026-07-10
- **Artifact:** data/outputs/movers_summary.md

League pairs below the thin-sample floor (5): MLS->USL1 (n=2). Factors touching these pairs are shrunk hard toward 1.0 and flagged low-confidence; treat their orderings as unproven.

## Proof-of-concept signal interpretation (verdict ratification)

- **Severity:** `must-review-before-trusting-results`
- **Added:** 2026-07-10
- **Artifact:** data/outputs/proof_of_concept.md

Proposed verdict: **signal** - projected vs actual Spearman r=0.530 beats shuffled labels (p=0.0005, n=303). With thin mover samples, distinguishing real signal from noise is a judgment call: the human ratifies or overrides this verdict before any Stage 3/4/6 work is unlocked.

## BLOCKER: FBref coverage is partial (scrape stack failure)

- **Severity:** `must-review-before-trusting-results`
- **Added:** 2026-07-10
- **Artifact:** data/outputs/coverage_report.md

Only MLS 2018 and MLS 2022 scraped successfully from FBref; MLS 2019-2021/2023-2025 and all ENG-Premier League seasons are explicit empty gaps after repeated failed attempts (headless-driver/bot-protection failure on the build machine, see DECISIONS.md D-012). Consequence: the ENG1>MLS strength prior is untestable and any Europe-facing claims are out of scope for this run. Retry with python -m src phase1 --refresh on a machine where FBref scraping works.

## Transfermarkt real feed request

- **Severity:** `should-review`
- **Added:** 2026-07-10
- **Artifact:** src/ingest/transfermarkt.py

The Transfermarkt source is a stub backed by a small hand-entered fixture (interface documented in src/ingest/transfermarkt.py). Market-value validation labels stay out of the proof-of-concept until the owner provides the real scraper/feed.
