#!/usr/bin/env bash
set +e
OUT=docs/baselines/2026-04-24
mkdir -p "$OUT"

# Put venv python at front of PATH so mutmut's cmd.exe-spawned `python -m pytest`
# hits the project's interpreter, not some system one.
export PATH="$(pwd)/.venv/Scripts:$PATH"
# Also set VIRTUAL_ENV so pytest picks up the right site-packages
export VIRTUAL_ENV="$(pwd)/.venv"

# Use .venv mutmut directly (skip `uv run` re-resolve)
.venv/Scripts/mutmut.exe run > "$OUT/mutmut_run.txt" 2>&1
rc=$?
printf '\n---\nEXIT=%d\n' "$rc" >> "$OUT/mutmut_run.txt"
echo "mutmut run exit=$rc"

.venv/Scripts/mutmut.exe results > "$OUT/mutmut_results.txt" 2>&1
rc2=$?
printf '\n---\nEXIT=%d\n' "$rc2" >> "$OUT/mutmut_results.txt"
echo "mutmut results exit=$rc2"
