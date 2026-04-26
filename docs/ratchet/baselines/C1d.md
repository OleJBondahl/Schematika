# Wave C1d baseline — `_phase4_render_graphics` complexity 22 → ≤ 5

Branch base: `branch1` @ `a3f2ef7` (post-C1c).
Wave branch: `complexity/C1d` in worktree `.worktrees/complexity/C1d`.

## State at start

`_phase4_render_graphics` at `src/schematika/electrical/builder_phases.py:473` is **complexity 22** — the highest in the codebase. After C1d, the C901 violator list in `builder_phases.py` should be EMPTY (all 4 phases ≤ 10), unlocking the threshold drops in C1e.

The function does THREE rendering passes in one body:

1. **Manual Connections Rendering** (lines 491-524): iterate `spec.manual_connections`, look up symbols, find ports, draw a `Line` between them, optionally add a wire label IF the line is vertical AND `spec.connection_wire_labels` has an entry for the index.

2. **Matching Connections Rendering** (lines 526-554): iterate `spec.matching_connections`, find common pin names between two components (`comp_a["pins"] ∩ comp_b["pins"]`, optionally filtered by `pin_filter`), draw lines for each common pin.

3. **Planned Chain Connections** (lines 556-588): iterate `spec.planned_connections` (filtered to `kind == "chain"`), use `draw_wire(sym1, sym2)` for the multi-segment wire, optionally add wire labels for each segment IF `has_per_connection_labels` AND `tgt_spec.wire_labels_above` has an entry.

All three sections share scaffolding:
- Iterate over a connection list
- Index-bounds check (`if idx >= len(realized_components): continue`)
- `"symbol"` presence check on both endpoints
- Symbol extraction

## Wave scope

**Internal complexity reduction only.** No change to public signature (`(c, realized_components, spec) -> None`) or behaviour. Inter-phase contract still `list[dict]`.

### Extract these helpers in `electrical/builder_phases.py` (above `_phase4_render_graphics`)

1. **`_get_endpoint_symbols(realized_components, idx_a, idx_b) -> tuple[Symbol, Symbol] | None`** — DRY the index-bounds + `"symbol"`-presence checks. Returns `(sym_a, sym_b)` if both endpoints are valid, else `None`. Used by all 3 rendering sections.

2. **`_render_manual_connections(c, realized_components, manual_connections, connection_wire_labels, style) -> None`** — encapsulates section 1. Uses `_get_endpoint_symbols`. Mutates `c.elements`.

3. **`_render_matching_connections(c, realized_components, matching_connections, style) -> None`** — encapsulates section 2. Uses `_get_endpoint_symbols`.

4. **`_render_planned_chain_connections(c, realized_components, planned_connections, has_per_connection_labels) -> None`** — encapsulates section 3. Uses `_get_endpoint_symbols`. Continues the `kind != "chain"` filter.

After extractions, `_phase4_render_graphics` becomes:

```python
def _phase4_render_graphics(
    c: Circuit,
    realized_components: list[dict[str, Any]],
    spec: CircuitSpec,
) -> None:
    """Phase 4: render manual/matching/chain wires; per-conn labels applied inline."""
    has_per_connection_labels = bool(spec.connection_wire_labels) or any(
        rc["spec"].wire_labels_above for rc in realized_components
    )
    style = standard_style()

    _render_manual_connections(
        c, realized_components, spec.manual_connections,
        spec.connection_wire_labels, style,
    )
    _render_matching_connections(
        c, realized_components, spec.matching_connections, style,
    )
    _render_planned_chain_connections(
        c, realized_components, spec.planned_connections, has_per_connection_labels,
    )
```

Target: complexity 22 → ≤ 5. Each helper individually < 10.

### Imports cleanup (try, don't force)

Phase 4 currently has 3 imports inside the function body (lines 479-484): `wire_labels`, `parts.standard_style`, `primitives.Line`. **Try to move them to module top**. Run `cd .worktrees/complexity/C1d && uv run python -c "import schematika"` (oh wait, that's blocked by hook — use `uv run pytest --collect-only -q 2>&1 | tail -5` instead, which forces import resolution). If no `ImportError` / `ModuleNotFoundError` is raised, the imports were not load-bearing for cycle-breaking and can be moved. If a cycle emerges (you'll see "circular import" in the output), leave them local to phase4 (or to the helpers that need them) — the previous in-function placement was deliberate.

