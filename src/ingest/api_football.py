"""API-Football ingest: per-player season stats (minutes, position, shots, key passes,
tackles, interceptions, duels, dribbles, ...) for the scouting-catalog leagues.

The free plan allows 100 requests/day, only seasons 2022-2024, and never a page
beyond 3 (20 players each). A league-wide /players listing runs ~50 pages, so the
catalog is pulled per team instead: /teams for each league-season, then
/players?league&season&team page by page (a squad fits in 3 pages; any team that
does not is flagged as truncated, never silently cut). It is a slow, resumable
backfill: every response is its own cached_pull, a run spends at most the day's
remaining quota (read from /status), and the next run skips everything cached. API
errors (plan, quota, auth) raise and are never cached, so a blocked request is
simply retried on a later day.

Season convention matches ours: season 2023 = the 2023/24 European season, or
calendar 2023 for MLS / Brazil / Argentina.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import pandas as pd
import requests

from src.common.config import data_path, league_registry, load_settings, read_env_var, seasons
from src.common.io import cached_frame, cached_pull
from src.common.logging import get_logger

log = get_logger("ingest.api_football")

SOURCE = "api_football"

# statistics groups that describe context, not performance (flattened separately)
CONTEXT_GROUPS = {"team", "league"}

# (api path, query params) -> decoded JSON payload
Fetch = Callable[[str, dict[str, Any]], dict[str, Any]]


class ApiFootballError(RuntimeError):
    """The API answered with an error (plan, quota, auth) or was unreachable."""


@dataclass(frozen=True)
class Target:
    league: str      # canonical code
    league_id: int   # API-Football league id
    season: int


@dataclass
class BackfillResult:
    fetched: int
    complete: bool
    stopped_reason: str | None = None


def api_football_targets() -> list[Target]:
    """Every configured league with an API-Football id x every free-plan season."""
    return [Target(code, int(spec["api_football"]), season)
            for code, spec in league_registry().items() if spec.get("api_football")
            for season in seasons("api_football")]


def flatten_players(response: list[dict[str, Any]]) -> pd.DataFrame:
    """One row per player x team stint; nested stat groups become group_field
    columns (tackles_total, passes_key, ...). Missing stays missing, never 0."""
    rows = []
    for item in response:
        player = item.get("player") or {}
        for stat in item.get("statistics") or []:
            row = {
                "player_id": player.get("id"),
                "player_name": player.get("name"),
                "firstname": player.get("firstname"),
                "lastname": player.get("lastname"),
                "birth_date": (player.get("birth") or {}).get("date"),
                "nationality": player.get("nationality"),
                "team_id": (stat.get("team") or {}).get("id"),
                "team_name": (stat.get("team") or {}).get("name"),
                "league_id": (stat.get("league") or {}).get("id"),
            }
            for group, fields in stat.items():
                if group in CONTEXT_GROUPS or not isinstance(fields, dict):
                    continue
                for field, value in fields.items():
                    row[f"{group}_{field}"] = value
            rows.append(row)
    df = pd.DataFrame(rows)
    for col in df.columns:
        if col.startswith(("player_", "firstname", "lastname", "birth_", "nationality",
                           "team_name", "games_position")):
            continue
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _raise_on_errors(payload: dict[str, Any]) -> None:
    errors = payload.get("errors")
    if errors:
        raise ApiFootballError("; ".join(f"{k}: {v}" for k, v in errors.items())
                               if isinstance(errors, dict) else str(errors))


def parse_page(payload: dict[str, Any]) -> tuple[pd.DataFrame, int]:
    """Rows and total page count from one /players response; raises on API errors."""
    _raise_on_errors(payload)
    total = int((payload.get("paging") or {}).get("total") or 1)
    return flatten_players(payload.get("response") or []), total


def parse_teams(payload: dict[str, Any]) -> pd.DataFrame:
    """Team ids and names from one /teams response; raises on API errors."""
    _raise_on_errors(payload)
    return pd.DataFrame([{"team_id": (item.get("team") or {}).get("id"),
                          "team_name": (item.get("team") or {}).get("name")}
                         for item in payload.get("response") or []],
                        columns=["team_id", "team_name"])


def daily_budget(requests_block: dict[str, Any], reserve: int) -> int:
    """Requests this run may spend: today's remaining quota minus a reserve."""
    return max(0, int(requests_block["limit_day"]) - int(requests_block["current"]) - reserve)


def _teams_params(target: Target) -> dict[str, int]:
    return {"league": target.league_id, "season": target.season}


def _players_params(target: Target, team_id: int, page: int) -> dict[str, int]:
    return {"league": target.league_id, "season": target.season,
            "team": int(team_id), "page": page}


def _page_total(df: pd.DataFrame, page: int) -> int:
    """Total pages recorded on a cached page (an empty page ends its team)."""
    return int(df["paging_total"].iloc[0]) if len(df) else page


class _BudgetSpent(Exception):
    pass


