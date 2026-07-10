"""Phase 3 gate: known real movers appear correctly in the mover set.

These are documented, real transfers within the American pyramid, verified against
the ingested data. If a refactor of the mover logic drops them, this catches it.
"""

import pandas as pd
import pytest

from src.common.config import data_path

KNOWN_MOVERS = [
    # (name substring, from_league, to_league) - all with >=900 min on both sides
    ("Nathan Harriel", "USLC", "MLS"),     # Philadelphia Union path, 2020 -> 2022
    ("Fabian Herbers", "USLC", "MLS"),     # to Chicago Fire, 2018 -> 2020
    ("Milan Iloski", "USLC", "MLS"),       # Orange County SC -> MLS, 2023 -> 2025
]


@pytest.mark.gate_phase3
def test_known_real_movers_present():
    path = data_path("data_interim") / "movers.parquet"
    if not path.exists():
        pytest.skip("movers.parquet absent - run `python -m src phase3` first")
    moves = pd.read_parquet(path)
    for name, from_league, to_league in KNOWN_MOVERS:
        hit = moves[
            moves["player_name"].str.contains(name, case=False, na=False)
            & (moves["from_league"] == from_league)
            & (moves["to_league"] == to_league)
        ]
        assert len(hit) >= 1, f"known mover missing: {name} {from_league}->{to_league}"
