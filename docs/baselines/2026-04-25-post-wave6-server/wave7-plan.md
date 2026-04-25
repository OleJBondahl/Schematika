# Wave 7 — close mutmut survivors

**Source data:** `docs/baselines/2026-04-25-post-wave6-server/mutmut_results.txt`
(16,550 mutants, 11,485 killed, **3,240 survived**, 1,671 no-tests, 154 timeouts).

Three independent priorities, dispatched in parallel via worktree-isolated
subagents. Each one targets a cluster of weakly-tested code identified by the
Wave 6 mutmut run on the Linux server.

## Priority W7-1 — `cable/` test scaffold

**Scope:** 444 mutants currently uncovered (most in `cable/builder.py` +
`cable/renderer.py`). Two existing test files (`test_cable_export.py`,
`test_cable_registry.py`) test `Project`-level cable behavior, not the cable
module itself.

**Deliverables:**

- `tests/unit/test_cable_builder.py` — covers `build_cable_drawings`, slot
  packing, label sourcing, color rules, error paths in `cable/errors.py`.
- `tests/unit/test_cable_model.py` — round-trips `CableDrawing`,
  `CableConnection`, `CableEnd` dataclasses; validates frozen-ness; checks
  `__post_init__` invariants.
- `tests/unit/test_cable_renderer.py` — calls `render` against fabricated
  `CableDrawing` inputs; asserts wireviz invocation parameters and SVG
  contents (not byte-exact, but key elements present).

**Target:** kill ≥250 of the 444 mutants. Don't chase mutants in `wireviz`
output formatting that we don't own — bound the `renderer.py` tests to our
inputs/outputs at the boundary.

**Forbidden:**
- Editing source under `src/schematika/cable/` (this is a *test-only* wave).
- Mocking `wireviz`. Use real wireviz; if it's not installed, mark the
  module under `pytest.importorskip("wireviz")`.

## Priority W7-2 — symbol factory geometry tests

**Scope:** 1,229 survivors + 267 no-tests across `electrical/symbols/` and
`pid/symbols/`. Top survivor concentrations:

| File | Survivors |
|---|---:|
| `electrical/symbols/contacts.py` | 278 |
| `pid/symbols/piping.py` | 137 |
| `electrical/symbols/motors.py` | 125 |
| `pid/symbols/valves.py` | 120 |
| `electrical/symbols/blocks.py` | 113 |
| `pid/symbols/vessels.py` | 107 |
| `electrical/symbols/protection.py` | 78 |
| `electrical/symbols/terminals.py` | 52 |
| `pid/symbols/instruments.py` | 31 |
| `electrical/symbols/references.py` | 31 |
| `electrical/symbols/breakers.py` | 31 |
| `electrical/symbols/connector_pins.py` | 29 |

**Diagnosis:** existing tests assert structural facts (port count, label
text, has-correct-keys) but not geometry — port positions, element ordering,
exact dimensions. mutmut mutations on coordinate arithmetic, port directions,
and rect vs. line element choice slip past structural-only assertions.

**Deliverables:**

- `tests/unit/symbols/test_electrical_geometry.py` — parametric tests across
  every electrical symbol factory: assert exact port `Point` / `Vector`
  values, exact element counts by type (Line/Circle/Rect/Text), exact
  element coordinates for at least one canonical instance per factory.
- `tests/unit/symbols/test_pid_geometry.py` — same for PID factories.
- Reuse fixtures and parametrize aggressively. One test function with 20
  params is better than 20 single-instance tests.

**Target:** kill ≥600 of the 1,229 survivors. Don't expand to test
*every* mutation — a representative geometry assertion per factory is
enough; the parametric structure handles the rest.

**Forbidden:**
- Touching factory source. Add tests only.
- Snapshot-based assertions ("compare to saved SVG"). Use explicit numeric
  assertions — they're what mutmut needs to catch arithmetic mutations.

## Priority W7-3 — `Project` class method coverage

**Scope:** 296 survivors + 262 no-tests in `project.py`. Top concentrations
of survivors are in BOM/system export paths:

| Method | Survivors |
|---|---:|
| `_export_bom_excel` | 73 |
| `build` | 40 |
| `_export_bom_csv` | 28 |
| `_generate_system_csv` | 21 |
| `_add_page_to_compiler` | 20 |
| `_generate_bom_typst` | 11 |
| `_build_descriptor_circuit` | 11 |
| `_aggregate_bom` | 11 |
| `_resolve_svg_for_page` | 10 |
| `_resolve_field_devices` | 9 |

Plus 262 mutants in `add_*` / `page` / `block_page` / `set_*` methods that
have **zero** test coverage.

**Deliverables:**

- `tests/unit/project/test_bom_export.py` — fixture builds a small `Project`
  with 2-3 circuits, calls `_aggregate_bom`, `_export_bom_csv`,
  `_export_bom_excel`, asserts row counts, column ordering, and totals.
  No PDF compile.
- `tests/unit/project/test_page_assembly.py` — calls `add_circuit`,
  `add_pcb`, `add_block_diagram`, `page`, `block_page` and asserts the
  internal `pages`/`circuits` state matches expectations. Verifies
  `_add_page_to_compiler` builds the right SVG list.
- `tests/unit/project/test_resolvers.py` — covers
  `_resolve_svg_for_page`, `_resolve_field_devices`,
  `_build_descriptor_circuit` with fabricated inputs.

**Target:** kill ≥250 of the 296 survivors and exercise ≥150 of the 262
no-tests.

**Forbidden:**
- Editing `project.py`. Tests only.
- Calling `Project.build()` end-to-end (it's a PDF compile — slow + needs
  typst). Use the internal methods directly with fixtures.

## Dispatch model

Three subagents in parallel via `Agent` with `isolation: worktree`. Each
gets a self-contained prompt referencing this plan. They commit and push to
their own worktree branches; the parent merges fast-forward when each
finishes.

Exit gates per agent (all must pass before commit):

1. `uv run pytest -x -q --no-cov` — green, no new failures.
2. `uv run ruff check tests/` — green.
3. `uv run pre-commit run --files <new test files>` — green.
4. Test count delta: at least the target number of new tests added.

After all three land, capture a post-Wave-7 mutmut run on the server (same
config) and compare survivor counts to the post-Wave-6 baseline. Expected
delta: ~1,100-1,300 fewer survivors total.

## What this wave is NOT

- Not refactoring source. Tests only.
- Not chasing every survivor. The point is signal density, not 100% kill.
- Not adding mocks for unowned dependencies (wireviz, typst, mcp).
