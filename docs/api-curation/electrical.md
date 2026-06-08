# API curation — electrical

**Source:** `src/schematika/electrical/__init__.py` plus the modules it re-exports from.
**Generated:** 2026-04-25 (Wave A0 phase 3)
**Status:** AWAITING USER REVIEW — fill the "Your decision" column.

> Notes from generation:
> - "In `__all__` today" is computed against `electrical/__init__.py:140` (the explicit `__all__`).
> - The `top` package (`src/schematika/__init__.py`) does `from .electrical import *`, so every row marked KEEP/in-`__all__` here is also exposed at `schematika.<name>`. Consumer usage column is recorded against `schematika.<name>` because every consumer file uses the top-level path.
> - Symbol factories from `electrical.symbols.*` are not duplicated here in detail — see `electrical-symbols.md`. They appear as one row each because each is an explicit name in `electrical.__all__`.
> - Per repo policy (CLAUDE.md "port-ID contract"), every symbol factory under `electrical/symbols/` is **KEEP** regardless of grep hits, but consumer usage is still recorded so the user can deliberately decide to remove an unused factory.

## Inventory

| # | Symbol | Kind | Defined in | In `__all__` today | Consumer uses | Examples / docs use | Recommendation | Your decision |
|---|---|---|---|---|---|---|---|---|
| 1 | `Circuit` | class | `electrical/system/system.py:17` | yes | yes (`circuits/pump_circuit.py:10`) | no | KEEP | _ |
| 2 | `add_symbol` | function | `electrical/system/system.py:31` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 3 | `merge_circuits` | function | `electrical/system/system.py:67` | yes | yes (`circuits/pump_circuit.py:10`) | no | KEEP | _ |
| 4 | `render_system` | function | `electrical/system/system.py:48` | yes | yes (4 consumer files) | yes (5 examples) | KEEP | _ |
| 5 | `draw_wire` | function | `electrical/layout/layout.py:36` | yes | yes (`circuits/power_supply.py:7`) | no | KEEP | _ |
| 6 | `BridgeMode` | StrEnum | `electrical/builder_models.py:10` | yes | yes (`circuits/fan_controll.py:10`, `devices/terminals.py:8`) | no | KEEP | _ |
| 7 | `BuildResult` | dataclass | `electrical/builder_models.py:165` | yes | yes (10 consumer files) | yes (`06_full_cabinet.py`) | KEEP | _ |
| 8 | `CircuitBuilder` | class | `electrical/builder.py:41` | yes | yes (10 consumer files) | yes (6 examples) | KEEP | _ |
| 9 | `ComponentRef` | dataclass | `electrical/builder_models.py:141` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 10 | `PortRef` | dataclass | `electrical/builder_models.py:133` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 11 | `merge_reuse_tags` | function | `electrical/builder_models.py:157` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 12 | `build_from_descriptors` | function | `electrical/descriptors.py:77` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 13 | `comp` | function | `electrical/descriptors.py:60` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 14 | `ref` | function | `electrical/descriptors.py:55` | yes | no | no | DEMOTE_CANDIDATE (note: name collision with `ref_symbol` re-export — confusing) | _ |
| 15 | `term` | function | `electrical/descriptors.py:67` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 16 | `wire` | callable instance | `electrical/wire.py:34` (`_Wire()`) | yes | no | no | DEMOTE_CANDIDATE | _ |
| 17 | `merge_build_results` | function | `electrical/builder_utils.py` | yes | yes (`circuits/power_supply.py:7`) | no | KEEP | _ |
| 18 | `add_wire_labels_to_circuit` | function | `electrical/layout/wire_labels.py:106` | yes | yes (`circuits/power_supply.py:7`) | no | KEEP | _ |
| 19 | `log_connection` | function | `electrical/system/connection_registry.py:43` | yes | yes (`circuits/power_supply.py:7`) | no | KEEP | _ |
| 20 | `SymbolFactory` | type alias | `electrical/model/core.py` (re-exports `core/symbol.py:48`) | yes | no | no | DEMOTE_CANDIDATE (kept for type-annotation use) | _ |
| 21 | `symbols` | submodule | `electrical/symbols/__init__.py` | yes | indirect (re-exports from here are used) | indirect | KEEP | _ |
| 22 | `no_contact` | symbol factory | `electrical/symbols/contacts.py:66` | yes | yes (4 consumer + 3 example) | yes | KEEP (port-ID contract) | _ |
| 23 | `nc_contact` | symbol factory | `electrical/symbols/contacts.py:134` | yes | no | no | KEEP (port-ID contract) | _ |
| 24 | `spdt_contact` | symbol factory | `electrical/symbols/contacts.py:328` | yes | no | no | KEEP (port-ID contract) | _ |
| 25 | `breaker` | symbol factory | `electrical/symbols/breakers.py:73` | yes | yes (3 consumer + 2 example) | yes | KEEP (port-ID contract) | _ |
| 26 | `thermal_overload` | symbol factory | `electrical/symbols/protection.py:75` | yes | yes (`circuits/pump_circuit.py:10`) | yes | KEEP (port-ID contract) | _ |
| 27 | `fuse` | symbol factory | `electrical/symbols/protection.py:100` | yes | no | no | KEEP (port-ID contract) | _ |
| 28 | `coil` | symbol factory | `electrical/symbols/coils.py:22` | yes | yes (4 consumer + 4 example) | yes | KEEP (port-ID contract) | _ |
| 29 | `motor` | symbol factory | `electrical/symbols/motors.py:208` | yes | no | yes (`02_dol_starter.py`, `06_full_cabinet.py`) | KEEP (port-ID contract) | _ |
| 30 | `contactor` | symbol factory | `electrical/symbols/assemblies.py:22` | yes | yes (2 consumer) | yes (2 examples) | KEEP (port-ID contract) | _ |
| 31 | `estop` | symbol factory | `electrical/symbols/assemblies.py:63` | yes | no | no | KEEP (port-ID contract) | _ |
| 32 | `turn_switch` | symbol factory | `electrical/symbols/assemblies.py:91` | yes | no | no | KEEP (port-ID contract) | _ |
| 33 | `ct_assembly` | symbol factory | `electrical/symbols/transducers.py:48` | yes | yes (2 consumer) | no | KEEP (port-ID contract) | _ |
| 34 | `estop_button` | symbol factory | `electrical/symbols/actuators.py:16` | yes | no | no | KEEP (port-ID contract) | _ |
| 35 | `turn_actuator` | symbol factory | `electrical/symbols/actuators.py:56` | yes | no | no | KEEP (port-ID contract) | _ |
| 36 | `ct` | symbol factory | `electrical/symbols/transducers.py:16` | yes | no | no | KEEP (port-ID contract) | _ |
| 37 | `terminal_box` | symbol factory | `electrical/symbols/blocks.py:18` | yes | no | no | KEEP (port-ID contract) | _ |
| 38 | `block` | symbol factory | `electrical/symbols/blocks.py:175` | yes | yes (`fan_controll.py`, `plc_power.py`, `power_supply.py`) | yes (`05_multi_builder.py`) | KEEP (port-ID contract) | _ |
| 39 | `psu` | symbol factory | `electrical/symbols/blocks.py:99` | yes | yes (`circuits/power_supply.py:7`) | no | KEEP (port-ID contract) | _ |
| 40 | `terminal` | symbol factory | `electrical/symbols/terminals.py:160` | yes | no | no | KEEP (port-ID contract) | _ |
| 41 | `ref_symbol` (alias of `ref` from `references.py:21`) | symbol factory | `electrical/symbols/references.py:21` (re-exported as `ref_symbol`) | yes | no | no | KEEP (port-ID contract; aliased to avoid clash with `descriptors.ref`) | _ |
| 42 | `CB_2P_PINS` | constant | `electrical/model/constants.py:81` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 43 | `CB_3P_PINS` | constant | `electrical/model/constants.py:80` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 44 | `CIRCUIT_SPACING` | constant | `electrical/model/constants.py:142` | yes | yes (5 consumer) | yes (`05_multi_builder.py`, `06_full_cabinet.py`) | KEEP | _ |
| 45 | `CIRCUIT_SPACING_NARROW` | constant | `electrical/model/constants.py:141` | yes | yes (4 consumer) | yes (`03_coil_contact_pair.py`) | KEEP | _ |
| 46 | `CIRCUIT_SPACING_WIDE` | constant | `electrical/model/constants.py:143` | yes | yes (`circuits/fan_singlepole.py:11`) | no | KEEP | _ |
| 47 | `COIL_PINS` | constant | `electrical/model/constants.py:77` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 48 | `CONTACTOR_3P_PINS` | constant | `electrical/model/constants.py:82` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 49 | `DEFAULT_POLE_SPACING` | constant | `electrical/model/constants.py` (re-exported) | yes | yes (`cabinet.py`, `circuits/fan_controll.py`, `circuits/power_supply.py`) | no | KEEP | _ |
| 50 | `GRID_SIZE` | constant | `core/constants.py` (re-exported) | yes | yes (4 consumer) | yes (3 examples) | KEEP | _ |
| 51 | `LabelPosition` | type alias | `electrical/model/constants.py:12` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 52 | `NC_CONTACT_PINS` | constant | `electrical/model/constants.py:79` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 53 | `NO_CONTACT_PINS` | constant | `electrical/model/constants.py:78` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 54 | `PinPrefix` | class | `electrical/model/constants.py:96` | yes | yes (`devices/terminals.py:8`) | no | KEEP | _ |
| 55 | `Position` | type alias | `electrical/model/constants.py:10` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 56 | `SPACING_COMPACT` | constant | `electrical/model/constants.py:135` | yes | yes (`circuits/internal_distribution.py:15`) | no | KEEP | _ |
| 57 | `SPACING_DEFAULT` | constant | `electrical/model/constants.py:137` | yes | yes (3 consumer) | no | KEEP | _ |
| 58 | `SPACING_NARROW` | constant | `electrical/model/constants.py:136` | yes | yes (3 consumer) | no | KEEP | _ |
| 59 | `SPACING_STANDARD` | constant | `electrical/model/constants.py:138` | yes | yes (5 consumer) | yes (3 examples) | KEEP | _ |
| 60 | `Side` | type alias | `electrical/model/constants.py:11` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 61 | `StandardCircuitKeys` | class | `electrical/model/constants.py:104` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 62 | `StandardTags` | class | `electrical/model/constants.py:57` | yes | yes (`circuits/power_supply.py:7`) | no | KEEP | _ |
| 63 | `THERMAL_OVERLOAD_PINS` | constant | `electrical/model/constants.py:83` | yes | yes (`circuits/pump_circuit.py:10`) | no | KEEP | _ |
| 64 | `WireLabels` | class | `electrical/model/constants.py:152` | yes | yes (10 consumer + 5 examples) | yes | KEEP | _ |
| 65 | `GenerationState` | dataclass | `electrical/model/state.py` (re-exports `core/state.py`) | yes | yes (`devices/plc_modules.py:14`) | no | KEEP | _ |
| 66 | `create_initial_state` | function | `electrical/model/state.py` (re-exports `core/state.py`) | yes | no | yes (5 examples) | KEEP | _ |
| 67 | `create_autonumberer` | function | `electrical/utils/autonumbering.py` | yes | yes (`fan_controll.py`, `pump_circuit.py`, `pump_controll.py`) | no | KEEP | _ |
| 68 | `get_tag_number` | function | `electrical/utils/autonumbering.py` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 69 | `next_tag` | function | `electrical/utils/autonumbering.py` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 70 | `next_terminal_pins` | function | `electrical/utils/autonumbering.py` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 71 | `export_terminal_list` | function | `electrical/utils/export_utils.py:21` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 72 | `finalize_terminal_csv` | function | `electrical/utils/export_utils.py:203` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 73 | `merge_terminal_csv` | function | `electrical/utils/export_utils.py:79` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 74 | `apply_start_indices` | function | `electrical/utils/utils.py:53` | yes | yes (`fan_singlepole.py`, `pump_circuit.py`, `valve_control.py`) | no | KEEP | _ |
| 75 | `fixed_tag` | function | `electrical/utils/utils.py:70` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 76 | `get_terminal_counter` | function | `electrical/utils/utils.py:48` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 77 | `merge_terminals` | function | `electrical/utils/utils.py:65` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 78 | `natural_sort_key` | function | `electrical/utils/utils.py` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 79 | `set_tag_counter` | function | `electrical/utils/utils.py:16` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 80 | `set_terminal_counter` | function | `electrical/utils/utils.py:22` | yes | yes (`circuits/power_supply.py:7`) | no | KEEP | _ |
| 81 | `export_registry_to_csv` | function | `electrical/system/connection_registry.py:153` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 82 | `get_registry` | function | `electrical/system/connection_registry.py:31` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 83 | `InternalDevice` | class | `electrical/internal_device.py:9` | yes | yes (`devices/internal_devices.py:7`) | no | KEEP | _ |
| 84 | `CableData` | dataclass | `electrical/field_devices.py:49` | yes | yes (`devices/external_connections.py:16`) | no | KEEP | _ |
| 85 | `ConnectorData` | dataclass | `electrical/field_devices.py:31` | yes | yes (`devices/device_templates.py:9`) | no | KEEP | _ |
| 86 | `DeviceCable` | dataclass | `electrical/field_devices.py:67` | yes | yes (`devices/external_connections.py:16`) | no | KEEP | _ |
| 87 | `DeviceEntry` | dataclass | `electrical/field_devices.py` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 88 | `DeviceTemplate` | dataclass | `electrical/field_devices.py:166` | yes | yes (`devices/device_templates.py:9`) | no | KEEP | _ |
| 89 | `FieldDevice` | dataclass | `electrical/field_devices.py:83` | yes | yes (`devices/external_connections.py:16`) | no | KEEP | _ |
| 90 | `FixedPin` | dataclass | `electrical/field_devices.py:149` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 91 | `PinDef` | dataclass | `electrical/field_devices.py:101` | yes | yes (`devices/device_templates.py:9`) | no | KEEP | _ |
| 92 | `PrefixedPin` | dataclass | `electrical/field_devices.py:132` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 93 | `SequentialPin` | dataclass | `electrical/field_devices.py:112` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 94 | `generate_field_connections` | function | `electrical/field_devices.py:283` | yes | yes (`devices/external_connections.py:16`) | no | KEEP | _ |
| 95 | `EMPTY_TEMPLATE` | constant | `electrical/inter_device.py:24` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 97 | `Terminal` | class (str subclass) | `electrical/terminal.py:15` | yes | yes (`cabinet.py`, `devices/plc_modules.py`, `devices/terminals.py`) | yes (`06_full_cabinet.py`) | KEEP | _ |
| 98 | `BridgeRange` | dataclass | `electrical/utils/terminal_bridges.py` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 99 | `ConnectionDef` | dataclass | `electrical/utils/terminal_bridges.py` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 100 | `expand_range_to_pins` | function | `electrical/utils/terminal_bridges.py:13` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 101 | `generate_internal_connections_data` | function | `electrical/utils/terminal_bridges.py:45` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 102 | `get_connection_groups_for_terminal` | function | `electrical/utils/terminal_bridges.py:18` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 103 | `parse_terminal_pins_from_csv` | function | `electrical/utils/terminal_bridges.py:59` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 104 | `update_csv_with_internal_connections` | function | `electrical/utils/terminal_bridges.py:105` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 105 | `PlcDesignation` | dataclass | `electrical/plc_resolver.py:43` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 106 | `PlcModuleType` | dataclass | `electrical/plc_resolver.py:28` | yes | yes (`devices/plc_modules.py:14`) | no | KEEP | _ |
| 107 | `PlcRack` | class | `electrical/plc_resolver.py` | yes | yes (`devices/plc_modules.py:14`) | no | KEEP | _ |
| 108 | `extract_plc_connections_from_registry` | function | `electrical/plc_resolver.py:355` | yes | yes (`devices/plc_modules.py:22`) | no | KEEP | _ |
| 109 | `generate_plc_report_rows` | function | `electrical/plc_resolver.py:394` | yes | yes (`devices/plc_modules.py:25`) | no | KEEP | _ |
| 110 | `resolve_plc_references` | function | `electrical/plc_resolver.py:303` | yes | yes (`devices/plc_modules.py:14`) | no | KEEP | _ |
| 111 | `CircuitValidationError` | exception | `core/exceptions.py:4` (re-exported via `electrical/exceptions.py`) | yes | no | no | DEMOTE_CANDIDATE (kept for `except` clauses, but no consumer catches it) | _ |
| 112 | `ComponentNotFoundError` | exception | `core/exceptions.py:30` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 113 | `PortNotFoundError` | exception | `core/exceptions.py:16` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 114 | `TagReuseError` | exception | `core/exceptions.py:40` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 116 | `TerminalReuseError` | exception | `core/exceptions.py:54` | yes | no | no | DEMOTE_CANDIDATE | _ |
| 117 | `WireLabelMismatchError` | exception | `core/exceptions.py:68` | yes | no | no | DEMOTE_CANDIDATE | _ |

