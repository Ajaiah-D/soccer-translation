"""Central logging setup: console + a per-run lineage log for dropped-row accounting."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

from src.common.config import data_path

_CONFIGURED = False


def get_logger(name: str) -> logging.Logger:
    global _CONFIGURED
    if not _CONFIGURED:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
        )
        root = logging.getLogger("clt")
        root.setLevel(logging.INFO)
        root.addHandler(handler)
        _CONFIGURED = True
    return logging.getLogger(f"clt.{name}")


def log_lineage(step: str, action: str, count: int, reason: str) -> None:
    """Append a dropped/kept-row accounting record. Never drop rows without calling this."""
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "step": step,
        "action": action,
        "count": int(count),
        "reason": reason,
    }
    lineage_file = data_path("data_outputs") / "data_lineage.jsonl"
    with open(lineage_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    get_logger("lineage").info("%s | %s %d rows: %s", step, action, count, reason)
