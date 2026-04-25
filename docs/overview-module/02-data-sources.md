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
  It's a `str` subclass carrying metadata. `Terminal` IDs are
  arbitrary strings (`"X1"`, `"PLC:AI"`). **Do not confuse with**
  `TerminalSymbol` in `src/schematika/electrical/symbols/terminals.py`,
  which is the internal rendered symbol — not the same type, not the
  one Overview consumes.

### `pcb/`

- Entry: `pcb.build(circuit, mapping)` returns `PCBBuildResult`
  (`src/schematika/pcb/model.py:169`).
- Carries `columns: tuple[(column_key, Circuit), ...]` — circuits laid
  out as KiCad netlist input.
- Pin identifiers are KiCad pin numbers as strings.
- Components identified by part_ref (`"J1"`, `"U1"`).

### `cable/`

- Entry: `cable.build_cable_drawings(connections, devices, ...)` returns
  `list[CableDrawing]`. Function is at
  `src/schematika/cable/builder.py:240`; the `CableDrawing` dataclass
  is at `src/schematika/cable/model.py:82`.
- `CableDrawing` carries:
  - `cable: CableDef` — designator, wire count, gauge, colors, length.
  - `connectors: tuple[CableConnector, ...]` — exactly two.
  - `connections: tuple[CableConnection, ...]` — per-wire mapping
    `(from_connector, from_pin, cable, wire, to_connector, to_pin)`.

### `block/` — out of scope

The user has stated that `schematika.block` is a trial, not part of the
production data flow. It IS imported by `project.py` (via the optional
`add_block_diagram()` path and `_block_results`), so the package isn't
unreferenced — but no consumer in production builds uses it. Overview
must not consume `BlockDiagram` data. Containment for Overview comes
from the consumer-supplied dict, not from any `BlockDiagram`.

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
| Signal kind (`power` / `signal`, growing on demand) | Not in data | Consumer-supplied classifier callable + palette dict, with name-pattern default |
| Port ordering hints | Insertion order today | Optional per-unit hint, deferrable to v0.5+ |

These gaps are inputs to Overview, not refactors of other modules. The
"shared data module" idea (canonical types in `core/datamodel/` adopted
by every domain) is deliberately deferred — it would be designing the
shared shapes against one example. Re-evaluate after the first end-to-end
v0 lands.

## Reusable primitives in `core/`

Two existing pieces in `src/schematika/core/` are directly reusable by
Overview:

- `core/validation.py` exposes `ValidationResult`
  (`passed: bool`, `warnings: list[str]`, `errors: list[str]`),
  `boxes_overlap()`, `check_text_overlap()`, `collect_elements()` —
  the same types and helpers `pid/validation.py` consumes. The
  Overview validator should use these, not define its own.
- `core/exceptions.py` exposes `CircuitValidationError(ValueError)`
  as the electrical domain base. The PID domain has its own base in
  `pid/errors.py` (`PIDError(ValueError)`). Overview should mirror that
  pattern with `OverviewError(ValueError)` in `overview/errors.py`.
