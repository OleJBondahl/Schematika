# `Project` integration reference

Quick reference for wiring `PCBBuildResult` (or any domain-module result) into `schematika.project.Project`. Source: `src/schematika/project.py`.

## Relevant `Project` methods

| Method | Line | Purpose |
|---|---|---|
| `add_circuit(key, builder_fn, count=1, **kwargs)` | 288 | Register a deferred circuit. `builder_fn(state, **kwargs)` must return `BuildResult`. |
| `page(title, circuit_key)` | 632 | Add a schematic page. `circuit_key` is a registered key or a list of keys (merged onto one page). |
| `build(output, temp_dir="temp", keep_temp=False, datetime_stamp=True)` | 820 | Build all deferred circuits, render SVGs, compile PDF via Typst. |

## `BuildResult` shape

`src/schematika/electrical/builder_models.py:175`.

```python
@dataclass
class BuildResult:
    state: GenerationState
    circuit: Circuit
    used_terminals: list[Any]
    component_map: dict[str, list[str]] = field(default_factory=dict)
    terminal_pin_map: dict[str, list[str]] = field(default_factory=dict)
    device_registry: dict[str, InternalDevice] = field(default_factory=dict)
    wire_connections: list[tuple[str, str, str, str]] = field(default_factory=list)
    bridge_groups: dict[str, list[tuple[int, int]]] = field(default_factory=dict)
    connection_log: list[str] = field(default_factory=list)
```

For pcb columns with no terminal state: return `used_terminals=[]` and leave the rest default.

## Deferred builder wrap pattern

`add_circuit` expects a callable, not a `Circuit`. Wrap an already-built `Circuit` with a default-arg closure so loop binding does not capture by reference:

```python
from schematika.electrical import BuildResult

def add_to_project(project, result):
    for key, circuit in result.columns:
        project.add_circuit(
            key,
            lambda state, c=circuit: BuildResult(
                state=state, circuit=c, used_terminals=[]
            ),
        )
    for title, keys in result.pages:
        project.page(title, list(keys))
```

The `c=circuit` default-arg idiom is the standard Python loop-capture fix. Without it every lambda closes over the last `circuit`.

## Building a single column inside `pcb/builder.py`

Use `CircuitBuilder` from `schematika.electrical`:

```python
from schematika.electrical import CircuitBuilder

def _build_column(state, column_symbols) -> Circuit:
    b = CircuitBuilder(state)
    b.set_layout(x=0, y=0, spacing=150, symbol_spacing=50)
    for sym, ref, pins in column_symbols:
        b.add_symbol(sym, ref, pins=pins)
    for src, src_pin, dst, dst_pin in column_connections:
        b.add_connection(src, src_pin, dst, dst_pin)
    return b.build().circuit
```

State threading happens automatically through `Project._build_all_circuits` — you return a `Circuit`, not a full `BuildResult`, because `pcb/` columns do not own terminal numbering.

## Page titles

Per spec: auto-generate `"Page 1"`, `"Page 2"`, …. Callers who want custom titles re-build a `PCBBuildResult` with replaced pages, or call `project.add_circuit` + `project.page` directly instead of `add_to_project`.
