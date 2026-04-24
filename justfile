# Schematika task runner
# Usage: just <target>

default:
    @just --list

# fast checks — run before every commit
check:
    uv run ruff format --check src tests
    uv run ruff check src tests
    uv run ty check
    pre-commit run --all-files

# tests
test:
    uv run pytest

cov:
    uv run pytest --cov=src/schematika --cov-report=term-missing

# live metrics — CLAUDE.md links here
stats:
    uv run python claude-tools/stats.py

# mutation testing (slow — weekly)
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

# purity gate (advisory)
purity:
    uv run python claude-tools/fp_purity_gate.py

# API style gate (advisory)
api-style:
    uv run python claude-tools/api_style_gate.py

# full local CI — run all gates
ci: check test purity api-style
