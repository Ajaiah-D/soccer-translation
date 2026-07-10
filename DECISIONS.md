# DECISIONS.md — decision log (spec §0.2)

Every non-trivial choice: what was decided, alternatives, reasoning, reversibility.

---

## D-001: Task runner = Makefile + `python -m src` CLI (dual)
- **Decided:** Provide a Makefile for POSIX/CI *and* a cross-platform `python -m src <phase>` CLI; both call the same entry points. Documentation treats the CLI as primary on this Windows host.
- **Alternatives:** Makefile only (spec default); install GNU make on Windows.
- **Reasoning:** `make` is absent on the build host. Spec §0.6 explicitly allows "a CLI". Dual keeps `make phaseN` working elsewhere.
- **Reversible:** yes

## D-002: Python 3.12 toolchain via uv, not system Python 3.14
- **Decided:** Pin `requires-python = ">=3.12,<3.13"` and let uv provision 3.12.
- **Alternatives:** system Python 3.14.
- **Reasoning:** soccer-data libraries and their compiled deps lag newest CPython; 3.12 is the safest widely-supported pin. uv.lock pins all dependency versions (spec §0.6).
- **Reversible:** yes

## D-003: Seasons 2018–2025 for both ASA and FBref
- **Decided:** Pull 2018–2025 inclusive (configurable in `config/settings.yaml`).
- **Alternatives:** all ASA history (2013+); shorter window.
- **Reasoning:** Wide enough to capture movers across the modern pyramid (MLS NEXT Pro from 2022, USL Super League from 2024 appear where they exist); avoids very old seasons whose metric definitions and league composition differ, and keeps API load modest per ASA's request.
- **Reversible:** yes (config change + `--refresh`)

## D-004: European comparison scope = Premier League only (FBref)
- **Decided:** Start with ENG-Premier League as the sole European league.
- **Alternatives:** Big-5 leagues; Championship.
- **Reasoning:** FBref scraping is slow and aggressively rate-limited; the MVP's calibration lives mostly inside the American pyramid (ASA covers all its leagues). One European anchor exercises the cross-source path without hammering FBref. More leagues = config addition later.
- **Reversible:** yes

## D-005: Empty API results are cached
- **Decided:** A pull that legitimately returns zero rows is cached as an empty frame with `content_hash="empty"`.
- **Alternatives:** re-fetch empties every run.
- **Reasoning:** "No data for this league/season" is a real answer (e.g. USL Super League before 2024). Caching it keeps re-runs at 0 network calls (Phase 1 gate).
- **Reversible:** yes
