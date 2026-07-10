# Contract: `transfermarkt`

Market value / transfer labels (stub fixture or real feed).

| column | type | required |
|---|---|---|
| `player_name` | `<class 'str'>` | yes |
| `as_of_season` | `<class 'int'>` | yes |
| `market_value_eur` | `typing.Optional[float]` | no (nullable) |
| `transfer_fee_eur` | `typing.Optional[float]` | no (nullable) |
| `source` | `<class 'str'>` | yes |

_Generated from `src/ingest/contracts_def.py`; edit the model, not this file._