# Metric glossary

## Goals added (g+) - ASA

**Source definition:** https://www.americansocceranalysis.com/what-are-goals-added
(read 2026-07-09; summary below is grounded in that page and the live API fields).

**Plain-language summary.** Goals added measures a player's total on-ball contribution
in attack and defense. Every touch is valued by how much it changes the team's
probability of scoring *minus* its probability of conceding over the next two
possessions:

> g+ of an action = (P(score after) - P(concede after)) - (P(score before) - P(concede before))

Example from ASA: a throughball moving the game state from (1.5% score, 1.0% concede)
to (6.0% score, 0.5% concede) is worth (0.060-0.005) - (0.015-0.010) = **+0.050 g+**.
Pass value is split between passer and receiver (harder passes split more evenly).
g+ gives no credit for the goal itself - it values the actions that create and prevent
goals, not finishing outcomes.

**Action types (exact API values):** `Dribbling`, `Fouling`, `Interrupting`, `Passing`,
`Receiving`, `Shooting`.

**Exact API fields (from `get_player_goals_added`):** per action type - 
`goals_added_raw` (total g+ from those actions), `goals_added_above_avg`
(g+ relative to a league-average player with the same actions), `count_actions`.
Our ingest flattens these to wide columns (`ga_raw_<action>`, `ga_above_avg_<action>`,
`ga_count_<action>`) and computes `goals_added_raw_total` / `goals_added_above_avg_total`
as sums across the six action types.

**g+ is NOT xG.** g+ is an *action-value* framework covering all on-ball actions
(including defensive ones); xG is a *shot-quality* model estimating the probability a
given shot becomes a goal. They are never interchangeable in this codebase: g+ fields
are named `goals_added_*`, xG fields `xgoals*`, and no calculation mixes them as
substitutes.

## Expected goals (xG) - ASA / FBref

Probability, at the moment of a shot, that the shot results in a goal, summed over a
player's shots. ASA field: `xgoals` (with `xplace` adjusting for shot placement,
`goals_minus_xgoals` as finishing over/under-performance). FBref field: `xg`.

## Expected assists / xPass - ASA

- `xassists`: xG value expected to accrue from a player's key passes.
- xPass endpoint: pass-completion model - `pass_completion_percentage` vs
  `expected_pass_completion_percentage`, `passes_completed_over_expected`, per-100-pass
  variants, and `share_team_touches`.

## Per-90 normalization

All rate metrics downstream are per-90: `metric_per90 = metric_total / minutes_played * 90`.
Formulas and source columns for every derived metric live in `docs/data_dictionary.md`
(written by Phase 2).
