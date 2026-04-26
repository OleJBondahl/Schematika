# C2b consumer migration — `add_symbol` bundling

## 1. Summary

`CircuitBuilder.add_symbol` previously accepted 13 keyword/positional-or-keyword
arguments plus `**kwargs` factory passthrough. In C2b these are bundled into three
frozen dataclasses imported from `schematika.core.options`:

- **`SymbolConfig`** (new) — `tag_prefix` (required), `poles`, `pins`,
  `device`, `wire_labels_above`, `factory_kwargs`.
- **`PlacementOptions`** (from C2a) — `relative_to`, `position`, `spacing`,
  `x_offset`.
- **`ConnectionOptions`** (from C2a) — `connect_from_previous`, `connect_to_next`.

Key removals and renames:

- `tag_prefix` moves into `SymbolConfig` as a **required** field — every call
  site must now pass `config=SymbolConfig(tag_prefix=...)`.
- `**kwargs` factory passthrough is replaced by
  `SymbolConfig.factory_kwargs: Mapping[str, Any] | None`.
- `y_increment` is **removed** — use `PlacementOptions.spacing` instead.
- `pins` and `wire_labels_above` accept only `tuple[str, ...] | None` (not
  `list`) — convert any list literals to tuples.

This is a single hard breaking commit. There is no compatibility shim.

## 2. Old → new mapping table

| Old kwarg | New location |
|-----------|--------------|
| `tag_prefix` | `config=SymbolConfig(tag_prefix=...)` (required) |
| `poles` | `config=SymbolConfig(poles=...)` |
| `pins` | `config=SymbolConfig(pins=...)` (must be `tuple`, not `list`) |
| `device` | `config=SymbolConfig(device=...)` |
| `wire_labels_above` | `config=SymbolConfig(wire_labels_above=...)` (must be `tuple`) |
| `**kwargs` | `config=SymbolConfig(factory_kwargs={"key": value, ...})` |
| `relative_to` | `placement=PlacementOptions(relative_to=...)` |
| `position` | `placement=PlacementOptions(position=...)` |
| `spacing` | `placement=PlacementOptions(spacing=...)` |
| `x_offset` | `placement=PlacementOptions(x_offset=...)` |
| `y_increment` | **REMOVED.** Use `placement=PlacementOptions(spacing=...)`. |
| `connect_from_previous` | `connection=ConnectionOptions(connect_from_previous=...)` |
| `connect_to_next` | `connection=ConnectionOptions(connect_to_next=...)` |

## 3. Call-site index (`../auxillary_cabinet_v3/src/circuits/`)

### `fan_controll.py`

**Before:**
```python
coil_ref = coil_builder.add_symbol(
    coil,
    "K",
    device=Devices.RELAY_FAN,
)
```
**After:**
```python
coil_ref = coil_builder.add_symbol(
    coil,
    config=SymbolConfig(tag_prefix="K", device=Devices.RELAY_FAN),
)
```

**Before (block with factory kwargs):**
```python
block_ref = block_builder.add_symbol(
    block,
    "K",
    pins=("y1", "y2", "t1", "t2"),
    connect_from_previous=False,
    device=Devices.RELAY_FAN,
    top_pins=("y1", "y2"),
    bottom_pins=("t1", "t2"),
)
```
**After:**
```python
block_ref = block_builder.add_symbol(
    block,
    config=SymbolConfig(
        tag_prefix="K",
        pins=("y1", "y2", "t1", "t2"),
        device=Devices.RELAY_FAN,
        factory_kwargs={"top_pins": ("y1", "y2"), "bottom_pins": ("t1", "t2")},
    ),
    connection=ConnectionOptions(connect_from_previous=False),
)
```

**Before:**
```python
q_coil = contact_builder.add_symbol(
    coil,
    "Q",
    relative_to=spdt.pin("14"),
    device=Devices.CONTACTOR_3P,
)
```
**After:**
```python
q_coil = contact_builder.add_symbol(
    coil,
    config=SymbolConfig(tag_prefix="Q", device=Devices.CONTACTOR_3P),
    placement=PlacementOptions(relative_to=spdt.pin("14")),
)
```

### `fan_singlepole.py`

**Before:**
```python
builder.add_symbol(
    breaker,
    tag_prefix="F",
    poles=2,
    device=Devices.BREAKER_2P_FAN,
)
```
**After:**
```python
builder.add_symbol(
    breaker,
    config=SymbolConfig(tag_prefix="F", poles=2, device=Devices.BREAKER_2P_FAN),
)
```

