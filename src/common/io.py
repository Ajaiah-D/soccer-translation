"""Cache-with-manifest IO. Every raw pull is cached to data/raw with a manifest entry
(source, endpoint, params, timestamp, row count, content hash). Re-runs read cache
unless refresh=True."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from src.common.config import data_path
from src.common.logging import get_logger

log = get_logger("io")

MANIFEST_NAME = "manifest.json"


def _manifest_path() -> Path:
    return data_path("data_raw") / MANIFEST_NAME


def _load_manifest() -> dict[str, Any]:
    p = _manifest_path()
    if p.exists():
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_manifest(manifest: dict[str, Any]) -> None:
    with open(_manifest_path(), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)


def cache_key(source: str, endpoint: str, params: dict[str, Any]) -> str:
    """Deterministic cache key for a pull."""
    blob = json.dumps({"source": source, "endpoint": endpoint, "params": params}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def frame_hash(df: pd.DataFrame) -> str:
    """Content hash of a frame, stable across runs for identical data."""
    return hashlib.sha256(
        pd.util.hash_pandas_object(df.reset_index(drop=True), index=False).values.tobytes()
    ).hexdigest()[:16]


def _parquet_safe(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce non-scalar object values (lists/dicts, e.g. ASA multi-team team_id) to
    joined strings so frames serialize to parquet losslessly enough for our keys."""
    df = df.copy()
    for col in df.columns:
        if df[col].dtype == object:
            has_nonscalar = df[col].map(lambda v: isinstance(v, (list, tuple, dict))).any()
            if has_nonscalar:
                df[col] = df[col].map(
                    lambda v: ",".join(map(str, v)) if isinstance(v, (list, tuple))
                    else (json.dumps(v) if isinstance(v, dict) else v))
    return df


def _cache_file(source: str, endpoint: str, params: dict[str, Any]) -> tuple[str, str, Path]:
    key = cache_key(source, endpoint, params)
    fname = f"{source}__{endpoint}__{key}.parquet"
    return key, fname, data_path("data_raw") / fname


def cached_frame(source: str, endpoint: str, params: dict[str, Any]) -> pd.DataFrame | None:
    """The cached frame for a pull, or None if it was never pulled. Never fetches."""
    _, _, fpath = _cache_file(source, endpoint, params)
    return pd.read_parquet(fpath) if fpath.exists() else None


def cached_pull(
    source: str,
    endpoint: str,
    params: dict[str, Any],
    fetch: Callable[[], pd.DataFrame],
    refresh: bool = False,
) -> pd.DataFrame:
    """Return cached frame if present (and not refresh), else fetch, cache, and manifest it.

    An empty fetch result is cached too (as a legitimate 'no data for this slice' answer),
    so re-runs stay offline.
    """
    key, fname, fpath = _cache_file(source, endpoint, params)

    if fpath.exists() and not refresh:
        return pd.read_parquet(fpath)

    df = fetch()
    if df is None:
        df = pd.DataFrame()
    df = _parquet_safe(df)
    df.to_parquet(fpath, index=False)

    manifest = _load_manifest()
    manifest[key] = {
        "source": source,
        "endpoint": endpoint,
        "params": params,
        "file": fname,
        "pulled_at": datetime.now(timezone.utc).isoformat(),
        "rows": int(len(df)),
        "content_hash": frame_hash(df) if len(df) else "empty",
    }
    _save_manifest(manifest)
    log.info("pulled %s/%s %s -> %d rows", source, endpoint, params, len(df))
    return df


def write_output(df: pd.DataFrame, key: str, name: str) -> Path:
    """Write a deterministic parquet artifact to a configured data dir."""
    p = data_path(key) / name
    df.to_parquet(p, index=False)
    return p