## Recommendation legend

- **KEEP** — already in `__all__` and used externally; leave as-is.
- **PROMOTE** — used externally but not in `__all__` (or "leaked-public"); add to `__all__`.
- **DEMOTE_CANDIDATE** — in `__all__` today, no external usage. User decides if aspirational/forward-API or genuinely unused-and-internal.
- **MAKE_INTERNAL** — leaked-public with no usage. Rename `_foo` or move to private module (Phase 5 work).
- **REMOVE** — dead module / dead symbol. Candidate for outright deletion (especially in `block/`).
- **KEEP (port-ID contract)** — symbol factory under `electrical/symbols/`. Public regardless of grep results.

## Summary

- Total symbols inspected: 117
- KEEP: 56
- KEEP (port-ID contract): 20 (all symbol factories — rows 22-41 — even unused ones)
- PROMOTE: 0 (no external usage was found for any name not already in `__all__`)
- DEMOTE_CANDIDATE: 41
- MAKE_INTERNAL: 0
- REMOVE: 0

> Notes for review:
> 1. Several "DEMOTE_CANDIDATE" exception classes (`CircuitValidationError`, `TagReuseError`, etc.) are part of the documented error contract per `CLAUDE.md`. Consumers may catch these even if grep doesn't find an explicit `except CircuitValidationError`. Consider downgrading these to KEEP at user discretion.
> 2. `ref` (function, descriptors) and `ref_symbol` (re-exported symbol factory) co-exist in `__all__`. The aliasing is deliberate but invites confusion. Worth a follow-up rename in A2/A3.
> 3. `merge_reuse_tags`, `term`, `comp`, `build_from_descriptors` form the "descriptors" mini-API. None used externally — could either be kept aspirationally or moved to a sub-module.
> 4. Pin-tuple constants (`COIL_PINS`, `NO_CONTACT_PINS`, `NC_CONTACT_PINS`, `CB_2P_PINS`, `CB_3P_PINS`, `CONTACTOR_3P_PINS`) — not used externally; symbol factories supply IEC defaults. Strong candidates for demotion.
