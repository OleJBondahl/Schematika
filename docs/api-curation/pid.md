# API curation — pid

**Source:** `src/schematika/pid/__init__.py`, `pid/constants.py`, `pid/connections.py`, `pid/builder.py`, `pid/diagram.py`, `pid/layout.py`, `pid/validation.py`, `pid/symbols/__init__.py`.
**Generated:** 2026-04-25 (Wave A0 phase 3)
**Status:** AWAITING USER REVIEW — fill the "Your decision" column.

> Notes from generation:
> - **`pid/__init__.py` has NO `__all__`.** The `In __all__ today` column is therefore computed via the "leaked-public scan": every top-level non-underscored name imported by `pid/__init__.py` is treated as "leaked-public".
> - `pid/constants.py` **does** have an explicit `__all__` listing constants and re-exports. Symbols defined in `pid/constants.py` but **not** in its `__all__` (none found in this scan) would be flagged.
> - Consumer (`auxillary_cabinet_v3/src/pid.py`) imports from `schematika.pid.builder`, `schematika.pid.constants`, and `schematika.pid.symbols` — bypassing the package-level facade entirely. This means the package-level imports in `pid/__init__.py` are not actually exercised by the consumer.

## Inventory

| # | Symbol | Kind | Defined in | In `__all__` today | Consumer uses | Examples / docs use | Recommendation | Your decision |
|---|---|---|---|---|---|---|---|---|
| 1 | `PNEUMATIC_LINE` | constant | `pid/connections.py:44` | leaked-public | no | no | MAKE_INTERNAL | _ |
| 2 | `PROCESS_PIPE` | constant | `pid/connections.py:40` | leaked-public | no | no | MAKE_INTERNAL | _ |
| 3 | `SIGNAL_LINE` | constant | `pid/connections.py:41` | leaked-public | no | no | MAKE_INTERNAL | _ |
| 4 | `PipeStyle` | dataclass | `pid/connections.py:27` | leaked-public | no | no | MAKE_INTERNAL | _ |
| 5 | `create_flow_arrow` | function | `pid/connections.py:86` | leaked-public | no | no | MAKE_INTERNAL | _ |
| 6 | `manhattan_route` | function | `pid/connections.py:54` | leaked-public | no | no | MAKE_INTERNAL | _ |
| 7 | `render_pipe` | function | `pid/connections.py:152` | leaked-public | no | no | MAKE_INTERNAL | _ |
| 8 | `INSTRUMENT_BUBBLE_RADIUS` | constant | `pid/constants.py:161` | yes (in `pid/constants.py:__all__`) | yes (`pid.py:15`) | no | KEEP | _ |
| 9 | `ISA_FIRST_LETTER` | dict constant | `pid/constants.py:208` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 10 | `ISA_SUCCEEDING_LETTERS` | dict constant | `pid/constants.py:237` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 11 | `PID_DEFAULT_PIPE_LENGTH` | constant | `pid/constants.py:200` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 12 | `PID_FLOW_ARROW_SIZE` | constant | `pid/constants.py:197` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 13 | `PID_LABEL_OFFSET` | constant | `pid/constants.py:205` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 14 | `PID_LINE_WEIGHT` | constant | `pid/constants.py:150` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 15 | `PID_MIN_EQUIPMENT_GAP` | constant | `pid/constants.py:203` | yes | yes (`pid.py:15`) | no | KEEP | _ |
| 16 | `PID_MIN_LEG_SPACING` | constant | `pid/constants.py:204` | yes | yes (`pid.py:15`) | no | KEEP | _ |
| 17 | `PID_OPEN_TANK_DASH` | constant | `pid/constants.py:158` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 18 | `PID_PNEUMATIC_DASH` | constant | `pid/constants.py:155` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 19 | `PID_PUMP_RADIUS` | constant | `pid/constants.py:164` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 20 | `PID_SIGNAL_DASH` | constant | `pid/constants.py:154` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 21 | `PID_SIGNAL_LINE_WEIGHT` | constant | `pid/constants.py:151` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 22 | `PID_STUB_LENGTH` | constant | `pid/constants.py:163` | yes | yes (`pid.py:15`) | no | KEEP | _ |
| 23 | `PID_TAG_OFFSET` | constant | `pid/constants.py:181` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 24 | `PID_TEXT_SIZE_BUBBLE` | constant | `pid/constants.py:176` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 25 | `PID_TEXT_SIZE_PIPE` | constant | `pid/constants.py:178` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 26 | `PID_TEXT_SIZE_TAG` | constant | `pid/constants.py:177` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 27 | `VALVE_SIZE` | constant | `pid/constants.py:162` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 28 | `validate_isa_letters` | function | `pid/constants.py:259` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 29 | `PID_ACTUATOR_STEM_HEIGHT` | constant | `pid/constants.py:172` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 30 | `PID_ACTUATOR_TRI_HEIGHT` | constant | `pid/constants.py:173` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 31 | `PID_CAP_HALF_HEIGHT` | constant | `pid/constants.py:190` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 32 | `PID_EQUIPMENT_STROKE` | constant | `pid/constants.py:149` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 33 | `PID_HX_RADIUS` | constant | `pid/constants.py:167` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 34 | `PID_HX_TUBE_LENGTH_FACTOR` | constant | `pid/constants.py:194` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 35 | `PID_HX_TUBE_OFFSET` | constant | `pid/constants.py:193` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 36 | `PID_LABEL_PIPE_OFFSET` | constant | `pid/constants.py:182` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 37 | `PID_REDUCER_INLET_HALF_H` | constant | `pid/constants.py:188` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 38 | `PID_REDUCER_LENGTH` | constant | `pid/constants.py:187` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 39 | `PID_REDUCER_OUTLET_HALF_H` | constant | `pid/constants.py:189` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 40 | `PID_TANK_HALF_HEIGHT` | constant | `pid/constants.py:166` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 41 | `PID_TANK_HALF_WIDTH` | constant | `pid/constants.py:165` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 42 | `PID_TEE_BRANCH_LENGTH` | constant | `pid/constants.py:185` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 43 | `PID_TEE_HALF_LENGTH` | constant | `pid/constants.py:184` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 44 | `PID_VALVE_BALL_RADIUS` | constant | `pid/constants.py:171` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 45 | `PID_VALVE_CENTER_RADIUS` | constant | `pid/constants.py:170` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 46 | `GRID_SIZE` (re-export from `core.constants`) | constant | `core/constants.py` | yes (in `pid/constants.py:__all__`) | no (consumer uses `from schematika import GRID_SIZE`) | no | DEMOTE_CANDIDATE (duplicate of top-level GRID_SIZE) | _ |
| 47 | `LINE_WIDTH_THIN` (re-export) | constant | `core/constants.py` | yes (in `pid/constants.py:__all__`) | no | no | DEMOTE_CANDIDATE | _ |
| 48 | `TEXT_FONT_FAMILY` (re-export) | constant | `core/constants.py` | yes (in `pid/constants.py:__all__`) | no | no | DEMOTE_CANDIDATE | _ |
| 49 | `TEXT_SIZE_MAIN` (re-export) | constant | `core/constants.py` | yes (in `pid/constants.py:__all__`) | no | no | DEMOTE_CANDIDATE | _ |
| 50 | `PIDDiagram` | dataclass | `pid/diagram.py:12` | leaked-public | no | no | MAKE_INTERNAL | _ |
| 51 | `add_equipment` | function | `pid/diagram.py:26` | leaked-public | no | no | MAKE_INTERNAL | _ |
| 52 | `merge_diagrams` | function | `pid/diagram.py:43` | leaked-public | no | no | MAKE_INTERNAL | _ |
| 53 | `render_pid` | function | `pid/diagram.py:49` | leaked-public | no | no | MAKE_INTERNAL | _ |
| 54 | `EquipmentSpec` | dataclass | `pid/builder.py:40` | leaked-public | no | no | MAKE_INTERNAL | _ |
| 55 | `PIDBuildResult` | dataclass | `pid/builder.py:76` | leaked-public | no | no | MAKE_INTERNAL | _ |
| 56 | `PIDBuilder` | class | `pid/builder.py:104` | leaked-public | yes (`pid.py:14` — but via `from schematika.pid.builder import PIDBuilder`, NOT from `schematika.pid`) | no | PROMOTE (used externally; should add `__all__` to `pid/__init__.py` and include) | _ |
| 57 | `PipeSpec` | dataclass | `pid/builder.py:64` | leaked-public | no | no | MAKE_INTERNAL | _ |
| 58 | `Placement` | dataclass | `pid/layout.py:13` | leaked-public | no | no | MAKE_INTERNAL | _ |
| 59 | `resolve_placements` | function | `pid/layout.py:22` | leaked-public | no | no | MAKE_INTERNAL | _ |
| 60 | `ValidationResult` | dataclass | `core/validation.py:24` (re-imported) | leaked-public | no | no | MAKE_INTERNAL (note: this is re-imported from `core.validation` — leaving it leaks core) | _ |
| 61 | `validate_pid` | function | `pid/validation.py:85` | leaked-public | no | no | MAKE_INTERNAL | _ |
| 62 | `ball_valve` | symbol factory | `pid/symbols/valves.py:179` | leaked-public (also in `pid/symbols/__init__.py` though no `__all__` there either) | no | no | KEEP (port-ID contract — extends to PID symbols) | _ |
| 63 | `centrifugal_pump` | symbol factory | `pid/symbols/process.py:75` | leaked-public | yes (`pid.py:21`) | no | KEEP (port-ID contract) | _ |
| 64 | `check_valve` | symbol factory | `pid/symbols/valves.py:155` | leaked-public | yes (`pid.py:21`) | no | KEEP (port-ID contract) | _ |
| 65 | `control_valve` | symbol factory | `pid/symbols/valves.py:109` | leaked-public | no | no | KEEP (port-ID contract) | _ |
| 66 | `gate_valve` | symbol factory | `pid/symbols/valves.py:73` | leaked-public | yes (`pid.py:21`) | no | KEEP (port-ID contract) | _ |
| 67 | `globe_valve` | symbol factory | `pid/symbols/valves.py:85` | leaked-public | no | no | KEEP (port-ID contract) | _ |
| 68 | `heat_exchanger` | symbol factory | `pid/symbols/vessels.py:114` | leaked-public | no | no | KEEP (port-ID contract) | _ |
| 69 | `instrument_bubble` | symbol factory | `pid/symbols/instruments.py:27` | leaked-public | no | no | KEEP (port-ID contract) | _ |
| 70 | `pipe_cap` | symbol factory | `pid/symbols/piping.py:125` | leaked-public | no | no | KEEP (port-ID contract) | _ |
| 71 | `pipe_reducer` | symbol factory | `pid/symbols/piping.py:76` | leaked-public | no | no | KEEP (port-ID contract) | _ |
| 72 | `pipe_segment` | symbol factory | `pid/symbols/piping.py:30` | leaked-public | yes (`pid.py:21`) | no | KEEP (port-ID contract) | _ |
| 73 | `pipe_tee` | symbol factory | `pid/symbols/piping.py:57` | leaked-public | no | no | KEEP (port-ID contract) | _ |
| 74 | `positive_displacement_pump` | symbol factory | `pid/symbols/process.py:90` | leaked-public | no | no | KEEP (port-ID contract) | _ |
| 75 | `tank` | symbol factory | `pid/symbols/vessels.py:32` | leaked-public | no | no | KEEP (port-ID contract) | _ |
| 76 | `three_way_valve` | symbol factory | `pid/symbols/valves.py:197` | leaked-public | yes (`pid.py:21`) | no | KEEP (port-ID contract) | _ |

