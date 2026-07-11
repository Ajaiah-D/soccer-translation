"""Pydantic data contracts for every ingested source (pending a real feed).

Each contract models one ROW of the frame. validate_frame() (src.common.contracts)
checks column presence for all fields and type-validates a row sample on load.
Markdown descriptions are generated into docs/contracts/ by write_contract_docs().
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Type

from pydantic import BaseModel

from src.common.config import data_path  # noqa: F401 (kept for parity with io usage)
from src.common.config import PROJECT_ROOT


class AsaPlayersRow(BaseModel):
    """Identity table: one row per player per league (asa get_players)."""
    player_id: str
    player_name: str
    birth_date: Optional[str] = None
    nationality: Optional[str] = None
    primary_broad_position: Optional[str] = None
    primary_general_position: Optional[str] = None
    league: str


class AsaPlayerXgoalsRow(BaseModel):
    """Player xG per league-season (asa get_player_xgoals, split_by_seasons)."""
    player_id: str
    team_id: str
    season_name: str
    general_position: Optional[str] = None
    minutes_played: int
    shots: int
    goals: int
    xgoals: float
    key_passes: int
    primary_assists: int
    xassists: float
    league: str
    season: int


class AsaPlayerXpassRow(BaseModel):
    """Player pass model per league-season (asa get_player_xpass, split_by_seasons)."""
    player_id: str
    team_id: str
    season_name: str
    general_position: Optional[str] = None
    minutes_played: int
    attempted_passes: int
    pass_completion_percentage: float
    xpass_completion_percentage: float
    passes_completed_over_expected: float
    share_team_touches: float
    league: str
    season: int


class AsaPlayerGoalsAddedRow(BaseModel):
    """Player g+ per league-season, flattened from the nested action-type payload.
    g+ is an action-value framework, NOT xG - see docs/metric_glossary.md."""
    player_id: str
    team_id: str
    season_name: str
    general_position: Optional[str] = None
    minutes_played: int
    goals_added_raw_total: Optional[float] = None
    goals_added_above_avg_total: Optional[float] = None
    league: str
    season: int


class FbrefPlayerSeasonRow(BaseModel):
    """FBref standard player season stats (soccerdata, flattened columns)."""
    player: str
    nation: Optional[str] = None
    pos: Optional[str] = None
    playing_time_min: Optional[float] = None
    performance_gls: Optional[float] = None
    performance_ast: Optional[float] = None
    league: str
    season: int


class UnderstatPlayerRow(BaseModel):
    """Understat player-season xG data (POST /main/getPlayersStats/)."""
    id: str
    player_name: str
    time: float  # minutes played
    goals: float
    xG: float
    assists: float
    xA: float
    position: Optional[str] = None
    league: str
    season: int


class TransfermarktRow(BaseModel):
    """Market value / transfer labels (stub fixture or real feed)."""
    player_name: str
    as_of_season: int
    market_value_eur: Optional[float] = None
    transfer_fee_eur: Optional[float] = None
    source: str


CONTRACTS: dict[str, Type[BaseModel]] = {
    "asa_players": AsaPlayersRow,
    "asa_player_xgoals": AsaPlayerXgoalsRow,
    "asa_player_xpass": AsaPlayerXpassRow,
    "asa_player_goals_added": AsaPlayerGoalsAddedRow,
    "fbref_player_season": FbrefPlayerSeasonRow,
    "understat_league_players": UnderstatPlayerRow,
    "transfermarkt": TransfermarktRow,
}


def write_contract_docs() -> Path:
    """Generate one markdown file per contract into docs/contracts/."""
    out_dir = PROJECT_ROOT / "docs" / "contracts"
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, model in CONTRACTS.items():
        lines = [f"# Contract: `{name}`", "", model.__doc__ or "", "",
                 "| column | type | required |", "|---|---|---|"]
        for field, info in model.model_fields.items():
            required = "yes" if info.is_required() else "no (nullable)"
            lines.append(f"| `{field}` | `{info.annotation}` | {required} |")
        lines += ["", "_Generated from `src/ingest/contracts_def.py`; edit the model, not this file._"]
        (out_dir / f"{name}.md").write_text("\n".join(lines), encoding="utf-8")
    return out_dir
