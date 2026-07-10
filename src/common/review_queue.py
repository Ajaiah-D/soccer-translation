"""Append-only, idempotent writer for REVIEW_QUEUE.md (items a reviewer should check before trusting results)."""

from __future__ import annotations

from datetime import datetime, timezone

from src.common.config import PROJECT_ROOT

QUEUE = PROJECT_ROOT / "REVIEW_QUEUE.md"

SEVERITIES = {"info", "should-review", "must-review-before-trusting-results"}


def add_review_item(title: str, severity: str, context: str, artifact: str) -> None:
    """Append an item unless an item with the same title already exists."""
    assert severity in SEVERITIES, f"bad severity {severity}"
    existing = QUEUE.read_text(encoding="utf-8") if QUEUE.exists() else ""
    marker = f"## {title}"
    if marker in existing:
        return
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    entry = (f"\n{marker}\n\n- **Severity:** `{severity}`\n- **Added:** {stamp}\n"
             f"- **Artifact:** {artifact}\n\n{context}\n")
    with open(QUEUE, "a", encoding="utf-8") as f:
        f.write(entry)
