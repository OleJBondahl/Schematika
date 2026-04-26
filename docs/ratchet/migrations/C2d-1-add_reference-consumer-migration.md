# C2d-1 consumer migration — `add_reference` bundling

## 1. Summary

`CircuitBuilder.add_reference` previously accepted 9 keyword-only arguments
(plus `**kwargs` for symbol factory passthrough). In C2d-1 the placement and
connection knobs are bundled into two existing frozen dataclasses imported from
`schematika.core.options`:

- **`PlacementOptions`** (from C2a) — `relative_to`, `position`, `spacing`,
  `x_offset`.
- **`ConnectionOptions`** (from C2a) — `connect_from_previous`, `connect_to_next`,
  `wire_label`.

Key removals:

- `y_increment` is **removed entirely** — use `PlacementOptions(spacing=...)`.
- All positional-style placement/connection kwargs (`relative_to=`, `position=`,
  etc.) are now type errors. Only `**factory_kwargs` passthrough args remain flat.

**`**factory_kwargs` is unchanged** — `direction=`, `label_pos=`, and any other
symbol-factory kwargs are still accepted as bare keyword arguments (not bundled).

This is a single hard breaking commit. There is no compatibility shim.

## 2. Old → new mapping table

| Old kwarg | New location |
|-----------|--------------|
| `relative_to` | `placement=PlacementOptions(relative_to=...)` |
| `position` | `placement=PlacementOptions(position=...)` |
| `spacing` | `placement=PlacementOptions(spacing=...)` |
| `x_offset` | `placement=PlacementOptions(x_offset=...)` |
| `y_increment` | **REMOVED.** Use `placement=PlacementOptions(spacing=...)`. |
| `connect_from_previous` | `connection=ConnectionOptions(connect_from_previous=...)` |
| `connect_to_next` | `connection=ConnectionOptions(connect_to_next=...)` |
| `wire_label` | `connection=ConnectionOptions(wire_label=...)` |
| `**kwargs` | unchanged — still flat `**factory_kwargs` (e.g. `direction=`, `label_pos=`) |

## 3. Call-site index (`../auxillary_cabinet_v3/src/circuits/`)

### `feedback.py` (3 calls — flat, factory kwargs only)

**Before:**
```python
q_builder.add_reference(PlcReference.DI, direction="down")
ft_builder.add_reference(PlcReference.DI, direction="down")
builder.add_reference(PlcReference.DI, direction="down")
```
**After (no placement/connection — only factory_kwargs remain flat):**
```python
q_builder.add_reference(PlcReference.DI, direction="down")
ft_builder.add_reference(PlcReference.DI, direction="down")
builder.add_reference(PlcReference.DI, direction="down")
```
*No change needed* — these calls have no placement/connection kwargs.

### `fan_controll.py` (4 calls — with placement)

**Before:**
```python
block_builder.add_reference(
    str(PlcReference.DO_DRY_3),
    relative_to=block_ref.pin("y1"),
    position="above",
    direction="up",
    label_pos="left",
)
```
**After:**
```python
from schematika.core.options import PlacementOptions

block_builder.add_reference(
    str(PlcReference.DO_DRY_3),
    placement=PlacementOptions(relative_to=block_ref.pin("y1"), position="above"),
    direction="up",
    label_pos="left",
)
```

### `fan_singlepole.py` (2 calls — with placement)

**Before:**
```python
builder.add_reference(
    str(PlcReference.DO_DRY_3),
    relative_to=block_ref.pin("y1"),
    position="above",
    direction="up",
    label_pos="left",
)
```
**After:**
```python
builder.add_reference(
    str(PlcReference.DO_DRY_3),
    placement=PlacementOptions(relative_to=block_ref.pin("y1"), position="above"),
    direction="up",
    label_pos="left",
)
```

### `power_supply.py` and `power_switching.py` (1 call each — flat)

**Before / After:** No change — these calls use only `direction=` kwargs.

### `pump_circuit.py` (2 calls — with placement and factory kwargs)

**Before:**
```python
builder.add_reference(
    str(PlcReference.AI_SIG),
    relative_to=ct.pin("41"),
    position="above",
    direction="up",
    label_pos="left",
)
```
**After:**
```python
builder.add_reference(
    str(PlcReference.AI_SIG),
    placement=PlacementOptions(relative_to=ct.pin("41"), position="above"),
    direction="up",
    label_pos="left",
)
```

### `pump_controll.py` (1 call — with placement and connection)

**Before:**
```python
b.add_reference(
    str(PlcReference.DO),
    relative_to=spdt.pin(pins[2]),
    position="below",
    direction="down",
    label_pos="right",
    wire_label=WireLabels.WH_0_5,
)
```
**After:**
```python
from schematika.core.options import ConnectionOptions, PlacementOptions

b.add_reference(
    str(PlcReference.DO),
    placement=PlacementOptions(relative_to=spdt.pin(pins[2]), position="below"),
    connection=ConnectionOptions(wire_label=WireLabels.WH_0_5),
    direction="down",
    label_pos="right",
)
```

### `valve_control.py` (1 call — with factory kwarg)

**Before:**
```python
coil_builder.add_reference(PlcReference.DO, poles=1)
```
**After:** No change — `poles` is a factory kwarg passed through `**factory_kwargs`.

## 4. What to test after migrating

- `b.add_reference("X1")` — chain placement, no extras.
- `b.add_reference("X1", placement=PlacementOptions(relative_to=comp.pin("1"), position="above"))` — non-chain placement.
- `b.add_reference("X1", connection=ConnectionOptions(wire_label="24V"))` — with wire label.
- `b.add_reference("X1", direction="down", label_pos="left")` — factory kwargs still flat.
- `y_increment=` keyword raises `TypeError` immediately.

## 5. Breakage note

All call sites with any of the removed kwargs (`relative_to=`, `position=`,
`spacing=`, `x_offset=`, `y_increment=`, `connect_from_previous=`,
`connect_to_next=`, `wire_label=`) will raise `TypeError` at call time. There
is no fallback. Factory-passthrough kwargs (`direction=`, `label_pos=`, `poles=`,
etc.) are unchanged — they remain flat.
