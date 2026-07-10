# ASA API surface (live introspection)

Introspected on 2026-07-09 against the installed `itscalledsoccer` client
(`from itscalledsoccer.client import AmericanSoccerAnalysis`). Build against this,
not against memory (spec §2).

## Supported leagues (client constant `LEAGUES`)

`['nwsl', 'mls', 'uslc', 'usl1', 'usls', 'nasl', 'mlsnp']`

(`nasl` is defunct and out of project scope; the other six map to `config/leagues.yaml`.)

## `get_*` methods and signatures

| Method | Signature (abridged) |
|---|---|
| `get_players` | `(leagues, ids, names)` → identity table |
| `get_teams` | `(leagues, ids, names)` |
| `get_games` | `(leagues, game_ids, team_ids, team_names, season_name, ...)` |
| `get_managers` / `get_referees` / `get_stadia` | `(leagues, ids, names)` |
| `get_player_xgoals` | `(leagues, **kwargs)` |
| `get_player_xpass` | `(leagues, **kwargs)` |
| `get_player_goals_added` | `(leagues, **kwargs)` |
| `get_player_salaries` | `(leagues='mls', **kwargs)` |
| `get_goalkeeper_xgoals` / `get_goalkeeper_goals_added` | `(leagues, **kwargs)` |
| `get_game_xgoals` | `(leagues, **kwargs)` |
| `get_team_xgoals` / `get_team_xpass` / `get_team_goals_added` / `get_team_salaries` | `(leagues, **kwargs)` |

All filters are keyword arguments. Kwargs observed in docstrings for the player endpoints:
`minimum_minutes`, `minimum_shots`, `minimum_key_passes`, `minimum_passes`,
`player_ids` / `player_names` (mutually exclusive), `team_ids` / `team_names`,
`season_name`, `start_date`/`end_date`, `stage_name`, `split_by_teams`,
`split_by_seasons`, `split_by_games`, `general_position`.

We pull with `season_name=<year>` and `split_by_seasons=True` so every row is a
player × team × season observation.

## Observed response shapes (live probe: `usl1`, season 2023)

### `get_player_xgoals` (289 rows)
Columns: `player_id, team_id, season_name, general_position, minutes_played, shots,
shots_on_target, goals, xgoals, xplace, goals_minus_xgoals, key_passes, primary_assists,
xassists, primary_assists_minus_xassists, goals_plus_primary_assists,
xgoals_plus_xassists, points_added, xpoints_added`

### `get_player_goals_added` (260 rows)
Columns: `player_id, team_id, season_name, general_position, minutes_played, data`

`data` is a **nested list** of per-action-type dicts:
`{action_type, goals_added_raw, goals_added_above_avg, count_actions}` with action types
`Dribbling, Fouling, Interrupting, Passing, Receiving, Shooting`.
The ingest layer flattens this to wide columns before caching (parquet-safe) and computes
totals `goals_added_raw_total` / `goals_added_above_avg_total` as the sum across
action types.

### `get_player_xpass` (observed from cache)
Columns: `player_id, team_id, season_name, general_position, minutes_played,
attempted_passes, pass_completion_percentage, xpass_completion_percentage,
passes_completed_over_expected, passes_completed_over_expected_p100,
avg_distance_yds, avg_vertical_distance_yds, share_team_touches, count_games`

### `get_players` (1553 rows for usl1)
Columns: `player_id, player_name, birth_date, nationality, primary_broad_position,
primary_general_position, secondary_broad_position, secondary_general_position,
season_name, height_ft, height_in, weight_lb, competition`

## Usage etiquette

ASA asks for modest use. Ingest enforces: 1 req/sec rate limit, exponential backoff on
error (config `ingest.*`), and aggressive local caching — a season/league slice is
fetched exactly once and re-read from `data/raw/` thereafter.
