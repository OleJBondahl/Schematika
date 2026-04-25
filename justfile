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
    uv run pre-commit run --all-files

# tests
test:
    uv run pytest --continue-on-collection-errors

cov:
    uv run pytest --cov=src/schematika --cov-report=term-missing

# runnable doctests in src/ — A3 gate. Pre-commit hook runs the same command.
doctest:
    uv run pytest --doctest-modules src/schematika --no-cov -q

# live metrics — CLAUDE.md links here
stats:
    uv run python scripts/stats.py

# mutation testing — Linux-only, slow, off-machine before tagged releases.
# Wired but not run by `just ci`. Reads paths from pyproject.toml [tool.mutmut].
mutmut:
    uv run mutmut run

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

# tier-1 API docstring audit — human-readable report. The pre-commit hook gates on --strict.
api-audit:
    uv run python scripts/api_docs_audit.py

# refresh docs/api-audit/baseline.md from current state (commit alongside doc edits)
api-audit-update:
    uv run python scripts/api_docs_audit.py --markdown

# numeric ratchet — verifies counts haven't regressed against docs/ratchet/baseline.toml
ratchet:
    uv run python scripts/ratchet_check.py

# update the ratchet baseline after a deliberate improvement (re-run ci first!)
ratchet-update:
    uv run python scripts/ratchet_check.py --update

# capture full metrics snapshot — non-blocking, advisory, structured for trend tracking
metrics:
    uv run python scripts/metrics_snapshot.py

# full local CI — every gate (incl. doctest hook) + full test suite + numeric ratchet.
# Excludes mutmut (Linux-only, run separately via `just mutmut`).
ci: gates test ratchet
