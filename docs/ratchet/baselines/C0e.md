# Wave C0e baseline — `block()` factory: extract pin-side + position helpers

Branch base: `branch1` @ `cec9885` (post-C0d).
Wave branch: `complexity/C0e` in worktree `.worktrees/complexity/C0e`.

## State at start

`docs/ratchet/baseline.toml [complexity]`: max_complexity = 22, max_args = 16, max_branches = 22, max_statements = 69, max_returns = 0.
`pyproject.toml`: max-complexity = 22, max-returns = 6.
`pytest.min_passing = 1920` (floor; actual 1938).

After C0d, 12 C901 violators remain in `src/`. C0e targets ONE of them:

- `src/schematika/electrical/symbols/blocks.py:227` `block` (complexity 15) — generic function-box symbol factory.

The other 11 (svg_path's match dispatch, electrical/builder.py's add_*/build chain, builder_phases.py's _phaseN_*) are tier-C1 territory.

## Wave scope

Single function refactor. Spec calls for 4 helper extractions; `block` becomes a thin orchestrator.

### `block()` shape today (lines 227-414, ~190 lines)

Function signature is fine — keep as-is. Behaviour: builds a `Symbol` containing:
- A rectangle (the box itself)
- Top pin lines + ports + labels (loop over `top_pins`)
- Bottom pin lines + ports + labels (loop over `bottom_pins`, almost identical to top)
- Optional component-tag label
- Numeric alias ports ("1", "3", ... for top; "2", "4", ... for bottom)

Complexity drivers (15 total):
- 2 `if x is None:` defaults for `top_pins`, `bottom_pins`
- 2 `if positions is not None and len(...) != ...: raise CircuitValidationError(...)` validations
- 2 `if explicit is not None: ... else: ...` branches for top/bottom x-positions
- 1 `if all_positions:` branch for box-width computation
- 2 `for ... in pins:` loops (each counts +1)
- 2 `for ... in alias:` loops with `if std_id not in ports:` checks
- 1 `if label:` for component tag

### Helpers to extract (all `@deal.pure` — `blocks.py` is in `electrical/symbols/`, not `core/`, but `block()` is already pure-by-construction; helpers should preserve that)

NOTE: `electrical/symbols/blocks.py` is NOT in `core/` so `@deal.pure` is recommended but not enforced by fp_purity_gate. Apply it on the helpers because they ARE pure (no I/O, no globals); leave `block()` itself with whatever decoration it has now (read the file to check — most factories don't carry `@deal.pure`).

1. **`_compute_pin_x_positions(pins, explicit, spacing) -> list[float]`** — collapses the 2 explicit-vs-uniform branches into a single helper. Used twice (top + bottom). Drops 4 branches from `block()`.

```python
def _compute_pin_x_positions(
    pins: tuple[str, ...],
    explicit: tuple[float, ...] | None,
    spacing: float,
) -> list[float]:
    if explicit is not None:
        return list(explicit)
    return [i * spacing for i in range(len(pins))]
```

2. **`_validate_pin_positions(positions, pins, name) -> None`** — collapses the 2 raise-validation branches.

```python
def _validate_pin_positions(
    positions: tuple[float, ...] | None,
    pins: tuple[str, ...],
    name: str,
) -> None:
    if positions is not None and len(positions) != len(pins):
        msg = f"{name}_pin_positions length ({len(positions)}) must match {name}_pins length ({len(pins)})"
        raise CircuitValidationError(msg)
```

3. **`_make_pin_side(pins, x_positions, side, box_height, pin_length, style) -> tuple[list[Element], dict[str, Port]]`** — unifies the two near-identical pin-side construction loops. `side` is `Literal["top", "bottom"]`. The differences are:
   - Top: pin line from `(px, 0)` to `(px, -pin_length)`; port at `(px, -pin_length)` with direction `Vector(0, -1)`; text `text_y = -pin_length / 2`.
   - Bottom: pin line from `(px, box_height)` to `(px, box_height + pin_length)`; port at `(px, box_height + pin_length)` with direction `Vector(0, 1)`; text `text_y = box_height + pin_length`.

   Use `match side` or a small `(line_start_y, line_end_y, port_y, port_dir, text_y)` tuple computed up-front per side.

4. **`_make_alias_ports(pins, ports, parity_offset) -> dict[str, Port]`** — unifies the two `for i, pin_label in enumerate(pins): std_id = str(i * 2 + offset); if std_id not in ports: ports[std_id] = replace(ports[pin_label], id=std_id)` loops. `parity_offset = 1` for top (odd), `2` for bottom (even).

```python
def _make_alias_ports(
    pins: tuple[str, ...],
    existing_ports: dict[str, Port],
    parity_offset: int,
) -> dict[str, Port]:
    aliases: dict[str, Port] = {}
    for i, pin_label in enumerate(pins):
        std_id = str(i * 2 + parity_offset)
        if std_id not in existing_ports and std_id not in aliases:
            aliases[std_id] = replace(existing_ports[pin_label], id=std_id)
    return aliases
```

(Returns just the new aliases; caller does `ports.update(aliases)`. Or take `ports` and mutate — pick whichever is cleaner. The mutation form is fine since `ports` is a fresh local dict in `block()`, not an argument.)

### After extractions, `block()` should look approximately like

```python
def block(
    label: str = "",
    top_pins: tuple[str, ...] | None = None,
    bottom_pins: tuple[str, ...] | None = None,
    pin_spacing: float = DEFAULT_POLE_SPACING,
    top_pin_positions: tuple[float, ...] | None = None,
    bottom_pin_positions: tuple[float, ...] | None = None,
) -> Symbol:
    """<existing tier-1 docstring with Examples — keep unchanged>"""
    top_pins = top_pins or ()
    bottom_pins = bottom_pins or ()
    _validate_pin_positions(top_pin_positions, top_pins, "top")
    _validate_pin_positions(bottom_pin_positions, bottom_pins, "bottom")

    style = standard_style()
    box_height = 4 * GRID_SIZE
    pin_length = GRID_SIZE / 2
    padding = GRID_SIZE / 2

    top_x = _compute_pin_x_positions(top_pins, top_pin_positions, pin_spacing)
    bottom_x = _compute_pin_x_positions(bottom_pins, bottom_pin_positions, pin_spacing)
    all_x = top_x + bottom_x
    if all_x:
        box_width = (max(all_x) - min(all_x)) + 2 * padding
        center_x = (min(all_x) + max(all_x)) / 2
    else:
        box_width = 2 * padding
        center_x = 0
    center_y = box_height / 2

    elements: list[Element] = [box(Point(center_x, center_y), box_width, box_height, filled=False)]
    ports: dict[str, Port] = {}

    top_elems, top_ports = _make_pin_side(top_pins, top_x, "top", box_height, pin_length, style)
    elements.extend(top_elems)
    ports.update(top_ports)

    bottom_elems, bottom_ports = _make_pin_side(bottom_pins, bottom_x, "bottom", box_height, pin_length, style)
    elements.extend(bottom_elems)
    ports.update(bottom_ports)

    if label:
        elements.append(standard_text(label, Point(center_x - box_width / 2, center_y)))

    ports.update(_make_alias_ports(top_pins, ports, parity_offset=1))
    ports.update(_make_alias_ports(bottom_pins, ports, parity_offset=2))

    return Symbol(elements, ports, label=label)
```

Target: `block` complexity 15 → ≤ 8.

## Done condition

- `block` no longer in `uv run ruff check src --select C901 --config 'lint.mccabe.max-complexity=10' --no-fix` output.
- The 4 new helpers exist in `src/schematika/electrical/symbols/blocks.py` (or a new `blocks_helpers.py` if the file is getting long — pick whichever; same-file is fine).
- All existing tests in `tests/unit/test_symbols.py` and `tests/unit/symbols/test_electrical_geometry.py` pass UNCHANGED. The doctest example `>>> "IN" in sym.ports and "OUT" in sym.ports` still returns `True`.
- The existing tier-1 docstring on `block()` (Args/Returns/Raises/Examples blocks) STAYS AS-IS — `block` is in `electrical.symbols.__all__` so it's tier-1; full Google-style docstring with Examples is required by `api_docs_audit.py`.
- The 4 new helpers are tier-3 (private, `_`-prefixed, not in any `__all__`) — at most one-line WHY docstrings. Most should have NO docstring at all.
- `uv run pytest -q --continue-on-collection-errors` → ≥ 1938.
- `uv run python scripts/api_style_gate.py --strict` → 0 violations.
- `uv run python scripts/api_docs_audit.py --strict` → 0 gaps (verify `block`'s docstring still has Examples — the audit will catch any accidental drop).
- `uv run pre-commit run --all-files` → exit 0.
- `uv run python scripts/ratchet_check.py` → exit 0.

## Test strategy

Existing tests cover the function via `>>> "IN" in sym.ports` doctest and integration tests in `test_symbols.py` and `test_electrical_geometry.py`. After refactoring, run:

```bash
cd .worktrees/complexity/C0e
uv run pytest tests/unit/test_symbols.py tests/unit/symbols/test_electrical_geometry.py -q --no-cov
```

All must pass. If they do, no new tests strictly required for this wave.

OPTIONAL (improves the kill-rate floor on `blocks.py` for the post-C5 mutmut comparison): add a small parametrized characterisation test for `_compute_pin_x_positions`:

```python
@pytest.mark.parametrize("pins,explicit,spacing,expected", [
    ((), None, 5.0, []),
    (("A",), None, 5.0, [0.0]),
    (("A", "B"), None, 5.0, [0.0, 5.0]),
    (("A", "B"), (1.0, 7.0), 5.0, [1.0, 7.0]),
])
def test_compute_pin_x_positions(pins, explicit, spacing, expected):
    assert _compute_pin_x_positions(pins, explicit, spacing) == expected
```

And one for `_validate_pin_positions` raising on length mismatch:

```python
def test_validate_pin_positions_raises_on_length_mismatch():
    with pytest.raises(CircuitValidationError, match="top_pin_positions length"):
        _validate_pin_positions((1.0,), ("A", "B"), "top")
```

Adding these is encouraged; not required.

## Out of scope

- Touching any function in `blocks.py` other than `block()`.
- Adding new public API symbols. Helpers stay private (`_`-prefixed, not in `__all__`).
- Touching the existing `block()` docstring.
- Threshold drops (no max-complexity drop in this wave; deferred to post-C1).
- The other 11 C901 violators (those are tier C1).
- Updating `docs/API_STYLE.md`.

## Notes for the implementer

- `block` is in `src/schematika/electrical/symbols/__init__.py`'s `__all__` (verify by `grep -n "^block" src/schematika/electrical/symbols/__init__.py` or similar). Therefore tier-1 — its existing docstring with Args/Returns/Raises/Examples is REQUIRED. Don't trim it.
- Helpers are tier-3 (private, not exported) — keep their docstrings absent or one-line WHY.
- The `Literal["top", "bottom"]` for `_make_pin_side` is a fine Python 3.14 type hint (or `typing.Literal`).
- If you find that extracting all 4 helpers doesn't drop complexity below 11, focus on the loops first (helpers 3 and 4) — they have the highest leverage. The validation and position-compute helpers (1 and 2) save 2-4 branches each.
- `replace(ports[pin_label], id=std_id)` — `replace` is `dataclasses.replace` (already imported). Don't introduce new imports if not needed.
- The CircuitValidationError import is already there at the top of `blocks.py` — don't re-import.
