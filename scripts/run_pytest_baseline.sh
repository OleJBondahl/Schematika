#!/usr/bin/env bash
set +e
OUT=docs/baselines/2026-04-24
uv run pytest --cov=src/schematika --cov-report=term-missing --cov-report=html:docs/baselines/2026-04-24/coverage_html > "$OUT/pytest.txt" 2>&1
rc=$?
printf '\n---\nEXIT=%d\n' "$rc" >> "$OUT/pytest.txt"
echo "pytest exit=$rc"
