@echo off
rem Daily slice of the API-Football backfill, for Windows Task Scheduler.
rem Appends to logs\apif_daily.log in the repo.
cd /d "%~dp0.."
if not exist logs mkdir logs
echo ==== %date% %time% >> logs\apif_daily.log
python -m uv run python -m src apif >> logs\apif_daily.log 2>&1
