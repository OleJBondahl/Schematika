#!/usr/bin/env bash
# Chunked mutmut runner — one invocation per file so each mutmut process
# exits and releases its memory before the next file starts. Mutmut's
# .mutmut-cache sqlite is shared across invocations, so already-tested
# mutants are skipped automatically. Re-running resumes where interrupted.
#
# Usage:
#   bash scripts/run_mutmut_chunked.sh                              # whole src/schematika
#   bash scripts/run_mutmut_chunked.sh src/schematika/core          # subtree
#   OUT_DIR=docs/baselines/2026-04-24-post-wave6 bash scripts/run_mutmut_chunked.sh
#
# Env:
#   OUT_DIR   — where to write logs (default: docs/baselines/<today>-chunked)
#   RUNNER    — pytest command (default: full suite, no cov, -x)
#   RESET     — if "1", delete .mutmut-cache before starting (fresh run)
#
# Output:
#   $OUT_DIR/mutmut_chunked.log     per-file progress + exit codes
#   $OUT_DIR/mutmut_results.txt     consolidated results across all files
#   $OUT_DIR/mutmut_summary.txt     one-line-per-file summary

set +e

SCOPE="${1:-src/schematika}"
OUT_DIR="${OUT_DIR:-docs/baselines/$(date +%F)-chunked}"
RUNNER="${RUNNER:-python -m pytest -x -q --no-cov}"

mkdir -p "$OUT_DIR"

# Windows venv hygiene — same as scripts/run_mutmut.sh.
export PATH="$(pwd)/.venv/Scripts:$PATH"
export VIRTUAL_ENV="$(pwd)/.venv"
export PYTHONIOENCODING=utf-8

MUTMUT=".venv/Scripts/mutmut.exe"
[ -x "$MUTMUT" ] || MUTMUT="mutmut"

LOG="$OUT_DIR/mutmut_chunked.log"
SUMMARY="$OUT_DIR/mutmut_summary.txt"
: > "$LOG"
: > "$SUMMARY"

if [ "${RESET:-0}" = "1" ]; then
    echo "RESET=1: removing .mutmut-cache" | tee -a "$LOG"
    rm -f .mutmut-cache
fi

# Discover files. Skip __init__.py, _purity.py (no-op shim), __main__.py
# (mcp server blocks on stdio import), and py.typed marker.
mapfile -t FILES < <(
    find "$SCOPE" -type f -name "*.py" \
        ! -name "__init__.py" \
        ! -name "_purity.py" \
        ! -name "__main__.py" \
        | sort
)

TOTAL_FILES="${#FILES[@]}"
echo "Chunked mutmut: $TOTAL_FILES files under $SCOPE" | tee -a "$LOG"
echo "Output dir:    $OUT_DIR" | tee -a "$LOG"
echo "Runner:        $RUNNER" | tee -a "$LOG"
echo "Cache:         .mutmut-cache (persistent across chunks)" | tee -a "$LOG"
echo "Started:       $(date)" | tee -a "$LOG"
echo "" | tee -a "$LOG"

START_EPOCH=$(date +%s)

for i in "${!FILES[@]}"; do
    F="${FILES[$i]}"
    IDX=$((i + 1))
    CHUNK_START=$(date +%s)

    printf '[%d/%d] %s\n' "$IDX" "$TOTAL_FILES" "$F" | tee -a "$LOG"

    # Run mutmut on this file only. Each invocation exits cleanly, freeing
    # all accumulated Python objects. The sqlite cache dedupes across runs.
    "$MUTMUT" run \
        --paths-to-mutate "$F" \
        --runner "$RUNNER" \
        > "$OUT_DIR/.chunk.stdout" 2>&1
    rc=$?

    # Strip spinner carriage-returns so the tail is real output, not 5 spinner frames.
    tr '\r' '\n' < "$OUT_DIR/.chunk.stdout" | grep -vE '^(⠋|⠙|⠹|⠸|⠼|⠴|⠦|⠧|⠇|⠏)' \
        | tail -5 | tee -a "$LOG"

    CHUNK_ELAPSED=$(($(date +%s) - CHUNK_START))

    # Extract final N/M progress from the stdout stream (mutmut run doesn't
    # print a kill/survive summary — results come from the cache sqlite).
    PROGRESS=$(tr '\r' '\n' < "$OUT_DIR/.chunk.stdout" | grep -oE '^[0-9]+/[0-9]+' \
        | awk -F/ '{print $1+0, $0}' | sort -n | tail -1 | awk '{print $2}')
    STATS="mutants=${PROGRESS:-?}"

    printf '%-70s rc=%d %ds %s\n' "$F" "$rc" "$CHUNK_ELAPSED" "$STATS" >> "$SUMMARY"
    printf '  exit=%d  elapsed=%ds  %s\n\n' "$rc" "$CHUNK_ELAPSED" "$STATS" | tee -a "$LOG"

    # Free Python bytecode cache in project tree (not .venv!). Prevents the
    # __pycache__ growth that correlated with the previous run's OOM.
    find src/ tests/ -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
    rm -rf .pytest_cache 2>/dev/null
done

rm -f "$OUT_DIR/.chunk.stdout"

TOTAL_ELAPSED=$(($(date +%s) - START_EPOCH))

echo "=== All chunks complete in ${TOTAL_ELAPSED}s ===" | tee -a "$LOG"
echo "" | tee -a "$LOG"
echo "Consolidating results..." | tee -a "$LOG"
"$MUTMUT" results > "$OUT_DIR/mutmut_results.txt" 2>&1
printf '\n---\nEXIT=%d\n' "$?" >> "$OUT_DIR/mutmut_results.txt"

echo "" | tee -a "$LOG"
echo "Final outputs:" | tee -a "$LOG"
echo "  $OUT_DIR/mutmut_chunked.log   (this log)" | tee -a "$LOG"
echo "  $OUT_DIR/mutmut_summary.txt   (per-file one-liner)" | tee -a "$LOG"
echo "  $OUT_DIR/mutmut_results.txt   (consolidated survivor list)" | tee -a "$LOG"
echo "" | tee -a "$LOG"
echo "Last 20 lines of consolidated results:" | tee -a "$LOG"
tail -20 "$OUT_DIR/mutmut_results.txt" | tee -a "$LOG"
