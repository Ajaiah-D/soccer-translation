# Contract: `asa_player_xgoals`

Player xG per league-season (asa get_player_xgoals, split_by_seasons).

| column | type | required |
|---|---|---|
| `player_id` | `<class 'str'>` | yes |
| `team_id` | `<class 'str'>` | yes |
| `season_name` | `<class 'str'>` | yes |
| `general_position` | `typing.Optional[str]` | no (nullable) |
| `minutes_played` | `<class 'int'>` | yes |
| `shots` | `<class 'int'>` | yes |
| `goals` | `<class 'int'>` | yes |
| `xgoals` | `<class 'float'>` | yes |
| `key_passes` | `<class 'int'>` | yes |
| `primary_assists` | `<class 'int'>` | yes |
| `xassists` | `<class 'float'>` | yes |
| `league` | `<class 'str'>` | yes |
| `season` | `<class 'int'>` | yes |

_Generated from `src/ingest/contracts_def.py`; edit the model, not this file._