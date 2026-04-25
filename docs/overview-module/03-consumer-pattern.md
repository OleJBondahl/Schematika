# Consumer Pattern (auxillary_cabinet_v3)

How a real consumer repo uses Schematika today. This is the template for
all future systems: one repo per physical system, containing the cabinet
description, the PCBs that sit inside it, and the cables out to field
devices.

## Repo layout

- `pyproject.toml` — Schematika as a path dep
  (`schematika = { path = "../Schematika", editable = true }`) with the
  `cable` extra.
- `src/cabinet.py` — main entry point. Defines `setup_project()` and
  `main()`.
- `src/cables.py` — cable-deliverable entry point. Imports and calls
  `setup_project()` from `cabinet.py`.
- `src/circuits/` — one file per circuit (pump, fan, PSU, distribution,
  valve, feedback, PLC, etc.).
- `src/devices/` — terminals, PLC rack, field-device templates.
- `src/devices/external_connections.py` — list of `FieldDevice`
  instances (the field side).
- `src/devices/terminals.py` — the terminal lexicon, single source of
  truth for shared identifiers.
- `src/temp/` — intermediate per-circuit SVGs and CSVs.
- `cabinet.pdf`, `cables.pdf` — final deliverables.

## Orchestration: single `Project` instance

`auxillary_cabinet_v3/src/cabinet.py:55-121` constructs **one**
`Project` and registers everything on it:

```python
project = Project(...)
project.terminals(*Terminals.all())
project.add_circuit("power_switching", lambda s: ...)
project.add_circuit("pumps", lambda s: pump_circuits(s, count=NUM_PUMPS))
# ... ~10 add_circuit calls ...
project.field_devices(FIELD_DEVICES, ...)
```

`project._results[key]` populates as each circuit lambda runs. **Order
matters**: later circuits use
`reuse_tags={"Q": project._results["pumps"]}`
(`auxillary_cabinet_v3/src/cabinet.py:88`), so the dependency order is
encoded by call order.

`cables.py` reuses the same setup function — that's the standard idiom
for adding a deliverable. The Overview script will follow the same
pattern.

## Cross-domain example: 24V from PSU to a field switch

1. `auxillary_cabinet_v3/src/devices/terminals.py:30` declares
   `FUSED_24V = Terminal("X52", ...)`.
2. `src/circuits/power_supply.py` registers PSU output to `FUSED_24V`.
3. `src/circuits/pump_controll.py:46` consumes `Terminals.FUSED_24V`
   for the relay coil.
4. `src/devices/external_connections.py` declares field switch S3 with
   a connection that resolves to a pin on `X52`.
5. After `project.build_circuits()`,
   `project._results["pump_controll"].wire_connections` and
   `project._external_connections` jointly carry the resolved graph.

The shared identifier is the **terminal tag string** (`"X52"`) + pin
name. No typed registry, no symbolic linking — string equality.

## What's NOT in this consumer today

- **No PCBs.** `auxillary_cabinet_v3` has electrical + cable but no
  `pcb.build(...)` calls. The Overview module must support PCBs (per
  the future-state plan), but v0 will not have a real-world PCB
  consumer to test against — use a synthetic fixture for that path.
- **No explicit containment.** Implicit rule: everything in `circuits/`
  is in the cabinet, everything in `external_connections.py` is in the
  field. This breaks the moment a PCB sits inside the cabinet, which is
  exactly the future case Overview must handle. The
  consumer-supplied containment dict is the answer.
- **No graphviz / system-diagram code.** Greps for `Digraph`, `dot`,
  `system_view`, `overview` in this repo turn up nothing relevant.

## Gotchas for the Overview author

- `project._results` is dict-keyed by circuit name string. Reading
  before the circuit is added → `KeyError`. Overview must run
  post-`build_circuits()`.
- PLC references are magic strings (`PLC:AI:Sig`) resolved inside the
  library at build time. Overview must read post-build state to see
  resolved pins; reading the pre-build registration won't work.
- Two existing scripts (`cabinet.py`, `cables.py`) share state via
  `setup_project()`. The new Overview entry point will follow the same
  pattern — likely a third script `src/overview.py` in the consumer, or
  an inline call at the end of `cabinet.py:main()`. The consumer
  decides; both are fine.
- Some terminal names contain colons (`PLC:AI:Sig`). When emitting these
  as port names in DOT, quote them or substitute — see
  [`04-graphviz-reference.md`](04-graphviz-reference.md) on DOT keyword
  collisions and special characters.
