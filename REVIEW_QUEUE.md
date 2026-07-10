# REVIEW_QUEUE.md — human review queue (spec §0.3)

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

League pairs below the thin-sample floor (5): MLS→USL1 (n=2). Factors touching these pairs are shrunk hard toward 1.0 and flagged low-confidence; treat their orderings as unproven.

## Proof-of-concept signal interpretation (verdict ratification)

- **Severity:** `must-review-before-trusting-results`
- **Added:** 2026-07-10
- **Artifact:** data/outputs/proof_of_concept.md

Agent-proposed verdict: **signal** — projected vs actual Spearman r=0.530 beats shuffled labels (p=0.0005, n=303). With thin mover samples, distinguishing real signal from noise is a judgment call: the human ratifies or overrides this verdict before any Stage 3/4/6 work is unlocked.
