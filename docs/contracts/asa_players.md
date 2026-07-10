# Contract: `asa_players`

Identity table: one row per player per league (asa get_players).

| column | type | required |
|---|---|---|
| `player_id` | `<class 'str'>` | yes |
| `player_name` | `<class 'str'>` | yes |
| `birth_date` | `typing.Optional[str]` | no (nullable) |
| `nationality` | `typing.Optional[str]` | no (nullable) |
| `primary_broad_position` | `typing.Optional[str]` | no (nullable) |
| `primary_general_position` | `typing.Optional[str]` | no (nullable) |
| `league` | `<class 'str'>` | yes |

_Generated from `src/ingest/contracts_def.py`; edit the model, not this file._