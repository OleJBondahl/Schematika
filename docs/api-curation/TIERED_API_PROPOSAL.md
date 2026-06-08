# Tiered public API — proposal

**Status:** DRAFT — awaiting user sign-off (phase 4).
**Generated:** 2026-04-25
**Sources:** `docs/api-curation/{top,electrical,electrical-symbols,pcb,pid,cable,catalog,core,block}.md`

## Tier rules

- **Tier 1 — strict (`schematika.<domain>`):** aux-cabinet-used + symbol factories (port-ID contract) + exception base classes. Full Google docstrings, examples blocks, `--doctest-modules`, ratchet on every gate.
- **Tier 2 — advanced (`schematika.<domain>.advanced`):** everything currently DEMOTE_CANDIDATE. Public, but lighter docstring bar, no doctest requirement, free to break minor.
- **Tier 3 — private (no re-export, no `__all__`):** everything currently MAKE_INTERNAL. Names without `_` prefix are fine; they just don't appear in any `__all__`.
- **REMOVE:** outright deletion of `block/` package and consumer's `block_diagram.py`.

The oracle for tier 1 is `auxillary_cabinet_v3` import grep, plus the two policy carve-outs (port-ID symbol factories, exception base classes).

---

## Per-package tier 1 (strict surface)

### `schematika` (top)

```python
# src/schematika/__init__.py
__all__ = [
    # everything in schematika.electrical.__all__ tier-1 — explicit, not wildcard
    *schematika.electrical.__all__,
]
# Project remains accessible via `from schematika.project import Project`
# (deliberate — Project is the orchestrator, not a domain primitive)
```

- **Tier 1:** wildcard from electrical (kept), `from schematika.project import Project` (kept as-is).
- **Tier 2:** `schematika.overview` (planned, not yet shipped).

### `schematika.electrical` — tier 1 (76 names)

Aux-cabinet-used + port-ID factories + exceptions.

**Core builder + render (10):**
`Circuit`, `CircuitBuilder`, `BuildResult`, `BridgeMode`, `merge_circuits`, `merge_build_results`, `render_system`, `draw_wire`, `add_wire_labels_to_circuit`, `log_connection`

**Symbol factories — port-ID contract (21):** see `schematika.electrical.symbols` below. All re-exported at `schematika.<name>` via wildcard.

**Layout constants (10):**
`CIRCUIT_SPACING`, `CIRCUIT_SPACING_NARROW`, `CIRCUIT_SPACING_WIDE`, `DEFAULT_POLE_SPACING`, `GRID_SIZE`, `SPACING_COMPACT`, `SPACING_DEFAULT`, `SPACING_NARROW`, `SPACING_STANDARD`, `THERMAL_OVERLOAD_PINS`

**Tag/wire conventions (3):**
`PinPrefix`, `StandardTags`, `WireLabels`

**State (2):**
`GenerationState`, `create_initial_state`

**Autonumbering + counters (3):**
`create_autonumberer`, `apply_start_indices`, `set_terminal_counter`

**Field-device data model (8):**
`InternalDevice`, `Terminal`, `CableData`, `ConnectorData`, `DeviceCable`, `DeviceTemplate`, `FieldDevice`, `PinDef`

**Field-device generators (1):**
`generate_field_connections`

**PLC resolver (5):**
`PlcModuleType`, `PlcRack`, `extract_plc_connections_from_registry`, `generate_plc_report_rows`, `resolve_plc_references`

**Exception contract (6 — policy carve-out):**
`CircuitValidationError`, `ComponentNotFoundError`, `PortNotFoundError`, `TagReuseError`, `TerminalReuseError`, `WireLabelMismatchError`

**Submodule reference (1):**
`symbols`

### `schematika.electrical.advanced` — tier 2 (41 names)

Descriptors mini-API, type aliases, pin-tuple constants, internal utilities, and inter-device helpers. All currently `DEMOTE_CANDIDATE` per matrix.

```
add_symbol, ComponentRef, PortRef, merge_reuse_tags,
build_from_descriptors, comp, ref, term, wire,
SymbolFactory, LabelPosition, Position, Side, StandardCircuitKeys,
CB_2P_PINS, CB_3P_PINS, COIL_PINS, CONTACTOR_3P_PINS, NC_CONTACT_PINS, NO_CONTACT_PINS,
get_tag_number, next_tag, next_terminal_pins,
export_terminal_list, finalize_terminal_csv, merge_terminal_csv,
fixed_tag, get_terminal_counter, merge_terminals, natural_sort_key, set_tag_counter,
export_registry_to_csv, get_registry,
DeviceEntry, FixedPin, PrefixedPin, SequentialPin,
EMPTY_TEMPLATE,
BridgeRange, ConnectionDef, expand_range_to_pins, generate_internal_connections_data,
get_connection_groups_for_terminal, parse_terminal_pins_from_csv, update_csv_with_internal_connections,
PlcDesignation
```

### `schematika.electrical.symbols` — tier 1 (21 factories, port-ID contract)

```
block, breaker, coil, connector_pin, contactor, ct, ct_assembly,
estop, estop_button, fuse, motor, nc_contact, no_contact, psu,
ref (alias `ref_symbol` at electrical top-level), spdt_contact,
terminal, terminal_box, thermal_overload, turn_actuator, turn_switch
```

Add `connector_pin` to `electrical.__all__` so it's surfaced at `schematika.connector_pin` for consistency.

---

### `schematika.pid` — tier 1 (21 names)

`pid/__init__.py` currently has no `__all__`. A1 adds an explicit one limited to:

**Builder (1):**
`PIDBuilder` (PROMOTE — used by consumer via deep path; surface at `schematika.pid.PIDBuilder`)