**Before:**
```python
c = builder.add_symbol(
    contactor,
    tag_prefix="Q",
    device=Devices.CONTACTOR_3P,
)
```
**After:**
```python
c = builder.add_symbol(
    contactor,
    config=SymbolConfig(tag_prefix="Q", device=Devices.CONTACTOR_3P),
)
```

**Before:**
```python
ct = builder.add_symbol(
    ct_assembly,
    tag_prefix="CT",
    pins=CT_PINS,
    connect_from_previous=False,
    connect_to_next=False,
    device=Devices.CT,
)
```
**After:**
```python
ct = builder.add_symbol(
    ct_assembly,
    config=SymbolConfig(tag_prefix="CT", pins=CT_PINS, device=Devices.CT),
    connection=ConnectionOptions(connect_from_previous=False, connect_to_next=False),
)
```

### `feedback.py`

**Before:**
```python
q_builder.add_symbol(no_contact, "Q", device=Devices.CONTACTOR_3P)
ft_builder.add_symbol(no_contact, "FT", device=Devices.THERMAL_OL)
builder.add_symbol(no_contact, "Q", device=Devices.CONTACTOR_3P)
```
**After:**
```python
q_builder.add_symbol(no_contact, config=SymbolConfig(tag_prefix="Q", device=Devices.CONTACTOR_3P))
ft_builder.add_symbol(no_contact, config=SymbolConfig(tag_prefix="FT", device=Devices.THERMAL_OL))
builder.add_symbol(no_contact, config=SymbolConfig(tag_prefix="Q", device=Devices.CONTACTOR_3P))
```

### `plc_power.py`

**Before (factory kwargs via `**kwargs`):**
```python
builder.add_symbol(
    block,
    "PLC",
    pins=("24V", "GND"),
    top_pins=("24V",),
    bottom_pins=("GND",),
    device=Devices.PLC_CONTROLLER,
)
```
**After:**
```python
builder.add_symbol(
    block,
    config=SymbolConfig(
        tag_prefix="PLC",
        pins=("24V", "GND"),
        device=Devices.PLC_CONTROLLER,
        factory_kwargs={"top_pins": ("24V",), "bottom_pins": ("GND",)},
    ),
)
```

### `power_supply.py`

**Before:**
```python
cb = builder.add_symbol(
    breaker,
    tag_prefix=StandardTags.BREAKER,
    poles=2,
    spacing=SPACING_NARROW,
    x_offset=0,
    connect_from_previous=False,
    device=Devices.BREAKER_2P_PSU,
)
psu_ref = builder.add_symbol(
    psu,
    tag_prefix=StandardTags.POWER_SUPPLY,
    spacing=SPACING_NARROW,
    pins=psu_pins,
    connect_from_previous=False,
    device=Devices.PSU_24V,
)
block_builder.add_symbol(
    block,
    tag_prefix="U",
    connect_from_previous=False,
    connect_to_next=False,
    device=Devices.RED_MODULE,
    top_pins=tuple(top_pin_labels),
    top_pin_positions=tuple(top_pin_positions),
    bottom_pins=bottom_pin_labels,
)
contact_builder.add_symbol(no_contact, "U", device=Devices.RED_MODULE)
```
**After:**
```python
cb = builder.add_symbol(
    breaker,
    config=SymbolConfig(
        tag_prefix=StandardTags.BREAKER,
        poles=2,
        device=Devices.BREAKER_2P_PSU,
    ),
    placement=PlacementOptions(spacing=SPACING_NARROW, x_offset=0),
    connection=ConnectionOptions(connect_from_previous=False),
)
psu_ref = builder.add_symbol(
    psu,
    config=SymbolConfig(
        tag_prefix=StandardTags.POWER_SUPPLY,
        pins=psu_pins,
        device=Devices.PSU_24V,
    ),
    placement=PlacementOptions(spacing=SPACING_NARROW),
    connection=ConnectionOptions(connect_from_previous=False),
)
block_builder.add_symbol(
    block,
    config=SymbolConfig(
        tag_prefix="U",
        device=Devices.RED_MODULE,
        factory_kwargs={
            "top_pins": tuple(top_pin_labels),
            "top_pin_positions": tuple(top_pin_positions),
            "bottom_pins": bottom_pin_labels,
        },
    ),
    connection=ConnectionOptions(connect_from_previous=False, connect_to_next=False),
)
contact_builder.add_symbol(
    no_contact, config=SymbolConfig(tag_prefix="U", device=Devices.RED_MODULE)
)
```

