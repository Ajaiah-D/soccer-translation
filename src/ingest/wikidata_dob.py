"""Birth-year enrichment from Wikidata for players whose source has no birth dates
(Understat). Fully automatic: batched SPARQL label queries against the open Wikidata
endpoint, cached like every other pull.

Precision rules (a wrong birth year is worse than a missing one):
- an item must be a human whose occupation is association football player;
- the label must match the player's name exactly (English label or alias);
- if several distinct footballers share the name with DIFFERENT birth years, the
  name is skipped and counted as ambiguous - never guessed.

Only players who can actually matter are queried: those lacking a birth year with
qualifying seasons in at least two covered leagues (potential movers).
"""

from __future__ import annotations

import time

import pandas as pd
import requests

from src.common.config import load_settings
from src.common.io import cached_pull
from src.common.logging import get_logger

log = get_logger("ingest.wikidata")

ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = ("soccer-translation-research/1.0 "
              "(cross-league player value translation; contact: repo owner)")
BATCH_SIZE = 40

# exact language-tagged label literals in VALUES hit the label index directly,
# which keeps the query fast enough for the public endpoint
QUERY_TEMPLATE = """
SELECT ?label ?item ?dob WHERE {{
  VALUES ?label {{ {labels} }}
  ?item rdfs:label ?label .
  ?item wdt:P31 wd:Q5 .
  ?item wdt:P106 wd:Q937857 .
  ?item wdt:P569 ?dob .
}}
"""


def _run_query(names: list[str]) -> pd.DataFrame:
    labels = " ".join('"' + n.replace('"', "") + '"@en' for n in names)
    query = QUERY_TEMPLATE.format(labels=labels)
    cfg = load_settings()["ingest"]
    last_exc: Exception | None = None
    for attempt in range(int(cfg["max_retries"])):
        try:
            resp = requests.get(ENDPOINT, params={"query": query, "format": "json"},
                                headers={"User-Agent": USER_AGENT}, timeout=120)
            resp.raise_for_status()
            rows = [{"player_name": b["label"]["value"],
                     "item": b["item"]["value"],
                     "birth_year": int(b["dob"]["value"][:4])}
                    for b in resp.json()["results"]["bindings"]]
            return pd.DataFrame(rows, columns=["player_name", "item", "birth_year"])
        except Exception as exc:  # noqa: BLE001 - retried with backoff
            last_exc = exc
            backoff = float(cfg["backoff_base_seconds"]) * (2 ** attempt)
            log.warning("wikidata query failed (attempt %d): %s - backing off %.1fs",
                        attempt + 1, str(exc)[:100], backoff)
            time.sleep(backoff)
    raise RuntimeError("wikidata query failed after retries") from last_exc


def _resolve_batch(names: list[str]) -> pd.DataFrame:
    """One cached batch: name -> birth_year, or NaN when unmatched/ambiguous."""
    raw = _run_query(names)
    out = []
    for name in names:
        hits = raw[raw["player_name"] == name]
        years = sorted(set(hits["birth_year"]))
        plausible = [y for y in years if 1960 <= y <= 2012]
        if len(plausible) == 1:
            out.append({"player_name": name, "birth_year": float(plausible[0]),
                        "status": "matched"})
        elif len(plausible) > 1:
            out.append({"player_name": name, "birth_year": None,
                        "status": "ambiguous"})
        else:
            out.append({"player_name": name, "birth_year": None,
                        "status": "unmatched"})
    return pd.DataFrame(out)


def lookup_birth_years(names: list[str], refresh: bool = False) -> pd.DataFrame:
    """Batched, cached lookups. Returns player_name, birth_year (NaN if unknown),
    status in {matched, ambiguous, unmatched}."""
    rate = float(load_settings()["ingest"]["rate_limit_seconds"])
    unique = sorted(set(n for n in names if isinstance(n, str) and n.strip()))
    frames = []
    for i in range(0, len(unique), BATCH_SIZE):
        batch = unique[i:i + BATCH_SIZE]

        def fetch(batch=batch) -> pd.DataFrame:
            time.sleep(rate)
            return _resolve_batch(batch)

        # cache key: the sorted batch itself (stable for a stable player universe)
        frames.append(cached_pull("wikidata", "dob_batch",
                                  {"names": batch}, fetch, refresh=refresh))
    if not frames:
        return pd.DataFrame(columns=["player_name", "birth_year", "status"])
    result = pd.concat(frames, ignore_index=True)
    counts = result["status"].value_counts().to_dict()
    log.info("wikidata birth years: %s", counts)
    return result
