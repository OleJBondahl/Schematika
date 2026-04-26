# C2d-2 consumer migration — `CircuitBuilder.build` bundling

## 1. Summary

`CircuitBuilder.build` previously accepted 11 keyword-or-positional arguments.
In C2d-2 all build options are bundled into a single frozen dataclass,
`BuildOptions`, imported from `schematika.core.options`:

```python
from schematika.core.options import BuildOptions
```

The new signature is:

```python
def build(self, *, options: BuildOptions | None = None) -> BuildResult:
```

Passing `options=None` (or calling `b.build()` with no arguments) uses all
defaults: `count=1`, `state=self._initial_state`, all reuse/override fields
`None`. No back-compat shim. `b.build(count=2)` raises `TypeError`.

### Key type change: `wire_labels`

`wire_labels` was `list[str] | None`; it is now `Sequence[str] | None`
(accepts both `list` and `tuple`). Consumer code passing a `list` continues to
work.

## 2. Old → new mapping table

| Old kwarg | New |
|-----------|-----|
| `count` | `options=BuildOptions(count=...)` |
| `start_indices` | `options=BuildOptions(start_indices=...)` |
| `terminal_start_indices` | `options=BuildOptions(terminal_start_indices=...)` |
| `tag_generators` | `options=BuildOptions(tag_generators=...)` |
| `fixed_tags` | `options=BuildOptions(fixed_tags=...)` |
| `terminal_maps` | `options=BuildOptions(terminal_maps=...)` |
| `reuse_tags` | `options=BuildOptions(reuse_tags=...)` |
| `reuse_terminals` | `options=BuildOptions(reuse_terminals=...)` |
| `wire_labels` | `options=BuildOptions(wire_labels=...)` (now `Sequence[str]`, was `list[str]`) |
| `state` | `options=BuildOptions(state=...)` |
| `connection_log_path` | `options=BuildOptions(connection_log_path=...)` |

## 3. Call-site index (`../auxillary_cabinet_v3/src/circuits/`)

All 24 call sites are `CircuitBuilder.build` calls (not `Project.build` or
`PIDBuilder.build`). `src/cabinet.py:149` is `project.build(...)` and is
unchanged.

### `fan_controll.py` (3 calls)

**Before:**
```python
coil_builder.build(count=count, wire_labels=COIL_WIRE_LABELS * count)

block_builder.build(
    count=count,
    reuse_tags={"K": coil_builder.result},
    wire_labels=BLOCK_WIRE_LABELS * count,
)

contact_builder.build(
    count=count,
    reuse_tags=contact_reuse,
    wire_labels=CONTACT_WIRE_LABELS * count,
)
```
**After:**
```python
coil_builder.build(options=BuildOptions(count=count, wire_labels=COIL_WIRE_LABELS * count))

block_builder.build(
    options=BuildOptions(
        count=count,
        reuse_tags={"K": coil_builder.result},
        wire_labels=BLOCK_WIRE_LABELS * count,
    )
)

contact_builder.build(
    options=BuildOptions(
        count=count,
        reuse_tags=contact_reuse,
        wire_labels=CONTACT_WIRE_LABELS * count,
    )
)
```

### `fan_singlepole.py` (1 call)

**Before:**
```python
builder.build(count=1, wire_labels=FAN_WIRE_LABELS)
```
**After:**
```python
builder.build(options=BuildOptions(count=1, wire_labels=FAN_WIRE_LABELS))
```

### `feedback.py` (3 calls)

**Before:**
```python
q_builder.build(
    count=count,
    reuse_tags={"Q": reuse_tags["Q"]} if reuse_tags and "Q" in reuse_tags else {},
    wire_labels=FEEDBACK_WIRE_LABELS * count,
)

ft_builder.build(
    count=count,
    reuse_tags={"FT": reuse_tags["FT"]} if reuse_tags and "FT" in reuse_tags else {},
    wire_labels=FEEDBACK_WIRE_LABELS * count,
)

builder.build(
    count=count,
    reuse_tags={"Q": reuse_tags["Q"]} if reuse_tags and "Q" in reuse_tags else {},
    wire_labels=FEEDBACK_WIRE_LABELS * count,
)
```
**After:**
```python
q_builder.build(
    options=BuildOptions(
        count=count,
        reuse_tags={"Q": reuse_tags["Q"]} if reuse_tags and "Q" in reuse_tags else {},
        wire_labels=FEEDBACK_WIRE_LABELS * count,
    )
)

ft_builder.build(
    options=BuildOptions(
        count=count,
        reuse_tags={"FT": reuse_tags["FT"]} if reuse_tags and "FT" in reuse_tags else {},
        wire_labels=FEEDBACK_WIRE_LABELS * count,
    )
)

builder.build(
    options=BuildOptions(
        count=count,
        reuse_tags={"Q": reuse_tags["Q"]} if reuse_tags and "Q" in reuse_tags else {},
        wire_labels=FEEDBACK_WIRE_LABELS * count,
    )
)
```

