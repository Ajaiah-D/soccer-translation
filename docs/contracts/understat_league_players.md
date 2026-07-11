# Contract: `understat_league_players`

Understat player-season xG data (POST /main/getPlayersStats/).

| column | type | required |
|---|---|---|
| `id` | `<class 'str'>` | yes |
| `player_name` | `<class 'str'>` | yes |
| `time` | `<class 'float'>` | yes |
| `goals` | `<class 'float'>` | yes |
| `xG` | `<class 'float'>` | yes |
| `assists` | `<class 'float'>` | yes |
| `xA` | `<class 'float'>` | yes |
| `position` | `typing.Optional[str]` | no (nullable) |
| `league` | `<class 'str'>` | yes |
| `season` | `<class 'int'>` | yes |

_Generated from `src/ingest/contracts_def.py`; edit the model, not this file._