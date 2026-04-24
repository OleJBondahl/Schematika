#!/usr/bin/env bash
# Run all baseline metric tools, capture stdout+stderr + exit code to a file each.
# Never bails on failure — every tool is expected to possibly fail; we want the output.

set +e
OUT="${1:-docs/baselines/2026-04-24}"
mkdir -p "$OUT"

run() {
    # $1 = output file basename, $2+ = command
    local file="$OUT/$1"
    shift
    echo ">>> $* (file=$file)"
    "$@" > "$file" 2>&1
    local rc=$?
    printf '\n---\nEXIT=%d\n' "$rc" >> "$file"
    return 0
}

run loc_by_file.txt scc src/ tests/ --by-file
run loc_summary.txt scc src/ tests/
run ruff_stats.txt uv run ruff check --statistics
run ruff_full.txt bash -c 'uv run ruff check --output-format=concise 2>&1 | head -2000'
run ty.txt uv run ty check
run interrogate.txt uv run interrogate -vv src/
run vulture.txt uv run vulture src/ --min-confidence 60
run import_linter.txt uv run lint-imports
run purity_gate.txt uv run python scripts/fp_purity_gate.py
run api_style_gate.txt uv run python scripts/api_style_gate.py
run darglint.txt bash -c 'uv run darglint -s google src/schematika/ 2>&1 | head -4000'
run complexity.txt uv run ruff check --select C90 --statistics

echo "All metric tools done."
