# POSIX task runner. On Windows without make, use the equivalent CLI:
#   python -m src <target>   (e.g. python -m src phase1)
# Both paths call the same code in src/__main__.py.

UV := python -m uv

.PHONY: setup test phase0 phase1 phase2 phase3 phase4 phase5 all report

setup:
	$(UV) sync

test:
	$(UV) run pytest

phase0:
	$(UV) run python -m src phase0

phase1:
	$(UV) run python -m src phase1

phase2:
	$(UV) run python -m src phase2

phase3:
	$(UV) run python -m src phase3

phase4:
	$(UV) run python -m src phase4

phase5:
	$(UV) run python -m src phase5

all:
	$(UV) run python -m src all

report:
	$(UV) run python -m src report
