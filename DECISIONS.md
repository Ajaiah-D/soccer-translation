# DECISIONS.md - decision log (what was decided, alternatives, reasoning, reversibility)

Every non-trivial choice: what was decided, alternatives, reasoning, reversibility.

---

## D-023: Asymmetric minutes thresholds with precision weighting
- **Decided:** A move needs >=900 minutes in the ORIGIN season (trustworthy baseline) but only >=450 in the DESTINATION season, and every mover's log-ratio is weighted by the harmonic mean of the two seasons' minutes (in 90s). Shrinkage still uses raw mover counts.
- **Why:** The old symmetric 900/900 rule silently excluded partial failures abroad, biasing strong destination leagues toward "easy" (survivorship). Lowering only the destination side pulls those failures into the sample; minutes-weighting keeps short noisy stints from dominating. A sensitivity table in the diagnostics shows factors under both definitions.
- **Reversible:** yes (config movers.min_minutes_destination)

## D-024: Attrition metric quantifies invisible failed moves
- **Decided:** Phase 3 reports, per directed league pair, origin-qualified players who appeared in the destination league within the gap window but never reached the destination threshold - failed moves that cannot produce a ratio. Players who left covered leagues entirely remain an acknowledged undercount.
- **Why:** The factors cannot see total failures; reporting their frequency (e.g. 54% MLSNP->MLS, 43% USLC->MLS) lets a reader judge the residual survivorship instead of trusting a hidden assumption.
- **Reversible:** yes

## D-026: API-Football free tier as the wide-coverage source (resumable backfill)
- **Decided:** Player season stats for 16 leagues (Big 5, Portugal, Netherlands, Belgium, Championship, Brazil, Argentina, MLS, Austria, Switzerland, Denmark, Scotland) come from API-Football's free plan, pulled as a quota-bounded daily backfill. The free plan rejects any page past 3, so a league-wide listing (~50 pages) is unreachable; players are pulled per team instead (/teams per league-season, then /players?league&season&team, a squad fits in 3 pages of 20; any team needing more is reported as truncated). Every response is its own cached pull; each run reads the day's remaining quota from /status, keeps a reserve of 5, and skips cached responses. API errors are raised and never cached. `python -m src apif` runs one day's slice; `python -m src apif-status` reports progress offline.
- **Alternatives:** paid APIs (StatsBomb/Opta/Wyscout: out of budget; API-Football paid months unlock 2025+ and pre-2022 history), scraping a third-party Opta-based Streamlit site (licensing risk; owner being asked for a direct share instead), FBref one-time click-through backfill (standard stats only).
- **Why:** The only free source found that covers the leagues clubs actually buy from, with defensive stats (tackles, interceptions, blocks, duels) and birth dates, from one provider across all leagues (no cross-provider seam). Constraints verified live: free plan serves seasons 2022-2024 only and pages 1-3 only; per-team pulls cost about 1 + 3 x teams requests per league-season, roughly 2,600 requests for 48 league-seasons, about 28 days at 95/day.
- **Limits:** no xG or progression metrics; positions are only G/D/M/F; three seasons give two transfer windows (2023, 2024) for mover calibration; current-season form (2025+) is not reachable on the free plan. The catalog is not yet wired into harmonize/calibration.
- **Reversible:** yes (config seasons.api_football, api_football.* including max_page, league api_football ids)

## D-025: Wikidata birth-year enrichment for European movers
- **Decided:** Players lacking a birth year with substantial seasons in >=2 leagues are looked up on Wikidata (batched exact-label SPARQL, cached; human + association-footballer + single plausible birth year required; ambiguous names skipped and counted). First run: 688 of 954 filled, 49 ambiguous, 217 unmatched.
- **Why:** Understat has no birth dates, which blocked age adjustment for intra-European movers. With 72% coverage the age adjustment now applies to most of the European graph.
- **Reversible:** yes (cached lookups; enrichment only fills missing values, never overwrites)

## D-020: Age adjustment of mover deltas
- **Decided:** Mover log-ratios are adjusted by the expected age-driven change, using aging curves estimated from within-league consecutive season pairs in this project's own data (per-age bucket means, shrunk toward 0; config calibration.age_adjust / aging_shrinkage_k). Phase 5 estimates its curve without held-out persons' seasons.
- **Why:** Transatlantic movers have systematically asymmetric ages (Europe->MLS movers past peak, MLS->Europe movers pre-peak), so unadjusted deltas conflate aging with league strength - the mechanism behind the implausible "Big-5 weaker than MLS" first-pass numbers.
- **Reversible:** yes (config flag)

## D-021: Age-unknown movers keep unadjusted deltas (config age_adjust_unknown=keep)
- **Decided:** Movers without a birth year (mostly intra-European; Understat has no birth dates) are retained with raw deltas, flagged and counted, rather than excluded.
- **Alternatives:** exclude (tested: collapses the European graph, e.g. ENG1 n 453->39, CIs balloon); impute mean ages (rejected: silent-ish imputation).
- **Reasoning:** The age-asymmetry bias is concentrated in transatlantic edges, all of which HAVE birth years (ASA side) and get adjusted. Intra-European move-age profiles are roughly symmetric by direction, so their aggregate aging bias largely cancels within pairs. Enriching European birth years (e.g. Wikidata) is logged as future work.
- **Reversible:** yes (config)

