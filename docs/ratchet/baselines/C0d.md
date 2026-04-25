# Wave C0d baseline — small C901 cleanup batch (8 functions)

Branch base: `branch1` @ `6b0bc25` (post-C0c).
Wave branch: `complexity/C0d` in worktree `.worktrees/complexity/C0d`.

## State at start

`docs/ratchet/baseline.toml`:
```
[complexity]
max_complexity   = 22  (held by _phase4_render_graphics; not in this wave)
max_args         = 16
max_branches     = 22
max_statements   = 69
max_returns      =  0
[pytest]
min_passing               = 1920
min_coverage_percent      =  90
min_core_coverage_percent =  94
```

`pyproject.toml`: `max-complexity = 22`, `max-args = 16`, `max-branches = 22`, `max-statements = 70`, `max-returns = 6`.

C901 violators at default threshold 10 in `src/` (20 total). C0d targets 8 of them — the small fish in the 11-13 range. Listed below in difficulty order.

## Wave scope

8 isolated function refactors. Each function should drop its C901 count below 11 (i.e., to ≤ 10, ruff's default). No function is touched outside its own body and an inline-extracted helper. Tests added per function as needed.

**The implementer should batch by file, commit each batch separately**, and report DONE_WITH_CONCERNS if any of the 8 prove harder than expected (deferring is fine — controller will dispatch a follow-up wave).

### The 8 targets (ordered easiest → hardest)

#### Group 1: rendering/svg.py (2 isinstance-chain rewrites)

1. **`_render_element`** at `src/schematika/rendering/svg.py:25` (complexity 12). 7-arm isinstance chain dispatching on `Element` subtype, each arm building an XML element. Convert to `match`/`case` (matches the C0a `translate` precedent). Single-return not applicable since the function mutates `parent: ET.Element` in place — but reducing from `if/elif` to `match` reduces the cyclomatic count. Behaviour-preserving.

2. **`to_xml_element`** at `src/schematika/rendering/svg.py:83` (complexity 12). Has an inner `_parse_dim` closure + several `if width == "auto"`/`if height == "auto"` decision branches. Extract `_parse_dim` to module scope (top-level `@deal.pure` helper if pure, otherwise module-level non-decorated). Consolidate the `width == "auto"` / `height == "auto"` branches via a single `_resolve_dim(val, default, auto_value)` helper.

#### Group 2: core/renderer.py (1 isinstance-chain in nested closure)

3. **`calculate_bounds`** at `src/schematika/core/renderer.py:48` (complexity 13). Has inner `process(elem)` closure with 5-arm isinstance chain + an `_expand(x, y)` mutation closure. Two options:
   - (a) Convert `process` isinstance chain to `match`/`case`.
   - (b) Replace the closures with a top-level `@deal.pure` helper `_bounds_for_element(elem) -> tuple[float, float, float, float]` that returns the bounds for one element; `calculate_bounds` then folds them. Removes the `nonlocal` and the closures, easier to test. Prefer (b).

#### Group 3: standalone refactors (5 individual fixes)

4. **`_three_pole_motor`** at `src/schematika/electrical/symbols/motors.py:46` (complexity 11). Read it. Likely a builder with several `if`-driven shape variations. Extract repeated `Symbol(...)` construction blocks if they're nearly identical, OR convert any nested `if`/`elif` to a small dispatch.

5. **`parse_terminal_pins_from_csv`** at `src/schematika/electrical/utils/terminal_bridges.py:59` (complexity 11). Likely a CSV-row parsing loop with several `if/elif` branches. Extract `_parse_row(row)` helper.

6. **`_convert_lines`** at `src/schematika/rendering/typst/markdown_converter.py:46` (complexity 12). Markdown-line-conversion logic with several `if line.startswith(...)` arms. Extract per-prefix handlers (table dispatch on prefix → handler function), OR convert the if-chain to `match`/`case` on a small enum.

7. **`_add_page_to_compiler`** at `src/schematika/project.py:1263` (complexity 13). Per-page-kind dispatch (similar to `_render_page` from C0a). `match`/`case` rewrite. **NOTE**: `project.py` is NOT in `core/` — it's the application orchestrator. No `@deal.pure` is required (the project module manipulates I/O state). But still: prefer `match` over `if/elif` for readability.

8. **`pid/builder.py:317` `build`** (complexity 11). PIDBuilder.build returns a frozen `PIDBuildResult` (per the project's "builders return their own *BuildResult, never Project" invariant). The complexity likely comes from validation-then-construction; extract `_validate(self) -> None` and `_make_result(self, validated_data) -> PIDBuildResult` if they're cleanly separable.

## Done condition

For EACH target the implementer completes:

- Function's C901 complexity drops to ≤ 10 (verify per-function: `uv run ruff check src/<file> --select C901 --config 'lint.mccabe.max-complexity=10' --no-fix` — function should not appear in the output).
- All existing tests for that function still pass UNCHANGED.
- A characterisation test exists for any non-trivial branch the refactor touched. Use `pytest.mark.parametrize` for table-driven coverage where natural; `dirty_equals.IsApprox(delta=1e-9)` for any new floating-point comparison.

For the wave overall:

- `uv run pytest -q --continue-on-collection-errors` → ≥ 1938 (the new floor, no regression).
- `uv run pytest --cov=src/schematika/core` core TOTAL ≥ 94%.
- `uv run python scripts/api_style_gate.py --strict` → 0 violations.
- `uv run python scripts/api_docs_audit.py --strict` → 0 gaps.
- `uv run pre-commit run --all-files` → exit 0.
- `uv run python scripts/ratchet_check.py` → exit 0; all 12 metrics green.
- **Threshold drop in `pyproject.toml`**: keep `max-complexity = 22` (the peak holder `_phase4_render_graphics` is unchanged — threshold drop is deferred until C1-tier refactors the build pipeline).

## Test strategy

For each target with insufficient existing tests:

- **Read existing tests first** (`grep -rn "<function_name>" tests/`). Most of these functions are already exercised by integration tests (e.g., `_render_element` is hit by every SVG-output test). A characterisation test is worth adding if a specific isinstance-arm or branch is uncovered.
- **`pytest.mark.parametrize` for table-driven tests** (one row per dispatch arm).
- **`dirty_equals.IsApprox(delta=1e-9)`** for any floating-point comparison.
- **Don't add hypothesis properties for trivial dispatch functions** — they don't add value beyond the parametrized table.

## Out of scope

- Touching any function NOT in the 8-target list. In particular: no changes to `_phase[1234]_*`, `add_terminal`/`add_symbol`/`add_spdt`/`build` in `electrical/builder.py`, or `block` in `electrical/symbols/blocks.py` (those are tier C0e or C1).
- Touching `parse`, `serialize`, `rotate_commands`, `translate_command` in `core/svg_path.py` — they're match-case dispatch with inherently high C901 (10 arms = 10+ complexity); a dispatch-table refactor is its own wave.
- Adding new public API (no new symbols in any package's `__all__`).
- Updating `docs/API_STYLE.md`.
- Threshold drops on any complexity rule (deferred).

## Notes for the implementer

- **Batch by file.** Three suggested batches: `rendering/svg.py` (2 functions, one commit), `core/renderer.py + ...` (mixed bag, one commit per file), `standalone misc` (one commit per function or grouped).
- **If you complete fewer than 8**, report DONE_WITH_CONCERNS and list which functions remain. The controller will dispatch a follow-up.
- **`_render_element` mutates `parent` in place** (XML SubElement creation). It can't be `@deal.pure`. The match/case refactor preserves the mutation; that's fine.
- **`to_xml_element` uses `isinstance(val, (int, float))`** (line 112) — newer Python prefers `isinstance(val, int | float)` per PEP 604, but only change if ruff's UP rules complain.
- **`calculate_bounds` is in `core/`** — must remain `@deal.pure`. The closure-elimination refactor (option b) preserves purity.
- **`pid/builder.py:317:build`**: returns `PIDBuildResult`. Confirm by reading the function before refactoring. If it returns something else, that's an API_STYLE violation that's separate work — flag and skip.
- **For `_add_page_to_compiler` in `project.py`**: project.py manipulates side-effecting state. Don't try to make it pure. Just reduce dispatch complexity.
- **No noqa workarounds**: if a function's complexity won't drop below 11 after a reasonable refactor, leave it alone and report DONE_WITH_CONCERNS — do NOT add `# noqa: C901` to satisfy a checklist item. Same lesson as C0b/C0c thresholds.
