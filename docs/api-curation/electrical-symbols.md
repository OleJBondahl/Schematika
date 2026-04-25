# API curation — electrical-symbols

**Source:** `src/schematika/electrical/symbols/__init__.py` and the per-symbol modules (actuators, assemblies, blocks, breakers, coils, connector_pins, contacts, motors, protection, references, terminals, transducers).
**Generated:** 2026-04-25 (Wave A0 phase 3)
**Status:** AWAITING USER REVIEW — fill the "Your decision" column.

> Notes from generation:
> - Per CLAUDE.md "port-ID contract" rule (rule 6 in the recommendation rubric), every symbol factory under `electrical/symbols/` is **KEEP** regardless of grep hits, because port-ID conventions are documented in factory docstrings and form a public contract. Consumer usage is recorded so the user can deliberately decide to remove an unused factory.
> - The `electrical/symbols/__init__.py` `__all__` lists 20 names. All 20 except `connector_pin` are also re-exported from `electrical/__init__.py:__all__`. `connector_pin` is exposed at `schematika.electrical.symbols.connector_pin` but **not** at the `schematika.<name>` top level — flagged below.
> - All entries map to `def name(label: str = "", ...) -> Symbol` with minor variation per factory.

## Inventory

| # | Symbol | Kind | Defined in | In `__all__` today | Consumer uses | Examples / docs use | Recommendation | Your decision |
|---|---|---|---|---|---|---|---|---|
| 1 | `block` | symbol factory | `electrical/symbols/blocks.py:175` | yes | yes (`fan_controll.py`, `plc_power.py`, `power_supply.py`) | yes (`05_multi_builder.py`) | KEEP (port-ID contract) | _ |
| 2 | `breaker` | symbol factory | `electrical/symbols/breakers.py:73` | yes | yes (`fan_singlepole.py`, `power_supply.py`, `pump_circuit.py`) | yes (`02_dol_starter.py`, `06_full_cabinet.py`) | KEEP (port-ID contract) | _ |
| 3 | `coil` | symbol factory | `electrical/symbols/coils.py:22` | yes | yes (`fan_controll.py`, `power_switching.py`, `pump_controll.py`, `valve_control.py`) | yes (4 examples) | KEEP (port-ID contract) | _ |
| 4 | `connector_pin` | symbol factory | `electrical/symbols/connector_pins.py:23` | yes | no | no | KEEP (port-ID contract) — but note: NOT re-exported at `schematika.<name>` top-level. Phase 5 should decide whether to add or rely on `from schematika.electrical.symbols import connector_pin`. | _ |
| 5 | `contactor` | symbol factory (assembly) | `electrical/symbols/assemblies.py:22` | yes | yes (`fan_singlepole.py`, `pump_circuit.py`) | yes (`02_dol_starter.py`, `06_full_cabinet.py`) | KEEP (port-ID contract) | _ |
| 6 | `ct` | symbol factory | `electrical/symbols/transducers.py:16` | yes | no | no | KEEP (port-ID contract) | _ |
| 7 | `ct_assembly` | symbol factory | `electrical/symbols/transducers.py:48` | yes | yes (`fan_singlepole.py`, `pump_circuit.py`) | no | KEEP (port-ID contract) | _ |
| 8 | `estop` | symbol factory (assembly) | `electrical/symbols/assemblies.py:63` | yes | no | no | KEEP (port-ID contract) | _ |
| 9 | `estop_button` | symbol factory | `electrical/symbols/actuators.py:16` | yes | no | no | KEEP (port-ID contract) | _ |
| 10 | `fuse` | symbol factory | `electrical/symbols/protection.py:100` | yes | no | no | KEEP (port-ID contract) | _ |
| 11 | `motor` | symbol factory | `electrical/symbols/motors.py:208` | yes | no | yes (`02_dol_starter.py`, `06_full_cabinet.py`) | KEEP (port-ID contract) | _ |
| 12 | `nc_contact` | symbol factory | `electrical/symbols/contacts.py:134` | yes | no | no | KEEP (port-ID contract) | _ |
| 13 | `no_contact` | symbol factory | `electrical/symbols/contacts.py:66` | yes | yes (4 consumer files) | yes (3 examples) | KEEP (port-ID contract) | _ |
| 14 | `psu` | symbol factory | `electrical/symbols/blocks.py:99` | yes | yes (`circuits/power_supply.py:7`) | no | KEEP (port-ID contract) | _ |
| 15 | `ref` | symbol factory | `electrical/symbols/references.py:21` | yes (re-exported as `ref_symbol` in `electrical/__init__.py`) | no | no | KEEP (port-ID contract) | _ |
| 16 | `spdt_contact` | symbol factory | `electrical/symbols/contacts.py:328` | yes | no | no | KEEP (port-ID contract) | _ |
| 17 | `terminal` | symbol factory | `electrical/symbols/terminals.py:160` | yes | no | no | KEEP (port-ID contract) | _ |
| 18 | `terminal_box` | symbol factory | `electrical/symbols/blocks.py:18` | yes | no | no | KEEP (port-ID contract) | _ |
| 19 | `thermal_overload` | symbol factory | `electrical/symbols/protection.py:75` | yes | yes (`circuits/pump_circuit.py:10`) | yes (`02_dol_starter.py`, `06_full_cabinet.py`) | KEEP (port-ID contract) | _ |
| 20 | `turn_actuator` | symbol factory | `electrical/symbols/actuators.py:56` | yes | no | no | KEEP (port-ID contract) | _ |
| 21 | `turn_switch` | symbol factory (assembly) | `electrical/symbols/assemblies.py:91` | yes | no | no | KEEP (port-ID contract) | _ |

## Recommendation legend

- **KEEP (port-ID contract)** — symbol factory; public regardless of grep results.
- All other categories (KEEP/PROMOTE/DEMOTE_CANDIDATE/MAKE_INTERNAL/REMOVE) — see other matrices for definitions.

## Summary

- Total symbols inspected: 21
- KEEP (port-ID contract): 21 (all)
- KEEP / PROMOTE / DEMOTE_CANDIDATE / MAKE_INTERNAL / REMOVE: 0

> Notes for review:
> 1. `connector_pin` is the only symbol factory not surfaced via the `schematika.<name>` top-level wildcard. The user should decide whether to add it (consistent surface) or treat it as deliberately scoped.
> 2. `ref` and `ref_symbol` co-exist as names: `electrical/symbols/__init__.py` exports `ref`; `electrical/__init__.py` re-imports it as `ref_symbol` to avoid clashing with `descriptors.ref`. Phase 5 may want a clearer name (`reference_arrow`?) — flag for user judgment.
> 3. Many factories (`estop`, `estop_button`, `fuse`, `nc_contact`, `spdt_contact`, `turn_switch`, `turn_actuator`, `terminal`, `terminal_box`, `ct`, `ref`, `connector_pin`) have zero usage in the consumer or examples. They remain KEEP under the port-ID contract, but the user might choose to remove some as deliberately unused symbols.
