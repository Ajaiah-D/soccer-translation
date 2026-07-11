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

## RESOLVED: Crosswalk false-positive spot-check (owner sign-off 2026-07-11)

- **Severity:** `info`
- **Added:** 2026-07-11
- **Artifact:** data/outputs/crosswalk_audit_sample.csv

Owner reviewed data/outputs/crosswalk_audit_sample.csv in full and confirmed every match is correct. The crosswalk is cleared for downstream use.

## RESOLVED: FBref coverage blocker (2026-07-11)

- **Severity:** `info`
- **Added:** 2026-07-11
- **Artifact:** data/outputs/coverage_report.md

All 16 FBref league-season slices are now cached (10,415 player-season rows) via the direct browser fetcher. Separately, FBref removed xG columns from its standard-stats pages, so Premier League xG/xA now comes from Understat's JSON endpoint - a plain-HTTP, fully repeatable path with no bot-protection interaction. The original blocker no longer constrains the calibration: ENG1 is in the league graph (n=24 moves touching, wide CI, honestly labeled).

## Crosswalk false positive found and fixed: cross-system name collision

- **Severity:** `info`
- **Added:** 2026-07-11
- **Artifact:** data/outputs/crosswalk_audit_sample.csv

After adding Premier League data, 'Amy Rodriguez' (NWSL) auto-matched to 'Jay Rodriguez' (Premier League, same seasons, ~92 name score, no birth years available to penalize), fabricating an NWSL->ENG1 move. Fixed systematically: players from disjoint league systems (mens/womens) can never match, enforced in the matcher and covered by a regression test. The audit sample was regenerated after the fix; the earlier owner sign-off predates Premier League data and this sample refresh.