### `internal_distribution.py` (1 call)

**Before:**
```python
builder.build(count=1, wire_labels=labels)
```
**After:**
```python
builder.build(options=BuildOptions(count=1, wire_labels=labels))
```

### `plc_power.py` (1 call)

**Before:**
```python
return builder.build(count=1, wire_labels=WIRE_LABELS)
```
**After:**
```python
return builder.build(options=BuildOptions(count=1, wire_labels=WIRE_LABELS))
```

### `power_supply.py` (6 calls)

**Before:**
```python
builder.build(count=1)
builder_pe.build(count=1)
block_builder.build(count=1)
builder_left.build(count=1)
builder_right.build(count=1)
contact_builder.build(
    count=1,
    reuse_tags={"U": block_builder.result},
    wire_labels=NO_CONTACT_WIRE_LABELS,
)
```
**After:**
```python
builder.build(options=BuildOptions(count=1))
builder_pe.build(options=BuildOptions(count=1))
block_builder.build(options=BuildOptions(count=1))
builder_left.build(options=BuildOptions(count=1))
builder_right.build(options=BuildOptions(count=1))
contact_builder.build(
    options=BuildOptions(
        count=1,
        reuse_tags={"U": block_builder.result},
        wire_labels=NO_CONTACT_WIRE_LABELS,
    )
)
```

### `power_switching.py` (4 calls)

**Before:**
```python
changeover.build(count=1)
k1_builder.build(count=1, fixed_tags={"K": "K1"}, wire_labels=K1_COIL_WIRE_LABELS)
coil_builder.build(count=1, wire_labels=RELAY_COIL_WIRE_LABELS)
contact_builder.build(
    count=1,
    reuse_tags={"K": coil_builder.result},
    wire_labels=RELAY_CONTACT_WIRE_LABELS,
)
```
**After:**
```python
changeover.build(options=BuildOptions(count=1))
k1_builder.build(options=BuildOptions(count=1, fixed_tags={"K": "K1"}, wire_labels=K1_COIL_WIRE_LABELS))
coil_builder.build(options=BuildOptions(count=1, wire_labels=RELAY_COIL_WIRE_LABELS))
contact_builder.build(
    options=BuildOptions(
        count=1,
        reuse_tags={"K": coil_builder.result},
        wire_labels=RELAY_CONTACT_WIRE_LABELS,
    )
)
```

### `pump_circuit.py` (1 call)

**Before:**
```python
res = builder.build(count=1, wire_labels=PUMP_WIRE_LABELS)
```
**After:**
```python
res = builder.build(options=BuildOptions(count=1, wire_labels=PUMP_WIRE_LABELS))
```

### `pump_controll.py` (2 calls)

**Before:**
```python
coil_builder.build(count=1, wire_labels=[WireLabels.RD_0_5, WireLabels.WH_0_5])
b.build(count=1, fixed_tags={"K": relay_tag}, tag_generators=shared_reuse or None)
```
**After:**
```python
coil_builder.build(options=BuildOptions(count=1, wire_labels=[WireLabels.RD_0_5, WireLabels.WH_0_5]))
b.build(options=BuildOptions(count=1, fixed_tags={"K": relay_tag}, tag_generators=shared_reuse or None))
```

### `valve_control.py` (2 calls)

**Before:**
```python
coil_builder.build(count=count, wire_labels=COIL_WIRE_LABELS * count)
contact_builder.build(count=count, reuse_tags={"K": coil_builder.result}, wire_labels=CONTACT_WIRE_LABELS * count)
```
**After:**
```python
coil_builder.build(options=BuildOptions(count=count, wire_labels=COIL_WIRE_LABELS * count))
contact_builder.build(
    options=BuildOptions(
        count=count,
        reuse_tags={"K": coil_builder.result},
        wire_labels=CONTACT_WIRE_LABELS * count,
    )
)
```

## 4. What to test

- `b.build()` (no args) still works — defaults to `count=1`, `state` from constructor.
- `b.build(options=BuildOptions(count=3))` produces 3 instances.
- `b.build(options=BuildOptions(wire_labels=[...]))` applies labels.
- `b.build(options=BuildOptions(reuse_tags={"K": result}))` reuses tags.
- `b.build(count=1)` raises `TypeError` (no back-compat shim).

## 5. Breaking change notice

This is a hard breaking change in wave C2d-2. Every direct caller of
`CircuitBuilder.build` with keyword arguments must be updated. The consumer
project (`auxillary_cabinet_v3`) has 24 call sites across 9 files listed above.

Import `BuildOptions` from `schematika.core.options` and wrap the old kwargs
in `options=BuildOptions(...)`. The `wire_labels` field now accepts any
`Sequence[str]` (list or tuple); no conversion is needed for existing list
values.
