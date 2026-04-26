# C2c consumer migration — `add_spdt` bundling

## 1. Summary

`CircuitBuilder.add_spdt` previously accepted 12 keyword/positional-or-keyword
arguments. In C2c these are bundled into three frozen dataclasses imported from
`schematika.core.options`:

- **`SpdtConfig`** (new) — `poles`, `pins`, `inverted`, `device`,
  `wire_labels_above`.
- **`PlacementOptions`** (from C2a) — `relative_to`, `position`, `spacing`,
  `x_offset`.
- **`ConnectionOptions`** (from C2a) — `connect_from_previous`
  (`connect_to_next` is **ignored** — see note below).

Key removals and renames:

- `tag_prefix` **stays as a positional-only arg** with default `"K"` — do not
  move it into `SpdtConfig`. `b.add_spdt()` and `b.add_spdt("K")` still work.
- `y_increment` is **removed** — use `PlacementOptions.spacing` instead.
- `pins` and `wire_labels_above` accept only `tuple[str, ...] | None` (not
  `list`) — convert any list literals to tuples.
- `connect_from_previous` **defaults to `False`** for `add_spdt` (unlike
  `add_terminal`/`add_symbol` which default to `True`). To preserve old
  behaviour, omit `connection=` entirely. To opt in, pass
  `connection=ConnectionOptions(connect_from_previous=True)`.

**Special note — `connect_to_next` is always `False` for `add_spdt`.**
Even if you pass `connection=ConnectionOptions(connect_to_next=True)`, the
method silently overrides it to `False` internally. SPDTs always branch the
chain; they never pass wiring forward. This matches the pre-C2c behaviour.

This is a single hard breaking commit. There is no compatibility shim.

## 2. Old → new mapping table

| Old kwarg | New location |
|-----------|--------------|
| `tag_prefix` | (positional, unchanged — still defaults to `"K"`) |
| `poles` | `config=SpdtConfig(poles=...)` |
| `pins` | `config=SpdtConfig(pins=...)` (must be `tuple`, not `list`) |
| `inverted` | `config=SpdtConfig(inverted=...)` |
| `device` | `config=SpdtConfig(device=...)` |
| `wire_labels_above` | `config=SpdtConfig(wire_labels_above=...)` (must be `tuple`) |
| `relative_to` | `placement=PlacementOptions(relative_to=...)` |
| `position` | `placement=PlacementOptions(position=...)` |
| `spacing` | `placement=PlacementOptions(spacing=...)` |
| `x_offset` | `placement=PlacementOptions(x_offset=...)` |
| `y_increment` | **REMOVED.** Use `placement=PlacementOptions(spacing=...)`. |
| `connect_from_previous` | `connection=ConnectionOptions(connect_from_previous=...)`. **Note**: `add_spdt` defaults `connect_from_previous` to `False` (different from `add_terminal`/`add_symbol`). Omit `connection=` to preserve the old default. |

## 3. Call-site index (`../auxillary_cabinet_v3/src/circuits/`)

### `fan_controll.py`

**Before:**
```python
spdt = contact_builder.add_spdt(
    "K",
    inverted=True,
    connect_from_previous=True,
    device=Devices.RELAY_FAN,
)
```
**After:**
```python
spdt = contact_builder.add_spdt(
    "K",
    config=SpdtConfig(inverted=True, device=Devices.RELAY_FAN),
    connection=ConnectionOptions(connect_from_previous=True),
)
```

### `power_switching.py`

**Before:**
```python
spdt = changeover.add_spdt(tag_prefix="K", poles=4)
```
**After:**
```python
spdt = changeover.add_spdt("K", config=SpdtConfig(poles=4))
```

### `pump_controll.py`

**Before:**
```python
spdt = b.add_spdt(
    tag_prefix="K",
    poles=1,
    pins=pins,
    inverted=True,
    connect_from_previous=True,
    x_offset=-GRID_SIZE / 2,
    device=Devices.RELAY_24V_4x21,
    wire_labels_above=[WireLabels.WH_0_5],
)
```
**After:**
```python
spdt = b.add_spdt(
    "K",
    config=SpdtConfig(
        poles=1,
        pins=pins,
        inverted=True,
        device=Devices.RELAY_24V_4x21,
        wire_labels_above=(WireLabels.WH_0_5,),
    ),
    placement=PlacementOptions(x_offset=-GRID_SIZE / 2),
    connection=ConnectionOptions(connect_from_previous=True),
)
```

Note: `wire_labels_above` was a `list` — it must become a `tuple`.

## 4. What to test after migrating

- `b.add_spdt()` (no args) still works — single-pole, tag `"K"`, no wiring.
- `b.add_spdt("K", config=SpdtConfig(poles=2))` produces a 2-pole SPDT.
- Omitting `connection=` preserves `connect_from_previous=False` (the old
  SPDT default) — no phantom wires from previous chain component.
- `connection=ConnectionOptions(connect_from_previous=True)` wires the chain in
  as before.
- `connect_to_next=True` in the bundle has no effect — confirm no forward wire
  is emitted.

## 5. Breakage note

All call sites with any of the removed/renamed kwargs will raise `TypeError` at
call time. There is no fallback. The `connect_from_previous=False` default
asymmetry is preserved by the new bundled default: omitting `connection=`
produces `ConnectionOptions(connect_from_previous=False, connect_to_next=False)`.
Callers that previously passed `connect_from_previous=True` explicitly must now
pass `connection=ConnectionOptions(connect_from_previous=True)`.