**Symbol factories — port-ID contract (15):**
`ball_valve`, `centrifugal_pump`, `check_valve`, `control_valve`, `gate_valve`, `globe_valve`, `heat_exchanger`, `instrument_bubble`, `pipe_cap`, `pipe_reducer`, `pipe_segment`, `pipe_tee`, `positive_displacement_pump`, `tank`, `three_way_valve`

**Layout constants (4):**
`INSTRUMENT_BUBBLE_RADIUS`, `PID_MIN_EQUIPMENT_GAP`, `PID_MIN_LEG_SPACING`, `PID_STUB_LENGTH`

**Exception contract (carve-out):** `pid/errors.py:PIDError` if not already exposed.

### `schematika.pid.advanced` — tier 2 (38 dimensional constants)

All `pid/constants.py` constants not in tier 1: `PID_*` constants, `ISA_*` dicts, `validate_isa_letters`, `VALVE_SIZE`, etc. (see `pid.md` rows 9-49).

### `schematika.pid` — tier 3 (private, 18 names)

Drop from `pid/__init__.py`'s `__all__` — accessible only via deep paths, no public guarantee:
- From `pid.connections`: `PNEUMATIC_LINE`, `PROCESS_PIPE`, `SIGNAL_LINE`, `PipeStyle`, `create_flow_arrow`, `manhattan_route`, `render_pipe`
- From `pid.diagram`: `PIDDiagram`, `add_equipment`, `merge_diagrams`, `render_pid`
- From `pid.builder`: `EquipmentSpec`, `PIDBuildResult`, `PipeSpec`
- From `pid.layout`: `Placement`, `resolve_placements`
- From `pid.validation`: `ValidationResult`, `validate_pid`

`ValidationResult` re-export from `core/validation.py` is dropped (currently leaks core type).

---

### `schematika.pcb` — tier 1 (2 names)

**Entry point + base error (policy carve-out):**
`build`, `PCBBuildError`

### `schematika.pcb.advanced` — tier 2 (16 names)

Everything else from `pcb/__init__.py:__all__`: page-size constants, fine-grained errors, dataclasses (`PCBBuildResult`, `SymbolMap`, etc.).

This implements the "deliberate-new-module-aspirational-KEEP" decision: the `__all__` is preserved but the strict surface is just the entry point.

---

### `schematika.cable` — tier 1 (3 names) — **needs your call**

Default proposal:
**Entry points:** `build_cable_drawings`, `cable_run_to_drawing`, `render_cable_svg`

### `schematika.cable.advanced` — tier 2 (4 dataclasses)

`CableConnection`, `CableConnector`, `CableDef`, `CableDrawing`

Alternative (option B in your phase-4 review): tier 1 = empty, all 7 → tier 2.
Recommendation: keep the 3 functions in tier 1 (they're the documented entry points even though aux cabinet doesn't reach them yet).

---

### `schematika.catalog` — tier 1 (5 names)

`catalog/__init__.py` currently has no `__all__`. A1 adds an explicit one:

**Used by consumer (4):**
`CatalogDevice`, `InstrumentSpec`, `ProcessSpec`, `DeviceCatalog`

**Exception contract (carve-out):**
`CatalogError` — currently NOT re-exported from `catalog/__init__.py`. A1 should expose it.

### `schematika.catalog` — tier 3 (private, 3)

Drop from facade: `ElectricalSpec`, `CableRegistry`, `CableSpec`. Accessible only via `from schematika.catalog.cables import …`.

---

### `schematika.core` — tier 3 (all 21 private)

Add `__all__ = []` to `core/__init__.py`. Documented as internal-by-convention (CLAUDE.md invariant 1: `core/` is I/O-free foundation, not user surface).

The 6 exception classes (`CircuitValidationError`, etc.) remain accessible via `schematika.<name>` because they're re-exported through `electrical.__all__` (tier 1). Adding `__all__ = []` to `core` does not break that re-export path.

---

## `block` — REMOVE

Delete `src/schematika/block/` and `auxillary_cabinet_v3/src/block_diagram.py`. Memory says block is dead and the consumer file using it is also dead; the matrix's flagged conflict resolves to "delete both."

---

## Tier-1 totals (the strict-tier work for A1/A2/A3)

| Package | Tier 1 count |
|---|---:|
| top | 1 (Project remains via `schematika.project`) |
| electrical (incl. exceptions, factories) | 76 |
| electrical.symbols | (subset of electrical.__all__ — 21) |
| pid | 21 |
| pcb | 2 |
| cable | 3 |
| catalog | 5 |
| **total tier-1 names** | **~108** |

Down from 309 in the union of all `__all__` today. A1 generates a `@public` decorator and writes the explicit `__all__` lists; A2 backfills Google docstrings on these 108; A3 adds Examples blocks + `--doctest-modules` for tier 1.

---

## Sign-off needed

**Confirm or correct:**
1. Tier-1 lists above (per-package).
2. `cable` choice: 3-function tier-1 (default) vs. all-7 tier-2.
3. `descriptors` (`comp`/`ref`/`term`/`wire`/`build_from_descriptors`) → tier 2 (default) vs. tier 1 (if it's the future fluent-builder API you want to promote).
4. `block` → REMOVE (default).
5. The two carve-outs: port-ID symbol factories always tier 1, exception base classes always tier 1.

If "go", phase 5 dispatches a subagent that:
- Creates `electrical/advanced.py`, `pid/advanced.py`, `pcb/advanced.py`, `cable/advanced.py` re-export modules.
- Edits each domain's `__init__.py` to the tier-1-only `__all__`.
- Adds `__all__ = []` to `core/__init__.py`.
- Deletes `src/schematika/block/` and consumer's `block_diagram.py`.
- Runs the canonical consumer build before/after each `src/` edit.
- One commit per package.
