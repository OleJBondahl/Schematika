# Schematika LLM Reference

## The Pattern

```python
from schematika import (
    CircuitBuilder, create_initial_state, render_system,
    breaker,
)

state = create_initial_state()
builder = CircuitBuilder(state)
builder.set_layout(x=0, y=0, spacing=150)
tm = builder.add_terminal(tm_id="X1", poles=3)
cb = builder.add_symbol(breaker, tag_prefix="F", poles=3)
result = builder.build(count=1, wire_labels=["L1", "L2", "L3"])
render_system(result.circuit, "output.svg")
```

## Symbol Catalog

All symbols use a unified API: `symbol_name(label, poles, pins)`. When `pins` is omitted, IEC-standard pins are auto-selected based on `poles`.

| Factory Function | Default Pins | Poles | Description |
|---|---|---|---|
| `no_contact` | `("13","14")` | 1 | NO contact |
| `no_contact` (poles=3) | `("13","14")` x3 | 3 | 3P NO contact |
| `nc_contact` | `("11","12")` | 1 | NC contact |
| `nc_contact` (poles=3) | `("11","12")` x3 | 3 | 3P NC contact |
| `spdt_contact` | `("11","12","14")` | 1 | Changeover (COM,NC,NO) |
| `spdt_contact` (poles=3) | `("11","12","14","21","22","24","31","32","34")` | 3 | 3P changeover |
| `coil` | `("A1","A2")` | 1 | Relay/contactor coil |
| `breaker` | `("1","2")` | 1 | Circuit breaker |
| `breaker` (poles=2) | `("1","2")` x2 | 2 | 2P breaker |
| `breaker` (poles=3) | `("1","2")` x3 | 3 | 3P breaker |
| `thermal_overload` | `("","T1","","T2","","T3")` | 1 | Thermal overload |
| `thermal_overload` (poles=3) | same | 3 | 3P thermal overload |
| `fuse` | `("1","2")` | 1 | Fuse |
| `motor` | `("1","2")` | 1 | Generic motor |
| `motor` (poles=3) | `("U","V","W","PE")` | 3 | 3-phase motor |
| `contactor` | contacts: `("L1","T1","L2","T2","L3","T3")` | 3 | Contactor + coil assembly |
| `estop` | `("1","2")` | 1 | E-stop + NC contact |
| `turn_switch` | `("1","2")` | 1 | Turn switch + NO contact |
| `terminal` | `()` | 1 | Single terminal |
| `terminal` (poles=3) | `("1","2","3")` | 3 | 3P terminal block |
| `psu` | fixed: L,N,PE / 24V,GND | - | Power supply unit |
| `block` | configurable top/bottom | - | Generic block with pins |
| `terminal_box` | auto-numbered | N | Rectangular terminal box |
| `ref_symbol` | `()` | - | Reference arrow (cross-ref) |
| `ct` | none | - | CT circle (no ports) |
| `ct_assembly` | `("1","2")` | - | CT + terminal box |

## Pin Conventions (IEC 60617)

- **NO contacts:** 13/14 (per pole: 13/14, 23/24, 33/34)
- **NC contacts:** 11/12 (per pole: 11/12, 21/22, 31/32)
- **SPDT:** 11=COM, 12=NC, 14=NO (per pole prefix: 1x, 2x, 3x)
- **Coils:** A1 (top), A2 (bottom)
- **Breakers:** 1/2 per pole (1-2, 3-4, 5-6)
- **Contactors:** L1/T1, L2/T2, L3/T3
- **Motors:** U, V, W, PE
- **Thermal overload:** /T1, /T2, /T3 (input pins unnamed)

## Tag Prefixes

`X`=terminal, `Q`=contactor, `F`=breaker, `K`=relay, `S`=switch, `U`=block, `M`=motor, `H`=indicator, `B`=sensor, `T`=transformer, `PSU`=power supply

## State Threading

`create_initial_state()` returns a state that tracks tag counters and terminal numbering. Pass it to `CircuitBuilder(state)`, then use `result.state` from `.build()` as input to the next builder. This ensures unique, sequential tag numbers across all circuits.

## reuse_tags

Use `reuse_tags` when a contactor's power circuit and control circuit share the same tag (e.g., Q1 power poles + Q1 coil):

```python
power_result = power_builder.build(count=3)
control_builder.add_symbol(coil, tag_prefix="Q", poles=1)
control_result = control_builder.build(reuse_tags={"Q": power_result})
```

## Common Mistakes

1. **Wrong pin names** -- Use IEC constants (`CB_3P_PINS`, `COIL_PINS`, `NO_CONTACT_PINS`) or let the symbol auto-select pins based on `poles`
2. **Passing string instead of factory** -- `add_symbol(breaker, ...)` not `add_symbol("breaker", ...)`
3. **Forgetting state threading** -- Always pass `result.state` to the next `CircuitBuilder`, or counters reset
4. **Wire label count mismatch** -- `wire_labels` list length must equal the number of vertical wires (= max poles across components)
5. **Using `y_increment` instead of `spacing`** -- The parameter is `spacing` on `set_layout()` and `add_symbol()`