### `power_switching.py`

**Before:**
```python
k1_builder.add_symbol(coil, "K")
coil_builder.add_symbol(coil, "K", device=Devices.RELAY_230V_1x21)
contact_builder.add_symbol(no_contact, "K", device=Devices.RELAY_230V_1x21)
```
**After:**
```python
k1_builder.add_symbol(coil, config=SymbolConfig(tag_prefix="K"))
coil_builder.add_symbol(coil, config=SymbolConfig(tag_prefix="K", device=Devices.RELAY_230V_1x21))
contact_builder.add_symbol(no_contact, config=SymbolConfig(tag_prefix="K", device=Devices.RELAY_230V_1x21))
```

### `pump_circuit.py`

**Before:**
```python
builder.add_symbol(breaker, tag_prefix="F", poles=3, device=Devices.BREAKER_3P_MOTOR)
builder.add_symbol(contactor, tag_prefix="Q", poles=3, device=Devices.CONTACTOR_3P, spacing=SPACING_DEFAULT / 2)
thermal_overload_ref = builder.add_symbol(
    thermal_overload, tag_prefix="FT", poles=3, pins=THERMAL_OVERLOAD_PINS, device=Devices.THERMAL_OL
)
ct = builder.add_symbol(
    ct_assembly, tag_prefix="CT", pins=CT_PINS,
    connect_from_previous=False, connect_to_next=False, device=Devices.CT,
)
```
**After:**
```python
builder.add_symbol(
    breaker,
    config=SymbolConfig(tag_prefix="F", poles=3, device=Devices.BREAKER_3P_MOTOR),
)
builder.add_symbol(
    contactor,
    config=SymbolConfig(tag_prefix="Q", poles=3, device=Devices.CONTACTOR_3P),
    placement=PlacementOptions(spacing=SPACING_DEFAULT / 2),
)
thermal_overload_ref = builder.add_symbol(
    thermal_overload,
    config=SymbolConfig(tag_prefix="FT", poles=3, pins=THERMAL_OVERLOAD_PINS, device=Devices.THERMAL_OL),
)
ct = builder.add_symbol(
    ct_assembly,
    config=SymbolConfig(tag_prefix="CT", pins=CT_PINS, device=Devices.CT),
    connection=ConnectionOptions(connect_from_previous=False, connect_to_next=False),
)
```

### `pump_controll.py`

**Before:**
```python
coil_builder.add_symbol(coil, "K", device=Devices.RELAY_24V_4x21)
b.add_symbol(coil, "Q", device=Devices.CONTACTOR_3P, wire_labels_above=[WireLabels.RD_0_5])
```
**After:**
```python
coil_builder.add_symbol(
    coil, config=SymbolConfig(tag_prefix="K", device=Devices.RELAY_24V_4x21)
)
b.add_symbol(
    coil,
    config=SymbolConfig(
        tag_prefix="Q",
        device=Devices.CONTACTOR_3P,
        wire_labels_above=(WireLabels.RD_0_5,),  # list → tuple
    ),
)
```

### `valve_control.py`

**Before:**
```python
coil_builder.add_symbol(coil, "K", device=Devices.RELAY_24V_1x21)
contact_builder.add_symbol(no_contact, "K", device=Devices.RELAY_24V_1x21)
```
**After:**
```python
coil_builder.add_symbol(coil, config=SymbolConfig(tag_prefix="K", device=Devices.RELAY_24V_1x21))
contact_builder.add_symbol(no_contact, config=SymbolConfig(tag_prefix="K", device=Devices.RELAY_24V_1x21))
```

## 4. What to test after migration

1. Add the import at the top of each circuit file:
   ```python
   from schematika.core.options import SymbolConfig, PlacementOptions, ConnectionOptions
   ```
2. Update each `add_symbol` call per the mapping above.
3. Run the consumer entry-point:
   ```bash
   cd ../auxillary_cabinet_v3
   uv run python src/main.py
   ```
4. Diff the resulting SVG(s) against the pre-migration versions — output should
   be byte-identical because no rendering behaviour changed.

## 5. Breakage note

**This is a breaking change.** The consumer will not import or run until updated.
There is no compatibility shim. Every call site that uses `add_symbol` must be
updated to pass `config=SymbolConfig(tag_prefix=...)`.
