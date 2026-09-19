# PCB API: own `Board` on the core graph, SKiDL as importer

Research note and throwaway prototypes, 2026-09-19. Not part of `src/`; nothing here is imported by the library.

**Status: leaning, not decided. Revisit together with the electrical-module rewrite. Do not rewrite `pcb/` before then.**

## Question

Are there better alternatives to SKiDL, and should Schematika wrap SKiDL in its own PCB API so `pcb` and `electrical` code share one Schematika syntax? The PCB side needs to deliver (a) a KiCad netlist and (b) parts, pins and nets as data for the drawings.

## Leaning

Own `Board` API (`part()`, `connect()`, `nc()`, declarative in the style of `Project.route()` / `field_devices()`) built on the core graph. Own KiCad netlist writer. SKiDL kept as an optional importer (`from_skidl`) so existing SKiDL code keeps working.

| Option | Verdict |
|---|---|
| 1. SKiDL directly (today) | Least work now. Two syntaxes, unstable refs unless every part has `tag=`, and a second model read back through `pcb/adapter.py`. |
| 2. Own API over SKiDL as a hidden backend | Works (prototype below). Still two models, SKiDL quirks leak through. |
| 3. Own API on the core graph, own netlist writer, SKiDL as importer | **Leaning.** One model, stable IDs by construction, deterministic netlist. Cost: KiCad symbol import, hierarchy and ERC (as graph validators) are ours to write. |

## Prototypes

Run from this directory (writes `skidl_out.net` and `own_out.net` into the working directory):

```
uv run --no-project --with skidl==2.3.0 python wrapper_skidl.py
uv run --no-project --with skidl==2.3.0 python own_netlist.py
```

- `wrapper_skidl.py`: a `Board` API with SKiDL as hidden backend. Uses an explicit `Circuit`, and parts come from catalog-style specs, so no KiCad symbol libraries are needed. Two boards in one process each got their own `J1` and `R1`, and SKiDL's global `default_circuit` stayed empty.
- `own_netlist.py`: a plain frozen IR, a KiCad netlist writer (about 40 lines; 158 with IR types, an s-expression reader and the diff), and an automated diff against SKiDL's own netlist.

Results (SKiDL 2.3.0, Python 3.14):

- Components and nets equal to SKiDL's on the test circuit; a perturbed case is detected.
- Our netlist carries pin names (`pinfunction`) and an MPN field. SKiDL's does not, and it adds random `SKiDL Tag` fields, so its output is not deterministic.
- SKiDL derives each component's `tstamp` from its hierarchical name including the tag (`uuid5(namespace, part.hiername)`, `tools/kicad9/gen_netlist.py`). It is stable only with an explicit `tag=`. Expectation, not tested in KiCad: tstamps derived from stable IDs keep footprints matched when a netlist is updated.

## Not verified

- That KiCad's own importer accepts our netlist. The check via `kinet2pcb` could not run: `pcbnew` will not load under the uv Python, and it fails the same way on SKiDL's own netlist. Running KiCad's bundled `python.exe` from a tool call hung and raised an error popup, so do not do that.
- Hierarchical sheets and NC pins are not covered by the prototype.

## Alternatives looked at

Facts for atopile and circuit-synth are from their GitHub README text only; tscircuit is from search snippets.

| Tool | Fit |
|---|---|
| SKiDL 2.3.0 (MIT, 2026-07-28) | Library parsing, ERC, subcircuits, SPICE. Global state. Pulls in `inspice` (GPL-3.0). |
| atopile (MIT) | Its own `.ato` language and compiler that outputs KiCad files. Replaces the syntax rather than wrapping it. No documented Python API found. |
| circuit-synth (MIT, Python 3.12+, KiCad 8+) | Its own Python syntax generating `.kicad_sch` / `.kicad_pcb`. Not a SKiDL wrapper. |
| tscircuit | TypeScript. Its KiCad converter had an open bug where nets landed on wrong pads. |

## Extra work option 3 implies

- KiCad symbol import if pins should be auto-filled from KiCad libraries: use `sexpdata` (BSD); `kiutils` is GPL-3.0.
- Hierarchy.
- ERC as validators over the graph.

Related decision on the backend model: own typed graph, AML only as inspiration and a possible future export.
