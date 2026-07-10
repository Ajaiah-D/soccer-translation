"""Phase 1 gate: re-running without --refresh hits cache with ZERO network calls."""

import socket

import pandas as pd
import pytest

from src.common.io import cached_pull


@pytest.mark.gate_phase1
def test_cached_pull_never_refetches(tmp_path, monkeypatch):
    """Second cached_pull for the same key must not invoke fetch at all."""
    monkeypatch.setattr("src.common.io.data_path", lambda key: tmp_path)

    calls = {"n": 0}

    def fetch():
        calls["n"] += 1
        return pd.DataFrame({"a": [1, 2]})

    first = cached_pull("testsrc", "ep", {"x": 1}, fetch)
    assert calls["n"] == 1 and len(first) == 2

    def fetch_forbidden():
        raise AssertionError("network fetch invoked on a cache hit")

    second = cached_pull("testsrc", "ep", {"x": 1}, fetch_forbidden)
    assert len(second) == 2  # served from cache, fetch never called


@pytest.mark.gate_phase1
def test_empty_results_are_cached_too(tmp_path, monkeypatch):
    """A legitimate zero-row answer is cached so re-runs stay offline (D-005)."""
    monkeypatch.setattr("src.common.io.data_path", lambda key: tmp_path)
    cached_pull("testsrc", "ep_empty", {}, lambda: pd.DataFrame())
    out = cached_pull("testsrc", "ep_empty", {},
                      lambda: (_ for _ in ()).throw(AssertionError("refetched empty")))
    assert out.empty


@pytest.mark.gate_phase1
def test_real_cache_serves_with_sockets_blocked(monkeypatch):
    """With the real data/raw cache populated (post-phase1), a re-pull of one real
    slice succeeds even when all socket creation is blocked."""
    from src.common.io import _load_manifest

    manifest = _load_manifest()
    asa_entries = [v for v in manifest.values() if v["source"] == "asa" and v["rows"] > 0]
    if not asa_entries:
        pytest.skip("data/raw cache not populated yet (run `python -m src phase1`)")

    entry = asa_entries[0]

    def no_network(*args, **kwargs):
        raise AssertionError("socket opened during a cached re-pull")

    monkeypatch.setattr(socket, "socket", no_network)
    monkeypatch.setattr(socket, "create_connection", no_network)

    from src.ingest.asa import _pull_player_season
    df = _pull_player_season(entry["endpoint"],
                             entry["params"]["league"],
                             entry["params"]["season"])
    assert len(df) == entry["rows"]
