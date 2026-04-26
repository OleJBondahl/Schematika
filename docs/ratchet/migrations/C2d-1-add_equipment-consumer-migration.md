# C2d-1 consumer migration — `add_equipment` bundling

## 1. Summary

`PIDBuilder.add_equipment` previously accepted `name` as the sole positional-only
argument, `factory` and `tag_prefix` as positional-or-keyword arguments, plus
6 keyword-only placement arguments and `**kwargs` for factory passthrough — 10
arguments total. In C2d-1 these are bundled into two frozen dataclasses:

- **`EquipmentConfig`** (new) — `factory`, `tag_prefix`, `factory_kwargs`.
  `factory` and `tag_prefix` are **required** (no defaults).
- **`EquipmentPlacement`** (new) — `relative_to`, `from_port`, `to_port`,
  `offset`, `position`, `x`, `y`. All default to their former values.

The new signature is:
```python
def add_equipment(self, name: str, /, *, config: EquipmentConfig, placement: EquipmentPlacement | None = None) -> PIDBuilder
```

`config` is **required** (no default). `placement` defaults to `None` (absolute
position 0,0 — same as before when no placement kwargs were passed).

This is a single hard breaking commit. There is no compatibility shim.

## 2. Old → new mapping table

| Old kwarg | New location |
|-----------|--------------|
| `factory` (positional-or-keyword) | `config=EquipmentConfig(factory=...)` (required) |
| `tag_prefix` (positional-or-keyword) | `config=EquipmentConfig(tag_prefix=...)` (required) |
| `**kwargs` | `config=EquipmentConfig(factory_kwargs={"key": value, ...})` |
| `relative_to` | `placement=EquipmentPlacement(relative_to=...)` |
| `from_port` | `placement=EquipmentPlacement(from_port=...)` |
| `to_port` | `placement=EquipmentPlacement(to_port=...)` |
| `offset` | `placement=EquipmentPlacement(offset=...)` |
| `position` | `placement=EquipmentPlacement(position=...)` |
| `x` | `placement=EquipmentPlacement(x=...)` |
| `y` | `placement=EquipmentPlacement(y=...)` |

## 3. Call-site index (`../auxillary_cabinet_v3/src/pid.py`, ~14 call sites)

### Flat absolute placement (x,y only)

**Before:**
```python
b.add_equipment("inlet", pipe_segment, "PIPE", x=20, y=70, length=20.0)
```
**After:**
```python
from schematika.core.options import EquipmentConfig, EquipmentPlacement

b.add_equipment(
    "inlet",
    config=EquipmentConfig(factory=pipe_segment, tag_prefix="PIPE", factory_kwargs={"length": 20.0}),
    placement=EquipmentPlacement(x=20, y=70),
)
```
Note: `length=20.0` was previously a `**kwargs` passthrough; it moves into
`EquipmentConfig.factory_kwargs`.

### Anchor-relative placement (the dominant pattern)

**Before:**
```python
b.add_equipment(
    "tw_valve1",
    three_way_valve,
    "V",
    relative_to="inlet",
    from_port="out",
    to_port="in",
)
```
**After:**
```python
b.add_equipment(
    "tw_valve1",
    config=EquipmentConfig(factory=three_way_valve, tag_prefix="V"),
    placement=EquipmentPlacement(relative_to="inlet", from_port="out", to_port="in"),
)
```

### Anchor-relative with offset (most kwarg-rich pattern)

**Before:**
```python
b.add_equipment(
    "sv1",
    gate_valve,
    "V",
    relative_to="tw_valve1",
    from_port="out_a",
    to_port="in",
    offset=(_EQ_GAP, 0),
)
```
**After:**
```python
b.add_equipment(
    "sv1",
    config=EquipmentConfig(factory=gate_valve, tag_prefix="V"),
    placement=EquipmentPlacement(
        relative_to="tw_valve1",
        from_port="out_a",
        to_port="in",
        offset=(_EQ_GAP, 0),
    ),
)
```

### Anchor-relative with factory kwargs + offset

**Before:**
```python
b.add_equipment(
    "out_a",
    pipe_segment,
    "PIPE",
    relative_to="pump1",
    from_port="outlet",
    to_port="in",
    offset=(_INST_DX + 30, 0),
    length=15.0,
)
```
**After:**
```python
b.add_equipment(
    "out_a",
    config=EquipmentConfig(
        factory=pipe_segment,
        tag_prefix="PIPE",
        factory_kwargs={"length": 15.0},
    ),
    placement=EquipmentPlacement(
        relative_to="pump1",
        from_port="outlet",
        to_port="in",
        offset=(_INST_DX + 30, 0),
    ),
)
```

## 4. What to test after migrating

- `b.add_equipment("p", config=EquipmentConfig(factory=pump, tag_prefix="P"))` —
  minimal call, absolute (0,0) placement.
- `b.add_equipment("p", config=EquipmentConfig(factory=pump, tag_prefix="P"), placement=EquipmentPlacement(x=50, y=50))` —
  explicit absolute placement.
- Relative placement: confirm port alignment is unchanged after migration.
- Factory kwargs: confirm `pipe_segment` with `length=` still produces correct
  pipe geometry when passed via `EquipmentConfig(factory_kwargs={"length": ...})`.
- Duplicate name: confirm `PIDValidationError` still raised.
- Invalid `relative_to`: confirm `PIDValidationError` still raised.
- `config=` omitted raises `TypeError` immediately (required arg).

## 5. Breakage note

All call sites that pass `factory`, `tag_prefix`, or any of the placement/
factory kwargs as bare keyword arguments will raise `TypeError` at call time.
There is no fallback. The most common migration patterns are:

1. `b.add_equipment("name", factory, "tag")` → wrap factory+tag in `EquipmentConfig`.
2. Add `placement=EquipmentPlacement(...)` if any of `relative_to`, `from_port`,
   `to_port`, `offset`, `position`, `x`, `y` were present.
3. Move any remaining `**kwargs` into `EquipmentConfig(factory_kwargs={...})`.
