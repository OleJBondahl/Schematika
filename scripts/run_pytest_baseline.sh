#!/usr/bin/env bash
set +e
OUT="${1:-docs/baselines/2026-04-24}"
mkdir -p "$OUT"
uv run pytest --cov=src/schematika --cov-report=term-missing --cov-report=html:"$OUT/coverage_html" > "$OUT/pytest.txt" 2>&1
rc=$?
printf '\n---\nEXIT=%d\n' "$rc" >> "$OUT/pytest.txt"
echo "pytest exit=$rc"
