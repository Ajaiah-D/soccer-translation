"""Phase 0 acceptance gate: config loads, CLI runs and exits 0, seed is fixed."""

import subprocess
import sys

import pytest

from src.common.config import (
    PROJECT_ROOT,
    asa_league_codes,
    fbref_league_codes,
    load_settings,
    random_seed,
    seasons,
    strength_priors,
)


@pytest.mark.gate_phase0
def test_hello_config_loads():
    settings = load_settings()
    assert settings["hello"] == "cross-league-translation is alive"


@pytest.mark.gate_phase0
def test_seed_is_42():
    assert random_seed() == 42


@pytest.mark.gate_phase0
def test_cli_noop_exits_zero():
    result = subprocess.run(
        [sys.executable, "-m", "src"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.gate_phase0
def test_league_registry_shape():
    asa = asa_league_codes()
    assert "MLS" in asa and asa["MLS"] == "mls"
    fbref = fbref_league_codes()
    assert "MLS" in fbref
    assert all(len(p) == 2 for p in strength_priors())


@pytest.mark.gate_phase0
def test_seasons_expand():
    s = seasons("asa")
    assert s[0] >= 2013 and s[-1] >= s[0] and s == sorted(s)