## Recommendation legend

- **KEEP** — already in `__all__` and used externally; leave as-is.
- **PROMOTE** — used externally but not in `__all__` (or "leaked-public"); add to `__all__`.
- **DEMOTE_CANDIDATE** — in `__all__` today, no external usage. User decides if aspirational/forward-API or genuinely unused-and-internal.
- **MAKE_INTERNAL** — leaked-public with no usage. Rename `_foo` or move to private module.
- **REMOVE** — dead module / dead symbol.
- **KEEP (port-ID contract)** — symbol factories under `pid/symbols/` (extending the rule from CLAUDE.md to the PID domain).

## Summary

- Total symbols inspected: 76
- KEEP: 4 (`INSTRUMENT_BUBBLE_RADIUS`, `PID_MIN_EQUIPMENT_GAP`, `PID_MIN_LEG_SPACING`, `PID_STUB_LENGTH`)
- KEEP (port-ID contract): 15 (all PID symbol factories — rows 62-76)
- PROMOTE: 1 (`PIDBuilder` — used externally but `pid/__init__.py` has no `__all__`; A1 should add one and include it)
- DEMOTE_CANDIDATE: 38 (most `pid/constants.py` constants — they are listed in `pid/constants.py:__all__` but no consumer uses them)
- MAKE_INTERNAL: 18 (most names from `pid/connections.py`, `pid/builder.py`, `pid/diagram.py`, `pid/layout.py`, `pid/validation.py` — leaked into `pid` namespace via `from .x import …` but `pid/__init__.py` has no `__all__`)
- REMOVE: 0

> Notes for review:
> 1. **The biggest finding: `pid/__init__.py` has no `__all__` at all.** Every name `from .connections import …`, `from .diagram import …`, etc. is exposed by accident. A1 should add an explicit `__all__` covering the names the user wants to keep.
> 2. The consumer accesses `PIDBuilder`, the symbol factories, and the four KEEP constants via fully-qualified module paths (`from schematika.pid.builder import PIDBuilder`), not via `from schematika.pid import …`. The user may want to standardise this — either promote everything the consumer actually uses to the package top-level, or accept the deeper paths as the public surface.
> 3. The symbol factories (rows 62-76) are extended KEEP under the port-ID contract by analogy with electrical/symbols. Confirm this rule applies to PID.
> 4. Many of the dimensional constants (e.g. `PID_TANK_HALF_HEIGHT`, `PID_HX_TUBE_OFFSET`) feel like internal layout details. Strong demotion candidates.
> 5. `ValidationResult` is re-exported from `core/validation.py` into `pid/__init__.py` — this leaks a core type. Phase 5 should decide whether to expose it deliberately or drop the re-export.
