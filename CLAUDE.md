# Schematika

## Project Overview

Python library for programmatically generating IEC 60617-compliant electrical schematic diagrams as SVG. **Zero runtime dependencies**, targets Python 3.12+. Current version: 0.1.7 (Alpha).

Data-first approach: engineers describe circuits as Python data structures, the library renders standards-compliant SVG output.

## Build & Development Commands

```bash
uv sync                                          # Install dependencies
pytest                                            # Run all tests (with coverage)
PYTEST_UPDATE_SNAPSHOTS=1 pytest                  # Update SVG snapshots
uv run ty check                                   # Type checking
uv run ruff check                                 # Linting
uv run ruff format                                # Formatting
```

## Architecture: Three-Layer API

1. **Project API** (`project.py`): Multi-page schematics, title blocks, PDF compilation.
2. **Circuit API** (`builder.py`, `descriptors.py`): `CircuitBuilder` fluent API, `BuildResult`, `build_from_descriptors()`.
3. **Symbol API** (`model/`, `system/`, `symbols/`): IEC symbol factories, Symbols, Ports, Circuits.

**Data flow:** `State (autonumbering) → Symbol factories → Circuit container → Layout/wiring → SVG render`

## Core Principles

- **Zero runtime dependencies** — everything built-in for SVG generation
- **Immutability by default** — frozen dataclasses. Four exceptions: `Circuit`, `Project`, `CircuitBuilder`, `PlcMapper` (mutable builders)
- **Functional state threading** — explicit `dict[str, Any]` state, no global mutable state
- **Grid-based coordinates** — 5mm grid (`GRID_SIZE`), origin top-left, Y increases downward, mm units
- **Standards compliance** — IEC 60617 symbols, ISO 14617 P&ID, ISA 5.1 instruments

## Import Order Sensitivity

**WARNING**: `__init__.py` files have deliberate import ordering to avoid circular imports. Do NOT reorder:
- `src/schematika/electrical/model/__init__.py` — `core` before `parts`
- `src/schematika/electrical/utils/__init__.py` — `utils` before `autonumbering`

These use `# noqa: E402` and `# noqa: I001` comments.

## Exception Hierarchy

All inherit from `CircuitValidationError`: `PortNotFoundError`, `ComponentNotFoundError`, `TagReuseError`, `TerminalReuseError`, `WireLabelMismatchError`. Old names kept as aliases.

## Name Collision: `Terminal`

- `terminal.py:Terminal(str)` — Primary type. Immutable `str` subclass with metadata. This is what users import.
- `symbols/terminals.py:TerminalSymbol(Symbol)` — Internal rendered symbol. Renamed from `Terminal`.

## Port ID Conventions

Not standardized — follow IEC per component type:
- Numeric: `"1"`, `"2"` (contacts)
- IEC non-sequential: `"1"`, `"2"`, `"4"` (SPDT)
- Semantic: `"U"`, `"V"`, `"W"`, `"PE"` (motors)
- Composite: `"1_com"`, `"1_nc"`, `"1_no"` (multi-pole)

## P&ID Module (`pid/`)

ISO 14617 / ISA 5.1 P&ID diagrams. Standards reference in `pid/constants.py` docstring.
- `PIDBuilder` — fluent builder, port-to-port alignment, ISA 5.1 letter code enforcement
- `validate_pid()` — overlap, boundary, stroke weight checks
- Key constants: equipment gap 30mm, leg spacing 40mm, bubble 12mm diameter, valve 10mm

## Testing

- pytest with pytest-cov. **Baseline: 1233 tests, 90% coverage.**
- SVG snapshot testing via `snapshot_svg` fixture — set `PYTEST_UPDATE_SNAPSHOTS=1` to update.

## Type Checking

~54 diagnostics baseline. Known false positives on `Terminal.__slots__`, `Point`/`Style` as `Element`, dynamic `__setattr__`.

## Consumer Project

`../auxillary_cabinet_v3/` is the primary consumer. See `todo.md` for audit-driven task list.

## P&ID Visual Iteration

```
1. Edit code → 2. Build: cd ../auxillary_cabinet_v3 && uv run python src/pid.py
3. Convert: uv run python scripts/pid_review.py <svg> → 4. Read PNG → 5. Fix → repeat
```

Requires: `uv sync --extra dev` then `uv run playwright install chromium`.