def backfill(fetch: Fetch, targets: list[Target], budget: int,
             max_page: int) -> BackfillResult:
    """Walk targets team by team and page by page, fetching only uncached responses,
    until the catalog is complete, the budget is spent, or the API refuses."""
    fetched = 0

    def get(endpoint: str, params: dict[str, int],
            parse: Callable[[dict[str, Any]], pd.DataFrame]) -> pd.DataFrame:
        nonlocal fetched
        df = cached_frame(SOURCE, endpoint, params)
        if df is not None:
            return df
        if fetched >= budget:
            raise _BudgetSpent
        df = cached_pull(SOURCE, endpoint, params, lambda: parse(fetch(endpoint, params)))
        fetched += 1
        return df

    def players(payload: dict[str, Any]) -> pd.DataFrame:
        rows, n_pages = parse_page(payload)
        return rows.assign(paging_total=n_pages)

    try:
        for target in targets:
            teams = get("teams", _teams_params(target), parse_teams)
            for team_id in teams["team_id"]:
                page, last = 1, None
                while last is None or page <= last:
                    df = get("players", _players_params(target, team_id, page), players)
                    if last is None:
                        last = min(_page_total(df, page), max_page)
                    page += 1
    except _BudgetSpent:
        return BackfillResult(fetched, False, "daily budget spent")
    except ApiFootballError as exc:
        log.warning("api_football stopped after %d requests: %s", fetched, exc)
        return BackfillResult(fetched, False, str(exc))
    return BackfillResult(fetched, True)


def catalog_status(targets: list[Target], max_page: int) -> pd.DataFrame:
    """Per league-season: teams known, teams fully cached, and teams whose squad runs
    past the plan's page cap (truncated). Reads the cache only, never the network."""
    rows = []
    for target in targets:
        teams = cached_frame(SOURCE, "teams", _teams_params(target))
        done = truncated = 0
        for team_id in ([] if teams is None else teams["team_id"]):
            first = cached_frame(SOURCE, "players", _players_params(target, team_id, 1))
            if first is None:
                continue
            total = _page_total(first, 1)
            last = min(total, max_page)
            if all(cached_frame(SOURCE, "players", _players_params(target, team_id, p))
                   is not None for p in range(2, last + 1)):
                done += 1
                truncated += total > max_page
        rows.append({"league": target.league, "league_id": target.league_id,
                     "season": target.season,
                     "teams_total": None if teams is None else len(teams),
                     "teams_done": done, "teams_truncated": truncated})
    out = pd.DataFrame(rows)
    out["teams_total"] = out["teams_total"].astype("Int64")
    return out


def _get(key: str, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = load_settings()["api_football"]
    try:
        resp = requests.get(f"{cfg['base_url']}/{path}", params=params,
                            headers={"x-apisports-key": key},
                            timeout=float(cfg["timeout_seconds"]))
        resp.raise_for_status()
        return resp.json()
    except (requests.RequestException, ValueError) as exc:
        raise ApiFootballError(f"{path} request failed: {exc}") from exc


def live_fetcher(key: str) -> Fetch:
    """Network fetcher, spaced to stay under the per-minute cap."""
    delay = float(load_settings()["api_football"]["request_delay_seconds"])

    def fetch(path: str, params: dict[str, Any]) -> dict[str, Any]:
        time.sleep(delay)
        return _get(key, path, params)

    return fetch


def write_catalog_report(status: pd.DataFrame, result: BackfillResult | None) -> Path:
    complete = status["teams_total"].notna() & (status["teams_done"] == status["teams_total"])
    lines = [
        "# API-Football catalog progress",
        "",
        f"- league-seasons complete: {int(complete.sum())} of {len(status)}",
        f"- teams cached: {int(status['teams_done'].sum())}"
        f" of {int(status['teams_total'].sum())} known"
        f" ({int(status['teams_total'].isna().sum())} league-seasons not started)",
        f"- teams with squads past the page cap: {int(status['teams_truncated'].sum())}"
        " (players beyond page cap missing for these teams)",
    ]
    if result is not None:
        lines.append(f"- last run: {result.fetched} requests; "
                     + ("catalog complete" if result.complete
                        else f"stopped: {result.stopped_reason}"))
    lines += ["", "| league | season | teams done | teams total | truncated |",
              "|---|---|---|---|---|"]
    for r in status.itertuples():
        total = "?" if pd.isna(r.teams_total) else int(r.teams_total)
        lines.append(f"| {r.league} | {r.season} | {r.teams_done} | {total} | "
                     f"{r.teams_truncated} |")
    out = data_path("data_outputs") / "api_football_catalog.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def run_backfill() -> BackfillResult:
    """CLI entry: spend today's remaining quota on uncached responses, then report."""
    cfg = load_settings()["api_football"]
    key = read_env_var(cfg["key_env_var"])
    if not key:
        raise SystemExit(f"{cfg['key_env_var']} is not set (add it to .env)")
    status_payload = _get(key, "status")
    if status_payload.get("errors"):
        raise SystemExit(f"api_football status check failed: {status_payload['errors']}")
    budget = daily_budget(status_payload["response"]["requests"], int(cfg["daily_reserve"]))
    log.info("api_football: %d requests available this run", budget)
    targets, max_page = api_football_targets(), int(cfg["max_page"])
    result = backfill(live_fetcher(key), targets, budget, max_page)
    report = write_catalog_report(catalog_status(targets, max_page), result)
    log.info("api_football: %d requests, %s; progress at %s", result.fetched,
             "catalog complete" if result.complete else f"stopped ({result.stopped_reason})",
             report)
    return result
