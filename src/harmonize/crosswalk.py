"""Cross-source player identity resolution (Phase 2).

Strategy:
- ASA `player_id` is the identity backbone for the American pyramid.
- FBref/Transfermarkt records are matched to ASA identities by blocked fuzzy matching:
  candidates must overlap on season coverage (block), then are scored with
  rapidfuzz token_sort_ratio on accent-stripped, suffix-normalized names, with
  birth-year agreement as a tie-break bonus.
- Scores >= accept_threshold auto-match; scores in [reject, accept) land in the
  low-confidence audit bucket (never auto-accepted); below reject never match.
- Players with no cross-source presence keep a source-scoped id, so nothing is dropped.

Determinism: inputs are sorted, ties broken lexicographically; identical inputs yield a
hash-identical crosswalk (asserted by the Phase 2 gate).
"""

from __future__ import annotations

import unicodedata

import pandas as pd
from rapidfuzz import fuzz

from src.common.config import load_settings
from src.common.logging import get_logger

log = get_logger("harmonize.crosswalk")

_NAME_SUFFIXES = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv"}

# letters NFKD cannot decompose; transliterate before accent stripping
_TRANSLITERATE = str.maketrans({"đ": "dj", "Đ": "Dj", "ø": "o", "Ø": "O",
                                "ß": "ss", "æ": "ae", "Æ": "Ae", "ł": "l", "Ł": "L"})


def normalize_name(name: str) -> str:
    """Lowercase, strip accents/punctuation/suffixes: 'Carles Gil' == 'carles gil',
    'Luiz Fernando Jr.' -> 'luiz fernando', 'Đorđe' -> 'djordje'."""
    if not isinstance(name, str):
        return ""
    text = unicodedata.normalize("NFKD", name.translate(_TRANSLITERATE))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().replace("-", " ").replace("'", "").replace(".", ". ").strip()
    tokens = [t.strip(".,") for t in text.split()]
    tokens = [t for t in tokens if t and t not in _NAME_SUFFIXES]
    return " ".join(tokens)


def score_match(name_a: str, name_b: str,
                birth_year_a: float | None = None,
                birth_year_b: float | None = None) -> float:
    """0-100 match confidence: fuzzy name score, +/- birth-year adjustment.
    Birth-year agreement adds up to +4 (capped at 100); a hard disagreement of
    >=2 years subtracts 25 (near-certain different person)."""
    base = fuzz.token_sort_ratio(normalize_name(name_a), normalize_name(name_b))
    years_known = (birth_year_a is not None and birth_year_b is not None
                   and not pd.isna(birth_year_a) and not pd.isna(birth_year_b))
    if years_known and birth_year_a and birth_year_b:
        gap = abs(int(birth_year_a) - int(birth_year_b))
        if gap == 0:
            base = min(100.0, base + 4)
        elif gap >= 2:
            base -= 25
    return float(base)


def match_records(
    left: pd.DataFrame,
    right: pd.DataFrame,
    left_id: str,
    right_id: str,
) -> pd.DataFrame:
    """Match each `right` record to at most one `left` record.

    Both frames need: <id>, `player_name`, optional `birth_year`, and `seasons`
    (a frozenset/set of ints used as the block: candidates must share a season).
    An optional `groups` column (set of league-system groups, e.g. {'mens'} or
    {'womens'}) adds a hard block: records from disjoint league systems never match
    (a women's-league player must not bind to a men's-league record, however
    similar the names).
    Returns one row per right record: right_id, matched left_id (or None),
    match_confidence, match_status in {'accepted', 'low_confidence', 'unmatched'}.
    """
    cfg = load_settings()["crosswalk"]
    accept, reject = float(cfg["accept_threshold"]), float(cfg["reject_threshold"])

    left_sorted = left.sort_values(left_id).reset_index(drop=True)
    left_records = left_sorted.to_dict(orient="records")

    # Blocking: inverted index of name tokens (>=3 chars) -> left row positions.
    # A candidate must share at least one name token AND one season with the query.
    token_index: dict[str, list[int]] = {}
    for pos, rec in enumerate(left_records):
        rec["_norm_name"] = normalize_name(rec["player_name"])
        for token in rec["_norm_name"].split():
            if len(token) >= 3:
                token_index.setdefault(token, []).append(pos)

    rows = []
    for _, r in right.sort_values(right_id).iterrows():
        norm_r = normalize_name(r["player_name"])
        candidate_positions = sorted({
            pos for token in norm_r.split() if len(token) >= 3
            for pos in token_index.get(token, [])
        })
        best_score, best_id = -1.0, None
        r_seasons = set(r["seasons"]) if r["seasons"] else set()
        r_groups = set(r["groups"]) if "groups" in r and r["groups"] else set()
        for pos in candidate_positions:
            l = left_records[pos]
            l_seasons = set(l["seasons"]) if l["seasons"] else set()
            if r_seasons and l_seasons and not (r_seasons & l_seasons):
                continue  # season block: never active in overlapping seasons
            l_groups = set(l["groups"]) if "groups" in l and l["groups"] else set()
            if r_groups and l_groups and not (r_groups & l_groups):
                continue  # league-system block: disjoint mens/womens systems
            s = score_match(l["player_name"], r["player_name"],
                            l.get("birth_year"), r.get("birth_year"))
            if s > best_score or (s == best_score and best_id is not None
                                  and str(l[left_id]) < str(best_id)):
                best_score, best_id = s, l[left_id]
        if best_score >= accept:
            status = "accepted"
        elif best_score >= reject:
            status = "low_confidence"  # kept for audit, not used downstream
        else:
            status, best_id = "unmatched", None
        rows.append({right_id: r[right_id],
                     "matched_" + left_id: best_id if status == "accepted" else None,
                     "candidate_" + left_id: best_id,
                     "match_confidence": max(best_score, 0.0),
                     "match_status": status, "player_name": r["player_name"]})
    return pd.DataFrame(rows)
