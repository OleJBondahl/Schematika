# Schematika LLM Reference

## The Pattern

```python
from schematika import (
    CircuitBuilder, create_initial_state, render_system,
    circuit_breaker_symbol, CB_3P_PINS,
)

state = create_initial_state()
builder = CircuitBuilder(state)
builder.set_layout(x=0, y=0, spacing=150)
tm = builder.add_terminal(tm_id="X1", poles=3)
cb = builder.add_symbol(circuit_breaker_symbol, tag_prefix="F", poles=3, pins=CB_3P_PINS)
result = builder.build(count=1, wire_labels=["L1", "L2", "L3"])
render_system(result.circuit, "output.svg")
```

## Symbol Catalog

| Factory Function | Default Pins | Poles | Description |
|---|---|---|---|
| `normally_open_symbol` | `("13","14")` | 1 | NO contact |
| `three_pole_normally_open_symbol` | `("13","14")` x3 | 3 | 3P NO contact |
| `normally_closed_symbol` | `("11","12")` | 1 | NC contact |
| `three_pole_normally_closed_symbol` | `("11","12")` x3 | 3 | 3P NC contact |
| `spdt_contact_symbol` | `("11","12","14")` | 1 | Changeover (COM,NC,NO) |
| `three_pole_spdt_symbol` | `("11","12","14","21","22","24","31","32","34")` | 3 | 3P changeover |
| `multi_pole_spdt_symbol` | auto IEC | N | N-pole changeover |
| `coil_symbol` | `("A1","A2")` | 1 | Relay/contactor coil |
| `circuit_breaker_symbol` | `("1","2")` | 1 | Circuit breaker |
| `two_pole_circuit_breaker_symbol` | `("1","2")` x2 | 2 | 2P breaker |
| `three_pole_circuit_breaker_symbol` | `("1","2")` x3 | 3 | 3P breaker |
| `thermal_overload_symbol` | `("","T1","","T2","","T3")` | 1 | Thermal overload |
| `three_pole_thermal_overload_symbol` | same | 3 | 3P thermal overload |
| `fuse_symbol` | `("1","2")` | 1 | Fuse |
| `motor_symbol` | `("1","2")` | 1 | Generic motor |
| `three_pole_motor_symbol` | `("U","V","W","PE")` | 3 | 3-phase motor |
| `contactor_symbol` | contacts: `("L1","T1","L2","T2","L3","T3")` | 3 | Contactor + coil assembly |
| `emergency_stop_assembly_symbol` | `("1","2")` | 1 | E-stop + NC contact |
| `turn_switch_assembly_symbol` | `("1","2")` | 1 | Turn switch + NO contact |
| `terminal_symbol` | `()` | 1 | Single terminal |
| `three_pole_terminal_symbol` | `("1","2","3")` | 3 | 3P terminal block |
| `multi_pole_terminal_symbol` | `()` | N | N-pole terminal block |
| `psu_symbol` | fixed: L,N,PE / 24V,GND | - | Power supply unit |
| `dynamic_block_symbol` | configurable top/bottom | - | Generic block with pins |
| `terminal_box_symbol` | auto-numbered | N | Rectangular terminal box |
| `ref_symbol` | `()` | - | Reference arrow (cross-ref) |
| `current_transducer_symbol` | none | - | CT circle (no ports) |
| `current_transducer_assembly_symbol` | `("1","2")` | - | CT + terminal box |

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
control_builder.add_symbol(coil_symbol, tag_prefix="Q", poles=1, pins=COIL_PINS)
control_result = control_builder.build(reuse_tags={"Q": power_result})
```

## Common Mistakes

1. **Wrong pin names** -- Use IEC constants (`CB_3P_PINS`, `COIL_PINS`, `NO_CONTACT_PINS`) not invented strings
2. **Passing string instead of factory** -- `add_symbol(circuit_breaker_symbol, ...)` not `add_symbol("circuit_breaker_symbol", ...)`
3. **Forgetting state threading** -- Always pass `result.state` to the next `CircuitBuilder`, or counters reset
4. **Wire label count mismatch** -- `wire_labels` list length must equal the number of vertical wires (= max poles across components)
5. **Using `y_increment` instead of `spacing`** -- The parameter is `spacing` on `set_layout()` and `add_symbol()`
