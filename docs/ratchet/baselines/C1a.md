# Wave C1a baseline — `_phase1_tag_and_state` complexity 15 → ≤ 10

Branch base: `branch1` @ `48711bc` (post-C1-pre).
Wave branch: `complexity/C1a` in worktree `.worktrees/complexity/C1a`.

## State at start

`docs/ratchet/baseline.toml`:
```
[complexity]
max_complexity   = 22  ← held by _phase4 (drops in C1d)
max_args         = 16
max_branches     = 22
max_statements   = 69  ← held by _phase2 (drops in C1b)
max_returns      =  0
[pytest]
min_passing               = 1957
min_coverage_percent      =   90
min_core_coverage_percent =   94
```

C1-pre shipped `RealizedComponent` + `realized_from_dict` / `realized_to_dict` in `electrical/builder_models.py`.

`_phase1_tag_and_state` at `src/schematika/electrical/builder_phases.py:36` is **complexity 15**. It does three things in one function:
1. Per-component-kind tag/pin resolution (terminal vs symbol/reference; multi-source resolution chain).
2. Y-position calculation (3-way: placed_right_of / placed_above|below_of / default-stack-advance).
3. Dict assembly + append.

## Wave scope

**Internal complexity reduction only.** No change to the public function's signature, return type, or behaviour. Continue to return `list[dict[str, Any]]` — the inter-phase contract stays dict-based until a later "C1-post" / C2 wave migrates everything at once.

But: the new helpers should TAKE/RETURN typed primitives (or `RealizedComponent`), so the type information flows. Use `realized_to_dict(rc)` at the assembly boundary to keep the existing dict return.

### Extract these helpers in `electrical/builder_phases.py` (above `_phase1_tag_and_state`)

1. **`_resolve_terminal_id(component_spec, terminal_maps, spec_terminal_map) -> str | int`** — handles the 2-priority lookup chain: runtime `terminal_maps[lname]` → spec `terminal_map[lname]` → fallback to `component_spec.kwargs["tm_id"]`. Returns the resolved id. Drops 2 branches from `_phase1`.

2. **`_resolve_terminal_pins(state, component_spec, tid, lname, terminal_reuse_generators) -> tuple[GenerationState, list[str]]`** — handles the 3-source pin chain: explicit `component_spec.pins` → `terminal_reuse_generators` lookup (str(tid) or lname keyed) → `next_terminal_pins(...)`. Returns `(updated_state, pins)`. Drops 3-4 branches.

3. **`_track_pin_accumulator(pin_accumulator, lname, tid, pins) -> None`** — handles the `if pin_accumulator is not None: ...` mutation block. Mutates `pin_accumulator` in place (it's the caller's dict). Drops 2 branches. NOT `@deal.pure` (it mutates its argument).

4. **`_resolve_symbol_or_reference_tag(state, component_spec, tag_generators, instance_tags) -> tuple[GenerationState, str]`** — validates `component_spec.tag_prefix is not None` (raises `CircuitValidationError`), generates tag via `tag_generators[prefix]` or `next_tag(state, prefix)`, mutates `instance_tags`. Returns `(updated_state, tag)`. Drops 2 branches.

5. **`_compute_component_y(component_spec, current_y, realized_components, layout_spacing) -> tuple[float, float]`** — handles the 3-way placement branch. Returns `(component_y, new_current_y)` where `new_current_y == current_y` for non-default placement (no stack advance). Drops 2 branches. NOTE: this still takes `realized_components: list[dict[str, Any]]` because phase1 hasn't migrated the inter-phase contract yet — accept the `Any` here for now.

After these 5 extractions, `_phase1_tag_and_state` becomes roughly:

```python
def _phase1_tag_and_state(
    state: GenerationState,
    y: float,
    spec: CircuitSpec,
    tag_generators: dict[str, Callable] | None,
    terminal_maps: dict[str, Any] | None,
    terminal_reuse_generators: dict[str, Callable] | None,
    pin_accumulator: dict[str, list[str]] | None,
) -> tuple[GenerationState, list[dict[str, Any]], dict[str, str]]:
    """Phase 1: assign tags/pins, compute initial Y; populates `realized_components`."""
    instance_tags: dict[str, str] = {}
    realized_components: list[dict[str, Any]] = []
    current_y = y

    for component_spec in spec.components:
        if component_spec.kind == "terminal":
            lname = component_spec.kwargs.get("logical_name")
            tid = _resolve_terminal_id(component_spec, terminal_maps, spec.terminal_map)
            state, pins = _resolve_terminal_pins(
                state, component_spec, tid, lname, terminal_reuse_generators,
            )
            _track_pin_accumulator(pin_accumulator, lname, tid, pins)
            tag = str(tid)
        elif component_spec.kind in ("symbol", "reference"):
            state, tag = _resolve_symbol_or_reference_tag(
                state, component_spec, tag_generators, instance_tags,
            )
            pins = list(component_spec.pins) if component_spec.pins else []
        else:
            tag = None
            pins = []

        comp_y, current_y = _compute_component_y(
            component_spec, current_y, realized_components, spec.layout.symbol_spacing,
        )

        rc = RealizedComponent(spec=component_spec, tag=tag or "", pins=tuple(pins), y=comp_y)
        realized_components.append(realized_to_dict(rc))

    return state, realized_components, instance_tags
```

