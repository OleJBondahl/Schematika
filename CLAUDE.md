# Schematika — agent guide

Python 3.14+ library that generates IEC 60617 / ISO 14617 / ISA 5.1 diagrams as SVG. Alpha, sole author. Breaking changes are fine. Zero runtime deps in the core.

## Mandatory skills (invoke before any code work)

Two global skills are the canonical guide for *how* code in this repo is written and reviewed. Invoke both at the start of any non-trivial task:

- **`python-coding-and-tooling`** — Mandatory toolchain (uv, ruff, ty, pytest, deal, vulture), forbidden tools (no bandit/radon/docstr-coverage/darglint/pydoclint/mypy/black), pyproject template, and the docstring style this repo follows. Read this first when adding code, choosing tools, or writing docstrings.
- **`reviewing-ai-generated-python`** — 13 AI-code-smell patterns with grep/AST signals. Read this when reviewing diffs, auditing modules, or before claiming a feature is done.

Conflicts between these skills and this `CLAUDE.md` are resolved as: **CLAUDE.md wins for repo-specific facts** (the invariants below, file layout, port-ID conventions); the **skills win for tooling, code style, and docstring conventions**. If you're unsure which applies, ask.

## Before exploring source

1. Read `.codesight/wiki/index.md` if it exists (auto-generated map of the codebase).
2. Read `docs/ARCHITECTURE.md` for the package layering.
3. Read `docs/API_STYLE.md` before designing a public API. The ruff hooks and `scripts/api_style_gate.py` enforce most of it.

Current numbers (LoC, test count, coverage, ty diagnostics) are not pinned here on purpose. Run `just stats` for the live values. If you need to put a number in a doc, put it in the commit that adds the check that enforces it.

## Invariants

1. `core/` is I/O-free. No `open`, `subprocess`, `datetime.now`, `print`. Clock reads get passed in as a `now` parameter.
2. `core/` never imports from any domain package (`electrical/`, `pcb/`, `pid/`, `cable/`, `block/`, `catalog/`). Domain packages import from `core/`.
3. No package imports from `project.py`. `project.py` consumes the domain packages. The import-linter contract enforces this.
4. Domain modules (`electrical.build_*`, `pcb.build`, `pid.PIDBuilder.build`, `cable.*`, `block.*`) return data classes, never a `Project`.
5. Frozen dataclasses by default. Builders are the explicit exception; add one and document why in the class docstring.

## Red flags (reject or rewrite on sight)

- `symbol.rotate(180)`. Symbols have no `.rotate()` method. Use the free function: `rotate(symbol, 180)`.
- Returning `Project` (or `None`) from a builder's `build()`. Every builder returns its own frozen `*BuildResult`.
- `add_thing(self, x, y, ...)`. Public APIs take `position: Point | None`, not scalar pairs.
- `x, y, label=...` with no `/` and no `*` markers. Public methods take one positional arg (identity) then keyword-only.
- Bare `except Exception:` that returns a default. Narrow the exception or let it propagate.
- New `ValueError` for domain validation. Use the domain base: `CircuitValidationError`, `PIDError`, `PCBBuildError`, `CableError`.
- New `__init__.py` with `from .thing import *` added in the middle of an ordering-sensitive file. See below.

## Name collisions

- `Terminal` lives in `electrical/terminal.py`. It is a `str` subclass carrying metadata. This is what users import.
- `TerminalSymbol` lives in `electrical/symbols/terminals.py`. Internal rendered symbol. Not the same thing.

## Exceptions

All electrical domain errors live in `core/exceptions.py` and inherit from `CircuitValidationError`. `electrical/exceptions.py` re-exports aliases for old import paths.

Other domains have their own base: `PIDError` (`pid/errors.py`), `PCBBuildError` (`pcb/errors.py`), `CableError` (planned).

## Import-order-sensitive files

These files reorder imports deliberately to break cycles. Do not rearrange. Each uses `# noqa: E402` or `# noqa: I001`.

- `src/schematika/electrical/__init__.py:7` — `system.system` before the rest.
- `src/schematika/electrical/model/__init__.py` — `core` first, then `primitives`, `parts`, `constants`.
- `src/schematika/electrical/model/constants.py:16,149` — two deferred imports.
- `src/schematika/electrical/utils/__init__.py` — `utils` before `autonumbering` before `renderer`.
- `src/schematika/catalog/__init__.py` — order `errors → device → registry → cables` (breaks the `cables.py` → `registry.py` runtime-import cycle). Protected by the blanket `__init__.py` `I001` ignore in `pyproject.toml`, not a per-line `# noqa`.

If ruff tries to reorder these on format, add the `noqa` comment rather than "fixing" it.

## Port ID conventions

Per IEC, per component type. Not standardized across the library because IEC isn't.

- Numeric: `"1"`, `"2"` (contacts, breakers).
- IEC non-sequential: `"11"`, `"12"`, `"14"` (SPDT pole 1).
- Semantic: `"U"`, `"V"`, `"W"`, `"PE"` (motors).
- Composite: `"1_com"`, `"1_nc"`, `"1_no"` (multi-pole SPDT — document at the symbol factory).

When adding a new symbol, write the port IDs in its factory docstring. `docs/LLM_REFERENCE.md` is the catalog.

## Build commands

```bash
uv sync --all-extras  # pcb tests need skidl/openpyxl/typst/wireviz/mcp to collect
uv run pytest
uv run ruff check
uv run ruff format
uv run ty check
just stats            # live LoC, test count, coverage, ty diagnostic count
just ci               # canonical local CI: every gate (via pre-commit) + full pytest. Run before any merge to `branch1`.
```

Set `PYTEST_UPDATE_SNAPSHOTS=1` before `pytest` to regenerate SVG snapshots.

## Consumer project

`../auxillary_cabinet_v3/` drives real-world API changes. When a public API shifts, grep that repo for the old name before declaring the rename done.

## P&ID visual review loop

```
1. Edit symbol/layout code
2. cd ../auxillary_cabinet_v3 && uv run python src/pid.py
3. uv run python scripts/pid_review.py <svg>
4. Read the PNG and the validate_pid() output
5. Fix, repeat
```

Requires `uv sync --extra dev` and `uv run playwright install chromium`.
