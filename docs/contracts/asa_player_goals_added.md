# Contract: `asa_player_goals_added`

Player g+ per league-season, flattened from the nested action-type payload.
    g+ is an action-value framework, NOT xG - see docs/metric_glossary.md.

| column | type | required |
|---|---|---|
| `player_id` | `<class 'str'>` | yes |
| `team_id` | `<class 'str'>` | yes |
| `season_name` | `<class 'str'>` | yes |
| `general_position` | `typing.Optional[str]` | no (nullable) |
| `minutes_played` | `<class 'int'>` | yes |
| `goals_added_raw_total` | `typing.Optional[float]` | no (nullable) |
| `goals_added_above_avg_total` | `typing.Optional[float]` | no (nullable) |
| `league` | `<class 'str'>` | yes |
| `season` | `<class 'int'>` | yes |

_Generated from `src/ingest/contracts_def.py`; edit the model, not this file._