## D-022: FiveThirtyEight SPI as external validation anchor
- **Decided:** League strengths are compared against mean club SPI per league (2016-2023), pulled from a pinned Internet Archive snapshot of the final SPI match file - fully automatic and permanently reproducible. Anchor-only leagues (EFL Championship, 2. Bundesliga) get SPI-based strength context without entering the mover calibration.
- **Why chosen over alternatives:** UEFA coefficients cover only continental-competition clubs (no MLS, no second tiers); FIFA ranks national teams; Opta's archive lacks league labels (mapping deferred); ClubElo is Europe-only. SPI is the only defunct-but-archived source with MLS + Big-5 + second tiers on one scale.
- **Limits (reported in diagnostics):** anchor ends early 2023; SPI measures club quality, not per-90 production conversion, so only ordering and rough magnitude are comparable.
- **Reversible:** yes

## D-017: FBref live fetching is opt-in (default off); pipeline is fully unattended
- **Decided:** `ingest.fbref_fetch_enabled: false` by default. FBref is treated as a frozen cached historical source; uncached slices surface as explicit coverage gaps. ASA and Understat cover all recurring needs without any interaction.
- **Why:** FBref's bot protection can demand an interactive verification click; the owner requires zero-intervention runs.
- **Reversible:** yes (flip the config flag)

## D-018: Seam consistency check uses goals (model-free), not FBref xG
- **Decided:** The MLS<->ENG1 seam check re-measures cross movers on goals per 90 three ways: FBref both sides (single provider, cached), mixed-source goals, and the production mixed xG+xA. No new scraping.
- **Why:** Goals are identically defined in every source, so they cannot carry xG-model bias; FBref's cached standard tables already have them for both leagues. The planned FBref-xG backfill (shooting pages) was dropped: it required an interactive click.
- **Result (first run):** single-provider goals factors agree with mixed-source ones within noise (e.g. ENG1->MLS 1.445 vs 1.404), supporting the production factor.
- **Reversible:** yes

## D-019: European coverage expanded to the Big-5 via Understat; second tiers out of scope
- **Decided:** Bundesliga, La Liga, Serie A, Ligue 1 added alongside the Premier League (config-only change; same Understat endpoint, fully automatic). Second-division European leagues (EFL Championship, 2. Bundesliga, ...) are NOT included: no open, fully-automatic per-player source exists (Understat lacks them; FBref needs interaction; FotMob/Sofascore gate their APIs).
- **Note:** Understat uses one global player id across its leagues, so intra-European moves link by id with no fuzzy matching.
- **UEFA coefficients were considered and rejected** as a strength substitute: they rank clubs/countries in continental competition, do not cover second divisions, and would replace the mover-based measurement this project exists to make.
- **Reversible:** yes

## D-016: Single-provider consistency check for the MLS<->ENG1 seam
- **Decided:** FBref's shooting pages (which still carry xG) are backfilled for MLS and ENG1 2018-2025 and merged into the FBref frames; Phase 4 diagnostics re-measure the MLS<->ENG1 movers with FBref xG on BOTH sides and report that factor next to the production (ASA xG vs Understat xG) estimate.
- **Why:** No fully-open source publishes xG for both MLS and the Premier League (ASA is US-only, Understat is Europe-only; fbrapi.com is dead, FotMob's API is gated behind signed app headers). The production factor therefore mixes two xG models; measuring the same movers within one provider cancels model bias and shows whether the seam distorts the estimate.
- **Scope:** the American-pyramid calibration is unaffected (single source, ASA, complete 2018-2025 for all six leagues). The FBref backfill is one-time, cached forever; recurring updates need only ASA + Understat, which run unattended.
- **Reversible:** yes

## D-014: Understat is the xG/xA source for European comparison leagues
- **Decided:** Premier League player-season xG/xA comes from Understat's JSON endpoint (POST /main/getPlayersStats/), cached like every source. FBref's cached standard tables remain for identity/minutes/goals.
- **Cause:** FBref removed the Expected (xG/xAG) columns from its standard-stats pages, and its bot protection requires an interactive verification that makes the browser path non-repeatable.
- **Trade-offs:** Understat provides no birth dates or nationalities (the crosswalk leans on name + season blocking + the league-system block); ASA and Understat xG models differ, but the conversion factor absorbs systematic scale differences by construction - noted as added uncertainty, not hidden.
- **Reversible:** yes

## D-015: League-system (mens/womens) hard block in the crosswalk
- **Decided:** Records whose league-system groups are disjoint can never match, regardless of name score. Groups are declared per league in config/leagues.yaml.
- **Cause:** A real false positive: Amy Rodriguez (NWSL) auto-matched to Jay Rodriguez (Premier League, overlapping seasons, ~92 name score, no birth years available), fabricating an NWSL->ENG1 move that put NWSL into the men's calibration graph.
- **Reversible:** yes (config + one matcher rule; regression-tested)

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
