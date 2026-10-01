"""Cross-platform phase runner: `python -m src <phase0|phase1|...|all|report|apif|apif-status>`.

Equivalent to the Makefile targets; both call these entry points.
Running with no argument performs a no-op environment check and exits 0 (Phase 0 gate).
"""

from __future__ import annotations

import argparse
import sys

from src.common.config import PROJECT_ROOT, load_settings
from src.common.logging import get_logger

log = get_logger("main")

PHASES = ["phase0", "phase1", "phase2", "phase3", "phase4", "phase5"]


def run_gate(name: str) -> None:
    """Run the phase's acceptance-gate pytest marker; raise on failure."""
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-m", f"gate_{name}", "-q"],
        cwd=str(PROJECT_ROOT),
    )
    if result.returncode != 0:
        raise SystemExit(f"acceptance gate for {name} FAILED (see pytest output)")
    log.info("acceptance gate for %s passed", name)


def run_phase(name: str, refresh: bool = False) -> None:
    if name == "phase0":
        settings = load_settings()
        log.info("phase0 OK: config loaded, hello=%r", settings["hello"])
        return
    if name == "phase1":
        from src.ingest.runner import run_phase1
        run_phase1(refresh=refresh)
        return
    if name == "phase2":
        from src.harmonize.runner import run_phase2
        run_phase2()
        return
    if name == "phase3":
        from src.calibration.movers import run_phase3
        run_phase3()
        return
    if name == "phase4":
        from src.calibration.league_strength import run_phase4
        run_phase4()
        return
    if name == "phase5":
        from src.validate.retrodict import run_phase5
        run_phase5()
        return
    raise SystemExit(f"unknown phase: {name}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m src")
    parser.add_argument("target", nargs="?", default=None,
                        choices=PHASES + ["all", "report", "apif", "apif-status"],
                        help="phase to run; omit for a no-op environment check")
    parser.add_argument("--refresh", action="store_true",
                        help="bypass cache and re-pull raw data (phase1 only)")
    args = parser.parse_args(argv)

    if args.target is None:
        load_settings()  # proves config loads
        log.info("environment check OK")
        return 0

    if args.target == "all":
        for phase in PHASES:
            log.info("=== running %s ===", phase)
            run_phase(phase, refresh=args.refresh)
            run_gate(phase)
        from src.report import write_run_report
        write_run_report()
        return 0

    if args.target == "report":
        from src.report import write_run_report
        write_run_report()
        return 0

    if args.target == "apif":
        # one day's slice of the resumable API-Football backfill (quota-bounded)
        from src.ingest.api_football import run_backfill
        run_backfill()
        return 0

    if args.target == "apif-status":
        from src.ingest.api_football import (api_football_targets, catalog_status,
                                             write_catalog_report)
        max_page = int(load_settings()["api_football"]["max_page"])
        report = write_catalog_report(catalog_status(api_football_targets(), max_page), None)
        print(report.read_text(encoding="utf-8"))
        return 0

    run_phase(args.target, refresh=args.refresh)
    run_gate(args.target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
