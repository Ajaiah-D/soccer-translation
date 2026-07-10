"""Transfermarkt interface - STUB backed by a hand-entered fixture (pending a real feed).

The owner has not provided a real scraper, so this module defines the interface the
real feed must satisfy and serves data from a small hand-entered fixture covering
proof-of-concept movers. A review-queue item requests the real feed.

Interface contract (what a real implementation must return):

    get_player_valuations(refresh: bool = False) -> pd.DataFrame with columns:
        player_name      str  - player's common display name
        birth_year       int? - for disambiguation
        nationality      str? - ISO-ish country name
        as_of_season     int  - season the valuation refers to
        market_value_eur float?- Transfermarkt market value in EUR (NaN if unknown)
        transfer_fee_eur float?- fee if a transfer occurred that season (NaN otherwise)
        from_league      str? - canonical league code before the move (if a move)
        to_league        str? - canonical league code after the move (if a move)
        source           str  - 'fixture' | 'transfermarkt'

NOTE: fixture rows are hand-entered approximations for interface exercise only.
Phase 5's success definition deliberately does NOT depend on market values, so this
stub is not load-bearing for the proof-of-concept verdict.
"""

from __future__ import annotations

import pandas as pd

from src.common.config import PROJECT_ROOT

FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "transfermarkt_fixture.csv"


def get_player_valuations(refresh: bool = False) -> pd.DataFrame:
    """Serve valuations from the hand-entered fixture (see module docstring)."""
    df = pd.read_csv(FIXTURE_PATH)
    df["source"] = "fixture"
    return df
