# Wave C1c baseline — `_phase3_instantiate_symbols` complexity 15 → ≤ 5

Branch base: `branch1` @ `0466f35` (post-C1b).
Wave branch: `complexity/C1c` in worktree `.worktrees/complexity/C1c`.

## State at start

`_phase3_instantiate_symbols` at `src/schematika/electrical/builder_phases.py:355` is **complexity 15**. It does two things in one loop body:

1. **Position computation** — 4-arm dispatch on placement mode (`placed_above_of`, `placed_below_of`, `placed_right_of`, default). The above/below arms duplicate each other nearly verbatim (only the sign of `y_offset` differs).

2. **Symbol creation** — 2-arm dispatch on component kind (`terminal` vs `symbol|reference`):
   - Terminal arm: branches on `poles >= _MULTI_POLE_MIN` to choose `_multi_pole_terminal` vs `_terminal_single_pole`.
   - Symbol/reference arm: distributes pins via `_distribute_pins`, then forwards `poles` if the factory accepts it (uses `inspect.signature` introspection — the only `import inspect` in this file).

Phase 3 also MUTATES the dict items: `rc["y"] = ...` (in placed_above/below arms) and `rc["symbol"] = placed_sym` (at the end). The inter-phase contract stays `list[dict]` for now.

`_phase[124]_*` status (post-C1b):
- `_phase1` already at ≤ 5 (C1a).
- `_phase2` already at 1 (C1b).
- `_phase4` still at complexity 22 (C1d's job).

## Wave scope

**Internal complexity reduction only.** No change to public signature, return type, or behaviour. Inter-phase contract still `list[dict]`. Phase 3 still mutates `rc["y"]` and `rc["symbol"]` in place — that asymmetry with frozen RealizedComponent is intentional and stays until a post-C1d wave migrates the contract.

### Extract these helpers in `electrical/builder_phases.py` (above `_phase3_instantiate_symbols`)

1. **`_compute_above_or_below_position(component_spec, realized_components, layout_spacing) -> tuple[float, float]`** — handles BOTH `placed_above_of` and `placed_below_of` arms (they're structurally identical: lookup ref_rc + ref_sym, find port, compute final_x and y_offset, apply sign). Returns `(final_x, new_y)`. The sign of `y_offset` is `-1` for above, `+1` for below — pick which mode is set. Raises `CircuitValidationError` if the port isn't found. **Use `@deal.raises(CircuitValidationError)`**.

2. **`_compute_placed_right_position(component_spec, realized_components, x) -> float`** — handles the `placed_right_of` arm including the chain-walk via `_get_absolute_x_offset`. Returns `final_x`. **`@deal.pure`**.

3. **`_make_terminal_symbol(tag, rc, component_spec) -> Symbol`** — handles the multi-pole vs single-pole branch in the terminal arm. Returns the constructed `Symbol`. **`@deal.pure`** (calls pure factory functions).

4. **`_make_factory_symbol(tag, rc, component_spec) -> Symbol`** — handles the kwargs distribution + inspect-based poles forwarding in the symbol/reference arm. Returns the constructed `Symbol`. **NOT `@deal.pure`** (uses `inspect.signature` which is ~pure but the call into `component_spec.func(tag, **kwargs)` is opaque). Move the `import inspect` to module top (the local import inside the function is a code smell — pull it out).

After extractions, `_phase3_instantiate_symbols` becomes roughly:

```python
def _phase3_instantiate_symbols(
    c: Circuit,
    realized_components: list[dict[str, Any]],
    spec: CircuitSpec,
    x: float,
) -> None:
    """Phase 3: call symbol factories; mutates `c`; adds `symbol` to each entry."""
    for rc in realized_components:
        component_spec = rc["spec"]
        tag = rc["tag"]

        if component_spec.placed_above_of is not None or component_spec.placed_below_of is not None:
            final_x, rc["y"] = _compute_above_or_below_position(
                component_spec, realized_components, spec.layout.symbol_spacing,
            )
        elif component_spec.placed_right_of is not None:
            final_x = _compute_placed_right_position(
                component_spec, realized_components, x,
            )
        else:
            final_x = x + component_spec.x_offset

        if component_spec.kind == "terminal":
            sym = _make_terminal_symbol(tag, rc, component_spec)
        elif component_spec.kind in ("symbol", "reference"):
            sym = _make_factory_symbol(tag, rc, component_spec)
        else:
            sym = None

        if sym is not None:
            placed_sym = add_symbol(c, sym, final_x, rc["y"])
            rc["symbol"] = placed_sym
```

Target: complexity 15 → ≤ 5. Each helper individually < 10.

## Done condition

- `_phase3_instantiate_symbols` no longer in `uv run ruff check src/schematika/electrical/builder_phases.py --select C901 --config 'lint.mccabe.max-complexity=10' --no-fix`.
- The 4 new helpers also pass C901 at threshold 10.
- `_phase3_instantiate_symbols` signature + return type EXACTLY unchanged (`(c, realized_components, spec, x) -> None`).
- `_phase[124]_*` UNCHANGED.
- All existing CircuitBuilder integration tests pass UNCHANGED (the regression net).
- `uv run pytest -q --continue-on-collection-errors` → ≥ 1994 (the new floor post-C1b).
- `uv run python scripts/ratchet_check.py` → exit 0.
- `uv run pre-commit run --all-files` → exit 0.

## Test strategy

Existing CircuitBuilder integration tests cover phase3 through the public API — that's the regression net.

For the new helpers, add `tests/unit/electrical/test_phase3_helpers.py`:

- `_compute_above_or_below_position`: parametrized over (above, below) × (with y_increment, default y_increment). 4 cases. Plus 1 raise-test for missing port.
- `_compute_placed_right_position`: 2 cases — direct (no chain) and chained (`placed_right_of` chain via `_get_absolute_x_offset`).
- `_make_terminal_symbol`: 2 cases — single-pole vs multi-pole.
- `_make_factory_symbol`: 1-2 cases — with pins (calls `_distribute_pins`), with poles forwarding via inspect.

## Out of scope

- Changing `_phase3_instantiate_symbols`'s signature.
- Touching `_phase[124]_*`.
- Touching `builder.py`.
- Migrating the inter-phase contract from `dict` to `RealizedComponent`.
- Threshold drops on any complexity rule.
- Adding helpers to any `__all__`.

## Notes for the implementer

- **`import inspect` move**: the original code has `import inspect` INSIDE `_phase3_instantiate_symbols` (line 434). Move it to the module top — `inspect` is a stdlib module with no side effects on import, and the local-import pattern is a smell.
- **`_compute_above_or_below_position` sign computation**: 
  ```python
  if component_spec.placed_above_of is not None:
      ref_idx, pin_name = component_spec.placed_above_of
      sign = -1
  else:
      ref_idx, pin_name = component_spec.placed_below_of
      sign = +1
  # ... port lookup, raise if None ...
  y_offset = component_spec.y_increment if component_spec.y_increment is not None else layout_spacing / 2
  return port.position.x + component_spec.x_offset, port.position.y + sign * y_offset
  ```
- **`_make_factory_symbol` inspect logic**: the `inspect.signature(component_spec.func)` + `if "poles" in sig.parameters` check is clean to move into the helper. The helper takes `component_spec.func`, calls `inspect.signature(...)`, and passes `poles` to `kwargs` only if the factory accepts it. Don't simplify away the inspect — it's load-bearing for factories that don't accept `poles`.
- **`_make_terminal_symbol` and `_make_factory_symbol` return `Symbol`** — both are non-None on the success paths. The `else: sym = None` arm in the rewritten phase3 catches unknown kinds (matches the original silent fall-through). Add a `# Unknown kind: preserve fall-through` comment per the C1a precedent.
- **No noqa workarounds for complexity rules.**
- **Tier-3 docstrings**: at most one-line WHY each. No Args/Returns/Raises blocks.
- **deal annotations**: 
  - `_compute_above_or_below_position`: `@deal.raises(CircuitValidationError)`.
  - `_compute_placed_right_position`: `@deal.pure` (only reads, returns).
  - `_make_terminal_symbol`: `@deal.pure` if `_multi_pole_terminal` and `_terminal_single_pole` are pure (they appear to be — check). If they aren't, leave undecorated.
  - `_make_factory_symbol`: leave undecorated (calls `component_spec.func` which is user-supplied).
