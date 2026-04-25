# Data Sources in Schematika

What the existing domain packages expose, what cross-domain linkage
exists, and what gaps the Overview module must fill from elsewhere.

## Domain packages

### `electrical/`

- Entry: `electrical.CircuitBuilder.build()` returns `BuildResult`
  (`src/schematika/electrical/builder_models.py:175`).
- `BuildResult` carries:
  - `wire_connections: list[(term_tag, term_pin, comp_tag, comp_pin)]`
    — the wire list.
  - `device_registry: dict[tag, InternalDevice]` — which symbol/MPN lives
    at which tag.
  - `terminal_pin_map: dict[term_tag, list[pins]]` — pin allocation per
    terminal.
  - `bridge_groups: dict[term_tag, list[(start, end)]]` — bridged pin
    ranges.
  - `circuit: Circuit` — the full schematic data model.
  - `state` — internal builder state, used to thread shared data.
- Public `Terminal` lives in `src/schematika/electrical/terminal.py`.
  `Terminal` IDs are arbitrary strings (`"X1"`, `"PLC:AI"`).

### `pcb/`

- Entry: `pcb.build(circuit, mapping)` returns `PCBBuildResult`
  (`src/schematika/pcb/model.py:168`).
- Carries `columns: tuple[(column_key, Circuit), ...]` — circuits laid
  out as KiCad netlist input.
- Pin identifiers are KiCad pin numbers as strings.
- Components identified by part_ref (`"J1"`, `"U1"`).

### `cable/`

- Entry: `cable.build_cable_drawings(connections, devices, ...)` returns
  `list[CableDrawing]` (`src/schematika/cable/model.py:81`).
- `CableDrawing` carries:
  - `cable: CableDef` — designator, wire count, gauge, colors, length.
  - `connectors: tuple[CableConnector, ...]` — exactly two.
  - `connections: tuple[CableConnection, ...]` — per-wire mapping
    `(from_connector, from_pin, cable, wire, to_connector, to_pin)`.

### `block/` — IGNORE

Not in production. Not part of the Overview data flow. Do not use.

## Cross-domain linkage

Linkage is **string identity** on terminal tags + pin names.

- Terminals are defined once per consumer repo (e.g.
  `auxillary_cabinet_v3/src/devices/terminals.py:30` defines
  `FUSED_24V = Terminal("X52", ...)`) and referenced by both internal
  circuits and field-device declarations.
- Schematika resolves the references during `project.build_circuits()`
  and threads the resolved state through the registry.

There is no typed ID system; the contract is "use the same string." This
is fragile in theory and works in practice because terminals are
defined in one place per consumer repo and imported by all consumers
within that repo.

## What a built `Project` exposes

After `project.build_circuits()` has run:

- `project._results: dict[circuit_key, BuildResult]` — every electrical
  / PCB circuit registered with `add_circuit()` or `add_pcb()`.
- `project._external_connections: list[ConnectionRow]` — field-device
  wiring rows of the form
  `(component_from, pin_from, terminal, terminal_pin, component_to, pin_to)`.
- `project._terminals` — the terminal lexicon registered via
  `project.terminals(...)`.
- Cable drawings (when `project.field_devices(...)` resolves them).

The Overview extractor reads from these. No new fields on `*BuildResult`
are needed for v0.

## Gaps Overview must fill from elsewhere

| Gap | Source today | v0 resolution |
|---|---|---|
| Containment (parent/child between cabinet/PCB/peer) | Not in data | Consumer-supplied containment dict |
| Signal kind (power / CAN / safety / signal / ...) | Not in data | Consumer-supplied classifier callable + palette dict, with name-pattern default |
| Port ordering hints | Insertion order today | Optional per-unit hint, deferrable to v0.5+ |

These gaps are inputs to Overview, not refactors of other modules. The
"shared data module" idea (canonical types in `core/datamodel/` adopted
by every domain) is deliberately deferred — it would be designing the
shared shapes against one example. Re-evaluate after the first end-to-end
v0 lands.
