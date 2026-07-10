# Contract: `fbref_player_season`

FBref standard player season stats (soccerdata, flattened columns).

| column | type | required |
|---|---|---|
| `player` | `<class 'str'>` | yes |
| `nation` | `typing.Optional[str]` | no (nullable) |
| `pos` | `typing.Optional[str]` | no (nullable) |
| `playing_time_min` | `typing.Optional[float]` | no (nullable) |
| `performance_gls` | `typing.Optional[float]` | no (nullable) |
| `performance_ast` | `typing.Optional[float]` | no (nullable) |
| `league` | `<class 'str'>` | yes |
| `season` | `<class 'int'>` | yes |

_Generated from `src/ingest/contracts_def.py`; edit the model, not this file._