Target: `_phase1_tag_and_state` complexity 15 → ≤ 8. Each helper should be < 10.

The `RealizedComponent` construction + `realized_to_dict` at the append site means `RealizedComponent` is now actively used (vulture won't complain).

## Done condition

- `_phase1_tag_and_state` no longer in `uv run ruff check src/schematika/electrical/builder_phases.py --select C901 --config 'lint.mccabe.max-complexity=10' --no-fix`.
- The 5 new helpers also pass C901 at threshold 10 (each individually).
- `_phase1_tag_and_state` return type EXACTLY unchanged: `tuple[GenerationState, list[dict[str, Any]], dict[str, str]]`.
- `_phase[234]_*` functions UNCHANGED (verify via `git diff branch1..HEAD -- src/schematika/electrical/builder_phases.py | grep "^@@" | head -10`).
- All existing CircuitBuilder integration tests pass UNCHANGED. The behavioural net for phase1 is the snapshot tests + builder integration tests — verify with `cd .worktrees/complexity/C1a && uv run pytest tests/unit/test_builder.py tests/unit/electrical/ -q --no-cov 2>&1 | tail -10`.
- `uv run pytest -q --continue-on-collection-errors` → ≥ 1957 (the new floor).
- `uv run pytest --cov=src/schematika/core` core TOTAL ≥ 94%.
- `uv run python scripts/api_style_gate.py --strict` → 0 violations.
- `uv run python scripts/api_docs_audit.py --strict` → 0 gaps.
- `uv run python scripts/fp_purity_gate.py` → 0 violations.
- `uv run pre-commit run --all-files` → exit 0.
- `uv run python scripts/ratchet_check.py` → exit 0; complexity peaks UNCHANGED (since other phases hold them).

## Test strategy

Existing CircuitBuilder integration tests (`tests/unit/test_builder.py` and others) exercise phase1 through the public API. After refactor, all must pass UNCHANGED. That's the regression net.

For the new helpers (which take primitive args, are pure or near-pure), add minimal characterisation tests in `tests/unit/electrical/test_phase1_helpers.py`:

- `test_resolve_terminal_id` — parametrize over the 3 lookup priorities (runtime override, spec map, fallback to kwargs).
- `test_resolve_terminal_pins` — parametrize over the 3 sources (explicit, reuse generator, fresh allocation). For the reuse-generator case, pass a `lambda state, poles: (state, ("X1", "X2"))`-style fake.
- `test_compute_component_y_default_stack_advance` — passes through layout spacing, advances current_y.
- `test_compute_component_y_placed_right_of` — uses ref component's y, no stack advance.
- `test_compute_component_y_placed_above_or_below` — uses current_y placeholder, no stack advance.
- `test_resolve_symbol_or_reference_tag_raises_without_prefix` — `pytest.raises(CircuitValidationError)`.

Don't over-test the existing behaviour — that's covered by integration tests. These characterisation tests pin the new helpers' contracts so future refactors notice if a helper changes.

## Out of scope

- Changing `_phase1_tag_and_state`'s signature or return type.
- Touching `_phase[234]_*` or any other function in `builder_phases.py`.
- Touching `builder.py` (`CircuitBuilder.build` and `add_*` methods — tier C2).
- Migrating the inter-phase contract from `dict` to `RealizedComponent` (deferred; that's a post-C1d wave or C2 territory).
- Threshold drops on any complexity rule (deferred to C1e).
- Updating `docs/API_STYLE.md`.
- Adding helpers to any `__all__`.

## Notes for the implementer

- All helpers go in `electrical/builder_phases.py` ABOVE `_phase1_tag_and_state` so they're defined before use.
- `electrical/builder_phases.py` is NOT in `core/` — `@deal.pure` is recommended-not-required. Apply it on the helpers that ARE pure (`_resolve_terminal_id`, `_compute_component_y`). For helpers that mutate (e.g. `_track_pin_accumulator`) or raise (`_resolve_symbol_or_reference_tag`), use the appropriate deal annotation:
  - Mutates argument: skip `@deal.pure` (or use `@deal.has(<marker>)` if there's an established repo convention — check existing code).
  - Raises: use `@deal.raises(CircuitValidationError)` (matches the C0e precedent for `_validate_pin_positions`).
- Tier-3 docstrings: the 5 new helpers are private, not in any `__all__` — at most a one-line WHY each, OR no docstring.
- The use of `RealizedComponent` + `realized_to_dict(rc)` at the append site is intentional: it exercises the C1-pre symbols (vulture stays quiet) AND ensures the data flowing into the dict is well-typed at construction.
- `tag = tag or ""` in the assembly: the original code allowed `tag = None` (the `else` branch with no kind match). The `RealizedComponent.tag: str` field doesn't allow None. Coerce to empty string to preserve the original behaviour. If this feels wrong, add `tag: str | None = None` to RealizedComponent — but that's a C1-pre amendment, not a C1a change. Prefer `tag = tag or ""` for now.
- `next_terminal_pins` returns `(state, pin_tuple)`. Preserve that signature in `_resolve_terminal_pins`.
- The original code does `lname = component_spec.kwargs.get("logical_name")` TWICE in the terminal branch (lines 56 and 66). The duplicate is unnecessary — collapse to one assignment in the helper.