If the imports are needed in MULTIPLE helpers (which is likely — `Line` is used in both manual and matching renderers, `standard_style` in all three), pull them to module top if no cycle, else import inside each helper that needs them. Don't have the helpers reach back into `_phase4_render_graphics` to get them.

## Done condition

- `_phase4_render_graphics` no longer in `uv run ruff check src/schematika/electrical/builder_phases.py --select C901 --config 'lint.mccabe.max-complexity=10' --no-fix`.
- The 4 new helpers also pass C901 at threshold 10.
- **`builder_phases.py` has ZERO C901 violators** at threshold 10 (all 4 phases + all helpers ≤ 10). This is the gating condition for C1e's threshold drops.
- `_phase4_render_graphics` signature + return type EXACTLY unchanged.
- `_phase[123]_*` UNCHANGED.
- All existing CircuitBuilder integration tests pass UNCHANGED. Phase 4 is exercised by SVG snapshot tests + per-symbol render tests — those are the regression net.
- `uv run pytest -q --continue-on-collection-errors` → ≥ 2005 (the new floor).
- `uv run python scripts/ratchet_check.py` → exit 0.
- `uv run pre-commit run --all-files` → exit 0.

## Test strategy

Existing CircuitBuilder integration tests + SVG snapshot tests cover phase4 through the public API — the regression net.

For the new helpers, add `tests/unit/electrical/test_phase4_helpers.py`:

- `_get_endpoint_symbols`: parametrized table covering (a) both indices valid and both have symbol, (b) `idx_a` out-of-bounds, (c) `idx_b` out-of-bounds, (d) `comp_a` has no `"symbol"`, (e) `comp_b` has no `"symbol"`. Cases (b)-(e) return `None`; case (a) returns `(sym_a, sym_b)`.
- `_render_manual_connections`: 1-2 cases — single direct line; line with vertical-detected wire label.
- `_render_matching_connections`: 1 case — two components with overlapping pins, with and without `pin_filter`.
- `_render_planned_chain_connections`: 1-2 cases — chain connection with no labels; chain with `wire_labels_above`.

## Out of scope

- Changing `_phase4_render_graphics`'s signature.
- Touching `_phase[123]_*`.
- Touching `builder.py`.
- Migrating the inter-phase contract from `dict` to `RealizedComponent` (post-C1d wave).
- Threshold drops on any complexity rule (those are C1e's job).
- Adding helpers to any `__all__`.

## Notes for the implementer

- **`has_per_connection_labels`** stays in the orchestrator (it's a single `bool` computed once, used only by `_render_planned_chain_connections`). Pass it as an argument.
- **`style = standard_style()`** stays in the orchestrator. Pass it to the helpers that need it (manual + matching; chain uses `draw_wire` which has its own style).
- **`_get_endpoint_symbols` return type**: `tuple[Symbol, Symbol] | None`. This requires `Symbol` to be available at the type-checker level. `Symbol` is already in the file's `TYPE_CHECKING` block (added in C1c) — reuse it.
- **`_render_manual_connections` per-connection wire label logic**: the original has nested ifs:
  ```python
  label = spec.connection_wire_labels.get(conn_idx)
  if label:
      is_vertical = abs(line.start.x - line.end.x) < _WIRE_VERTICAL_THRESHOLD
      if is_vertical:
          pos = calculate_wire_label_position(line.start, line.end)
          c.elements.append(create_wire_label_text(label, pos))
  ```
  Combine the `if label and is_vertical:` (or use early continue) to flatten. Pin the original behaviour: labels only render on vertical lines (NOT horizontal).
- **`_render_planned_chain_connections` filter**: only processes `pc.kind == "chain"` entries. Other kinds are skipped via `continue`. Preserve.
- **No noqa workarounds for complexity rules.**
- **Tier-3 docstrings**: at most one-line WHY each. No Args/Returns/Raises blocks.
- **deal annotations**: 
  - `_get_endpoint_symbols`: `@deal.pure` (only reads, returns).
  - The 3 render helpers: undecorated (mutate `c.elements`).
- **Prepare for C1e**: this wave's success unlocks threshold drops in C1e. After C1d ships, the max-complexity peak in src/ should drop from 22 to whatever the next-highest holder is. Likely candidates (from the post-C0 violator list): `electrical/builder.py:build` (18), `add_symbol` (13), `add_spdt` (13), `add_terminal` (12). But those are tier C2 / not in C1's scope — C1e's threshold drop will simply move max-complexity to whatever the new measured peak is, regardless of which function holds it.
