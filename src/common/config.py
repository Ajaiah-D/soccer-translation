"""Configuration loading. All tunables live in config/*.yaml — nothing is hardcoded in logic."""

from __future__ import annotations

import functools
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"


@functools.lru_cache(maxsize=None)
def load_settings() -> dict[str, Any]:
    with open(CONFIG_DIR / "settings.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


@functools.lru_cache(maxsize=None)
def load_leagues() -> dict[str, Any]:
    with open(CONFIG_DIR / "leagues.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def random_seed() -> int:
    return int(load_settings()["random_seed"])


def seasons(source: str) -> list[int]:
    """Inclusive season range for a source ('asa' or 'fbref')."""
    block = load_settings()["seasons"][source]
    return list(range(int(block["start"]), int(block["end"]) + 1))


def data_path(key: str) -> Path:
    """Resolve a configured data directory (created on demand)."""
    p = PROJECT_ROOT / load_settings()["paths"][key]
    p.mkdir(parents=True, exist_ok=True)
    return p


def league_registry() -> dict[str, dict[str, Any]]:
    return load_leagues()["leagues"]


def asa_league_codes() -> dict[str, str]:
    """Canonical code -> ASA code, for leagues ASA covers."""
    return {
        code: spec["asa"]
        for code, spec in league_registry().items()
        if spec.get("asa")
    }


def fbref_league_codes() -> dict[str, str]:
    """Canonical code -> FBref (soccerdata) league id, for leagues FBref covers."""
    return {
        code: spec["fbref"]
        for code, spec in league_registry().items()
        if spec.get("fbref")
    }


def strength_priors() -> list[tuple[str, str]]:
    """Pairs (stronger, weaker) used by the Phase 4 monotonicity gate."""
    return [tuple(pair) for pair in load_leagues()["strength_priors"]]
