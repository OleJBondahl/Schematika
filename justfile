# Schematika task runner
# Usage: just <target>

default:
    @just --list

# fast checks — run before every commit
check:
    uv run ruff format --check src tests
    uv run ruff check src tests
    uv run ty check

# all gates (no test) — what pre-commit also runs
gates:
    pre-commit run --all-files

# tests
test:
    uv run pytest --continue-on-collection-errors

cov:
    uv run pytest --cov=src/schematika --cov-report=term-missing

# live metrics — CLAUDE.md links here
stats:
    uv run python scripts/stats.py

# mutation testing — slow, Linux-only (Windows incompat on this machine).
# Run periodically off-machine before tagged releases. NOT in `just ci`.
mutate module="src/schematika/pcb/builder.py":
    uv run mutmut run --paths-to-mutate {{module}}

# dead code sweep (manual — confidence 60)
dead-code:
    uv run vulture src --min-confidence 60

# docs
docs:
    uv run pdoc src/schematika -o docs/api

docs-test:
    uv run pytest --doctest-glob='*.md' docs/ README.md

# LLM context
context:
    npx repomix

context-wiki:
    npx codesight --wiki

# purity gate (also run inside `just gates` via pre-commit)
purity:
    uv run python scripts/fp_purity_gate.py

# API style gate (also run inside `just gates` via pre-commit)
api-style:
    uv run python scripts/api_style_gate.py --strict

# full local CI — every gate + full test suite. Excludes mutmut (Linux-only).
ci: gates test
