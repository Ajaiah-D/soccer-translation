# DECISIONS.md - decision log (what was decided, alternatives, reasoning, reversibility)

Every non-trivial choice: what was decided, alternatives, reasoning, reversibility.

---

## D-013: FBref fetching moved from soccerdata to a direct browser fetcher
- **Decided:** Replace the soccerdata scrape path with src/ingest/fbref_direct.py: one short Selenium session with the locally installed Chrome renders each missing league-season stats page (the site requires JavaScript execution; the first page may need a single human click on its verification checkbox, which clears the whole session), pages are spaced 6 seconds apart, and the standard table is parsed out of its HTML comment wrapper into the same column schema the old path produced.
- **Alternatives:** keep soccerdata (its driver kept dying mid-session on this machine); plain HTTP with TLS impersonation (blocked: the protection layer demands JS execution); manual table downloads (owner explicitly declined).
- **Reasoning:** The browser path is the only one that worked reliably here; volume is tiny (one page per league-season, cached forever) and request spacing stays well under the site's published limits.
- **Reversible:** yes (the cached_pull layer is unchanged; any fetcher that returns the same frame works)

## D-001: Task runner = Makefile + `python -m src` CLI (dual)
- **Decided:** Provide a Makefile for POSIX/CI *and* a cross-platform `python -m src <phase>` CLI; both call the same entry points. Documentation treats the CLI as primary on this Windows host.
- **Alternatives:** Makefile only (spec default); install GNU make on Windows.
- **Reasoning:** `make` is absent on the build host. Spec section 0.6 explicitly allows "a CLI". Dual keeps `make phaseN` working elsewhere.
- **Reversible:** yes

## D-002: Python 3.12 toolchain via uv, not system Python 3.14
- **Decided:** Pin `requires-python = ">=3.12,<3.13"` and let uv provision 3.12.
- **Alternatives:** system Python 3.14.
- **Reasoning:** soccer-data libraries and their compiled deps lag newest CPython; 3.12 is the safest widely-supported pin. uv.lock pins all dependency versions (spec section 0.6).
- **Reversible:** yes

## D-003: Seasons 2018-2025 for both ASA and FBref
- **Decided:** Pull 2018-2025 inclusive (configurable in `config/settings.yaml`).
- **Alternatives:** all ASA history (2013+); shorter window.
- **Reasoning:** Wide enough to capture movers across the modern pyramid (MLS NEXT Pro from 2022, USL Super League from 2024 appear where they exist); avoids very old seasons whose metric definitions and league composition differ, and keeps API load modest per ASA's request.
- **Reversible:** yes (config change + `--refresh`)

## D-004: European comparison scope = Premier League only (FBref)
- **Decided:** Start with ENG-Premier League as the sole European league.
- **Alternatives:** Big-5 leagues; Championship.
- **Reasoning:** FBref scraping is slow and aggressively rate-limited; the MVP's calibration lives mostly inside the American pyramid (ASA covers all its leagues). One European anchor exercises the cross-source path without hammering FBref. More leagues = config addition later.
- **Reversible:** yes

## D-006: Failed FBref league-season scrapes are cached as explicit empty gaps
- **Decided:** If a scrape fails after soccerdata's retries, the slice is cached empty and shows as MISSING in the coverage report; `--refresh` retries it.
- **Alternatives:** abort the run; retry every run (violates the 0-network-calls cache gate).
- **Reasoning:** Surfacing beats stalling (section 0.1); the gap is explicit, never silent.
- **Reversible:** yes (`--refresh`)

## D-007: ASA row wins when both sources cover the same person-league-season
- **Decided:** For MLS seasons present in both ASA and FBref, the ASA row is kept (richer metrics: g+, xPass); the duplicate drop is recorded in the lineage log.
- **Reversible:** yes

## D-008: Mover definition
- **Decided:** A move = consecutive qualifying seasons (>=900 min, config) in different leagues, destination strictly later and within 2 seasons (config `movers.max_season_gap`).
- **Alternatives:** any-gap transitions; same-season loan pairs.
- **Reasoning:** Long gaps confound league effect with aging/career drift; same-season splits are ambiguous about ordering.
- **Reversible:** yes

## D-009: Calibration on multiplicative log-ratios of positive rates only
- **Decided:** Conversion factors are estimated from log(to/from) of `xg_xa_per90` and `goals_added_raw_per90`, excluding (and counting) movers with a non-positive value on either side. Shrinkage: mean log-ratio x n/(n+k), k=4. Chaining: WLS on the league graph anchored at MLS=1.0, weights = pair n.
- **Alternatives:** additive deltas (handles negatives but doesn't match the spec's factor-toward-1.0 shrinkage); ratios with epsilon floors (distorts small rates).
- **Reasoning:** Spec mandates multiplicative factors shrunk toward 1.0; exclusion counts are logged and reported rather than imputed.
- **Reversible:** yes

## D-010: Phase 5 re-estimates strengths on the train half only
- **Decided:** The proof-of-concept re-runs calibration on the non-holdout movers and projects the holdout with those factors, even though Phase 4's published factors use all movers.
- **Reasoning:** Using all-mover factors would let each held-out mover's own post-move season influence its projection - label leakage. The published Phase 4 artifact remains the all-data estimate; the validation is the honest test.
- **Reversible:** no (methodological requirement)

## D-011: Success definition (validation.*)
- **Decided:** success = (post-move minutes / pre-move minutes >= 0.5) AND (actual post-move primary metric >= 75% of the strength-adjusted projection). Primary metric: goals_added_raw_per90.
- **Alternatives:** market-value growth (needs real Transfermarkt feed); league-median benchmarks.
- **Reasoning:** Matches the spec's example ("retained minutes share + non-negative g+ delta"), uses only data we ingest reliably, and does not depend on the hand-entered Transfermarkt stub.
- **Reversible:** yes (config)

## D-012: FBref coverage accepted as partial (BLOCKER logged)
- **Decided:** After repeated failed attempts (initial run, fresh-process retries, one final time-boxed attempt per approach), FBref slices other than MLS 2018 and MLS 2022 are recorded as explicit empty gaps. A BLOCKER item is in REVIEW_QUEUE.md.
- **Cause:** The scraping stack (headless Chrome driver behind FBref's bot protection) dies mid-session on this machine; ~2/8 success rate, minutes per attempt, all attempts after the first minutes of a session fail.
- **Impact:** Cross-source crosswalk is exercised end to end on the two good MLS slices. ENG1 never enters the calibration graph, so the ENG1>MLS prior is reported "untestable" rather than tested. The American-pyramid core (all-ASA) is unaffected.
- **Retry path:** `python -m src phase1 --refresh` (or delete the empty fbref entries from data/raw/manifest.json) on a machine/network where FBref scraping works.
- **Reversible:** yes

## D-005: Empty API results are cached
- **Decided:** A pull that legitimately returns zero rows is cached as an empty frame with `content_hash="empty"`.
- **Alternatives:** re-fetch empties every run.
- **Reasoning:** "No data for this league/season" is a real answer (e.g. USL Super League before 2024). Caching it keeps re-runs at 0 network calls (Phase 1 gate).
- **Reversible:** yes
