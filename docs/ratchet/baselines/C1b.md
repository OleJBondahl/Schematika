# Wave C1b baseline — `_phase2_register_connections` complexity 21 → ≤ 6

Branch base: `branch1` @ `73ac017` (post-C1a).
Wave branch: `complexity/C1b` in worktree `.worktrees/complexity/C1b`.

## State at start

`docs/ratchet/baseline.toml`:
```
[complexity]
max_complexity   = 22
max_args         = 16
max_branches     = 22  ← _phase2 holds it (21 branches)
max_statements   = 69  ← _phase2 holds it (69 statements)
max_returns      =  0
[pytest]
min_passing               = 1957  ← actual 1970 post-C1a; bump to 1970 separately
```

`_phase2_register_connections` at `src/schematika/electrical/builder_phases.py:199` is **complexity 21**, the largest single function in the codebase. It does TWO loops (linear + manual) that each dispatch on a 5-arm `(component_from.kind, component_to.kind)` matrix — total 10 dispatch branches. Heavy duplication between the loops.

## Wave scope

**Internal complexity reduction only.** No change to public signature, return type, or behaviour. Inter-phase contract stays `list[dict[str, Any]]`.

The big win: a **single `_register_connection_pair` helper** that handles the 5-arm kind-dispatch, used by both linear and manual loops. Eliminates ~10 branches from `_phase2`.

### Extract these helpers in `electrical/builder_phases.py` (above `_phase2_register_connections`)

1. **`_should_auto_connect(curr, next_comp) -> bool`** — predicate for the linear loop's skip conditions. Returns True iff `curr["spec"].connect_to_next is True` AND none of `next_comp["spec"].placed_right_of/above_of/below_of` is set. Drops 4 branches from `_phase2`. `@deal.pure`.

