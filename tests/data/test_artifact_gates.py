"""Artifact-dependent gate tests for Phases 1-4. Each test validates the REAL
pipeline outputs; tests skip (with a loud reason) until the phase has been run,
and `make phaseN` runs the phase then its gate marker."""

from pathlib import Path

import pandas as pd
import pytest

from src.common.config import (
    PROJECT_ROOT,
    asa_league_codes,
    data_path,
    load_settings,
    seasons,
    strength_priors,
)


def _require(path: Path, phase: str):
    if not path.exists():
        pytest.skip(f"{path.name} absent — run `python -m src {phase}` first")
    return path


# ---------------- Phase 1 ----------------

@pytest.mark.gate_phase1
def test_asa_frames_nonempty_and_contract_valid():
    from src.common.contracts import validate_frame
    from src.ingest.contracts_def import CONTRACTS
    interim = data_path("data_interim")
    _require(interim / "asa_player_xgoals.parquet", "phase1")
    for name, contract in [("asa_players", "asa_players"),
                           ("asa_player_xgoals", "asa_player_xgoals"),
                           ("asa_player_xpass", "asa_player_xpass"),
                           ("asa_player_goals_added", "asa_player_goals_added")]:
        df = pd.read_parquet(interim / f"{name}.parquet")
        assert len(df) > 0, f"{name} is empty"
        validate_frame(df, CONTRACTS[contract], name)


@pytest.mark.gate_phase1
def test_coverage_report_has_zero_silent_gaps():
    """Every league×season×metric cell is present and labeled ok or MISSING."""
    report = _require(data_path("data_outputs") / "coverage_report.md", "phase1")
    text = report.read_text(encoding="utf-8")
    for league in asa_league_codes():
        assert f"### {league}" in text, f"coverage report missing league {league}"
    n_seasons = len(seasons("asa"))
    n_leagues = len(asa_league_codes())
    n_cells = text.count("ok (n=") + text.count("MISSING")
    assert n_cells >= n_seasons * n_leagues * 5, "coverage table has unlabeled cells"


@pytest.mark.gate_phase1
def test_manifest_records_every_cached_pull():
    from src.common.io import _load_manifest
    manifest = _load_manifest()
    if not manifest:
        pytest.skip("manifest absent — run `python -m src phase1` first")
    for key, entry in manifest.items():
        assert {"source", "endpoint", "params", "pulled_at", "rows",
                "content_hash"} <= set(entry)
        assert (data_path("data_raw") / entry["file"]).exists()


# ---------------- Phase 2 ----------------

@pytest.mark.gate_phase2
def test_crosswalk_deterministic_hash():
    """Rebuilding the crosswalk from the same inputs yields an identical hash."""
    from src.common.io import frame_hash
    from src.harmonize.runner import build_crosswalk, build_player_seasons
    _require(data_path("data_crosswalk") / "player_crosswalk.parquet", "phase2")
    stored = (data_path("data_crosswalk") / "crosswalk.hash").read_text(encoding="utf-8")
    rebuilt, _ = build_crosswalk(build_player_seasons())
    assert frame_hash(rebuilt.astype(str)) == stored


@pytest.mark.gate_phase2
def test_crosswalk_reconciles_no_silent_drops():
    cw_path = _require(data_path("data_crosswalk") / "player_crosswalk.parquet", "phase2")
    cw = pd.read_parquet(cw_path)
    ps = pd.read_parquet(data_path("data_interim") / "player_seasons.parquet")
    for source in ps["source"].unique():
        n_source_players = ps[ps["source"] == source]["source_player_id"].nunique()
        assert (cw["source"] == source).sum() == n_source_players, \
            f"{source}: crosswalk rows != distinct players (silent drop?)"
    assert cw["person_id"].notna().all()


@pytest.mark.gate_phase2
def test_every_metric_has_data_dictionary_entry():
    from src.harmonize.metrics import METRIC_COLUMNS
    dd = _require(PROJECT_ROOT / "docs" / "data_dictionary.md", "phase2")
    text = dd.read_text(encoding="utf-8")
    for metric in METRIC_COLUMNS + ["minutes", "position"]:
        assert f"`{metric}`" in text, f"{metric} missing from data dictionary"


@pytest.mark.gate_phase2
def test_audit_sample_exists_with_buckets():
    path = _require(data_path("data_outputs") / "crosswalk_audit_sample.csv", "phase2")
    sample = pd.read_csv(path)
    assert "audit_bucket" in sample.columns
    ps = pd.read_parquet(data_path("data_interim") / "player_seasons.parquet")
    if (ps["source"] != "asa").any():
        # cross-source records exist, so there must be matches to audit
        assert len(sample) > 0


# ---------------- Phase 3 ----------------

@pytest.mark.gate_phase3
def test_every_mover_has_two_qualifying_seasons():
    path = _require(data_path("data_interim") / "movers.parquet", "phase3")
    moves = pd.read_parquet(path)
    threshold = float(load_settings()["movers"]["min_minutes_qualifying"])
    assert len(moves) > 0
    assert (moves["from_minutes"] >= threshold).all()
    assert (moves["to_minutes"] >= threshold).all()
    assert (moves["from_league"] != moves["to_league"]).all()
    assert (moves["to_season"] > moves["from_season"]).all()


@pytest.mark.gate_phase3
def test_movers_summary_reports_pairs_and_flags_thin():
    path = _require(data_path("data_outputs") / "movers_summary.md", "phase3")
    text = path.read_text(encoding="utf-8")
    assert "Moves per league pair" in text
    moves = pd.read_parquet(data_path("data_interim") / "movers.parquet")
    floor = int(load_settings()["movers"]["thin_pair_floor"])
    thin_exists = (moves.groupby(["from_league", "to_league"]).size() < floor).any()
    if thin_exists:
        assert "THIN" in text, "thin pairs exist but are not flagged in the summary"


# ---------------- Phase 4 ----------------

@pytest.mark.gate_phase4
def test_every_factor_carries_n_and_ci():
    path = _require(data_path("data_outputs") / "league_strength.parquet", "phase4")
    strengths = pd.read_parquet(path)
    assert {"strength", "ci_low", "ci_high", "n_moves_touching",
            "low_confidence"} <= set(strengths.columns)
    assert strengths["n_moves_touching"].notna().all()
    factors = pd.read_parquet(data_path("data_outputs") / "pairwise_factors.parquet")
    assert {"n", "factor", "low_confidence"} <= set(factors.columns)


@pytest.mark.gate_phase4
def test_no_confident_prior_violation_in_diagnostics():
    path = _require(data_path("data_outputs") / "calibration_diagnostics.md", "phase4")
    text = path.read_text(encoding="utf-8")
    assert "Prior checks" in text
    assert "VIOLATION-confident" not in text, \
        "confident prior violation surfaced — see review queue (blocker)"
    assert len(strength_priors()) > 0
