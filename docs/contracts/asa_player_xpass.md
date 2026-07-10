# Contract: `asa_player_xpass`

Player pass model per league-season (asa get_player_xpass, split_by_seasons).

| column | type | required |
|---|---|---|
| `player_id` | `<class 'str'>` | yes |
| `team_id` | `<class 'str'>` | yes |
| `season_name` | `<class 'str'>` | yes |
| `general_position` | `typing.Optional[str]` | no (nullable) |
| `minutes_played` | `<class 'int'>` | yes |
| `attempted_passes` | `<class 'int'>` | yes |
| `pass_completion_percentage` | `<class 'float'>` | yes |
| `xpass_completion_percentage` | `<class 'float'>` | yes |
| `passes_completed_over_expected` | `<class 'float'>` | yes |
| `share_team_touches` | `<class 'float'>` | yes |
| `league` | `<class 'str'>` | yes |
| `season` | `<class 'int'>` | yes |

_Generated from `src/ingest/contracts_def.py`; edit the model, not this file._