2. **`_register_connection_pair(state, comp_from, pin_from, side_from, p_from, comp_to, pin_to, side_to, p_to) -> tuple[GenerationState, tuple[str, str, str, str] | None]`** — the centerpiece. Handles the 5-arm `(kind_from, kind_to)` dispatch:
   - `terminal × symbol|reference`: log connection from comp_from's registry pin; side defaults to `"bottom"` if `side_from is None`.
   - `symbol|reference × terminal`: log connection from comp_to's registry pin; side defaults to `"top"` if `side_to is None`.
   - `reference × symbol`: if `comp_from["pins"]` is non-empty, use `comp_from["pins"][0]`; else allocate via `next_terminal_pins(state, comp_from["tag"], 1)`. Then log. Side defaults to `"bottom"` if `side_from is None`.
   - `symbol × reference`: mirror of the above for `comp_to`. Side defaults to `"top"` if `side_to is None`.
   - `symbol × symbol`: just emit the wire tuple, no `log_connection` call.
   - Other / unmatched: return `(state, None)` (no-op — preserves the original code's silent fall-through).
   
   Returns `(updated_state, wire_tuple_or_None)`. The wire tuple convention is `(tag_from, pin_from_resolved, tag_to, pin_to_resolved)` — the resolved pins might be the inputs OR newly-allocated registry pins, depending on the arm.

   **Important about the linear-vs-manual asymmetry**: read the original code carefully. In the LINEAR loop, the `reference × symbol` arm ALWAYS allocates `next_terminal_pins` (ignores `comp_from["pins"]`). In the MANUAL loop, it checks `comp_a["pins"]` first. **Reconcile**: the manual-loop behaviour is the "honour user-supplied pins" intent; the linear-loop behaviour is "always alloc fresh." Use the manual-loop's `if comp_from["pins"]: use; else: alloc` pattern in the helper — it's a strict superset. The linear loop's call site sets `comp["pins"]` to whatever `_phase1` resolved, so when the helper sees a non-empty `comp["pins"]`, it'll honour them. **Test that the linear loop's behaviour is preserved by running the existing CircuitBuilder integration tests.** If a test fails, the linear-vs-manual difference is load-bearing and the helper needs a flag (`prefer_existing_ref_pins: bool = True`) — but try the unified version first.

   `@deal.pure` is incorrect here (the function calls `log_connection` and `next_terminal_pins`, both of which take and return `state`). The function is pure-by-state-passing — no side effects on globals or its arguments — but `@deal.pure` strictly requires no calls to impure functions. Leave it undecorated, or use `@deal.has(<marker>)` if there's an established repo precedent. Check: `grep -rn "@deal.has" src/schematika/electrical/`. If nothing else uses it, leave undecorated.

3. **`_register_linear_connections(state, realized_components) -> tuple[GenerationState, list[tuple[str, str, str, str]]]`** — encapsulates the entire linear-connection loop. Uses `_should_auto_connect` + `_register_connection_pair`. Returns `(updated_state, wires)`.

4. **`_register_manual_connections(state, realized_components, manual_connections) -> tuple[GenerationState, list[tuple[str, str, str, str]]]`** — encapsulates the manual-connection loop. Uses `_register_connection_pair`.

5. **`_phase2_register_connections` becomes**:

```python
def _phase2_register_connections(
    state: GenerationState,
    realized_components: list[dict[str, Any]],
    spec: CircuitSpec,
) -> tuple[GenerationState, list[tuple[str, str, str, str]]]:
    """Phase 2: register linear + manual connections in the registry."""
    state, linear_wires = _register_linear_connections(state, realized_components)
    state, manual_wires = _register_manual_connections(
        state, realized_components, spec.manual_connections,
    )
    return state, linear_wires + manual_wires
```

Target: `_phase2_register_connections` complexity 21 → ≤ 5. Each helper individually < 10 (the 5-arm `_register_connection_pair` will be ~5-7).

## Done condition

- `_phase2_register_connections` no longer in `uv run ruff check src/schematika/electrical/builder_phases.py --select C901 --config 'lint.mccabe.max-complexity=10' --no-fix`.
- The 4 new helpers also pass C901 at threshold 10 (each individually).
- `_phase2_register_connections` signature + return type EXACTLY unchanged.
- `_phase[134]_*` UNCHANGED (verify with `git diff branch1..HEAD -- src/schematika/electrical/builder_phases.py | grep "^@@" | head -10` — only phase2-related hunks should appear).
- All existing CircuitBuilder integration tests pass UNCHANGED.
- `uv run pytest -q --continue-on-collection-errors` → ≥ 1970 (the new floor — bump separately if not already).
- `uv run pytest --cov=src/schematika/core` core TOTAL ≥ 94%.
- `uv run python scripts/api_style_gate.py --strict` → 0 violations.
- `uv run python scripts/api_docs_audit.py --strict` → 0 gaps.
- `uv run python scripts/fp_purity_gate.py` → 0 violations.
- `uv run pre-commit run --all-files` → exit 0.
- `uv run python scripts/ratchet_check.py` → exit 0.

## Test strategy

Existing CircuitBuilder integration tests (`tests/unit/test_builder.py` and `tests/unit/electrical/`) exercise `_phase2_register_connections` through the public API — those are the regression net.

For the new `_register_connection_pair` helper (the centerpiece), add a dedicated parametrized test in `tests/unit/electrical/test_phase2_helpers.py`:

- Parametrized table with one row per (kind_from, kind_to) arm: `terminal-symbol`, `terminal-reference`, `symbol-terminal`, `reference-terminal`, `reference-symbol` (with explicit pins), `reference-symbol` (without explicit pins, forces alloc), `symbol-reference` (with), `symbol-reference` (without), `symbol-symbol`, `terminal-terminal` (no-op). Assert the returned wire tuple matches expectation; assert `log_connection` was called or NOT called as appropriate (use `monkeypatch` to spy on `log_connection` if needed, OR use a fake `state` and inspect post-call state).

For `_should_auto_connect`: parametrized table over the 4 conditions (connect_to_next True/False × placed_*_of None/set).

For `_register_linear_connections` and `_register_manual_connections`: small smoke test with a 2-component circuit. The integration tests already cover these paths via the public API; smoke tests just confirm the helpers can be invoked standalone.

## Out of scope

- Changing `_phase2_register_connections`'s signature or return type.
- Touching `_phase[134]_*` or any function outside phase2 + new helpers.
- Touching `builder.py`.
- Migrating the inter-phase contract from `dict` to `RealizedComponent` (deferred to post-C1d).
- Threshold drops on any complexity rule.
- Adding helpers to any `__all__`.
- Refactoring `_resolve_pin` or `_resolve_registry_pin` (those are existing utilities).

## Notes for the implementer

- **Manual connection skip condition**: the original manual loop has `if idx_a >= len(realized_components) or idx_b >= len(realized_components): continue`. Preserve this in `_register_manual_connections` (it's defensive against malformed input).
- **`comp["pins"]` may be `None` or a list**. The check `if comp["pins"]:` handles both (None and empty list both falsy). Match the original.
- **`_register_connection_pair`'s `pin_from`/`pin_to` parameters**: these are PRE-RESOLVED via `_resolve_pin` in the caller. The helper does NOT call `_resolve_pin` itself. The asymmetry between linear (`is_input=False/True` based on position) and manual (`is_input=(side_X == "top")`) is preserved in the call site, NOT in the helper.
- **Wire tuple format**: the original linear loop and manual loop both produce 4-tuples like `(tag_a, pin_a_resolved, tag_b, pin_b_resolved)`. The helper must return this format consistently. The resolved pin names depend on the arm — sometimes they're the input `pin_from`/`pin_to`, sometimes they're a freshly-allocated `reg_pin`. Read the original code to understand which arm uses which.
- **deal annotation**: as noted in the spec for `_register_connection_pair` — leave undecorated unless there's an established `@deal.has(...)` precedent.
- **Tier-3 docstrings**: at most one-line WHY each. No Args/Returns/Raises blocks.
- **No noqa for complexity rules**.

## Bump baseline.toml `min_passing` 1957 → 1970 separately

The post-C1a state has 1970 tests. baseline.toml still says 1957. This is a missed floor bump. **The C1b implementer should NOT update baseline.toml** — that's separate housekeeping the controller will do between waves. Just make sure `pytest` reports ≥ 1970 (with new tests added in this wave, expect 1970 + N).
