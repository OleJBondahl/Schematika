# Symbol library: one source, checked against the standards

Status: research, no production code. Branch `layout-improvment`, 2026-09-19.
Continues `docs/research/layout-improvement/symbol-standards.md`, which specced three symbols and
concluded PCB needs none. This doc supersedes that on scope: electrical, PCB, P&ID and overview all
need many more symbols, and no one should have to review each iteration by eye.
The symbol list is in [inventory.md](inventory.md).

## What the standards define

The standards define symbols as drawings on a grid, not as coordinate tables. Nothing can be coded
"from the definition" without first turning a drawing into geometry.

| Source | Content | Machine-readable | Licence |
|---|---|---|---|
| ISO 81714-1 | Grid of module M, subdivisible by 0.1 M or 0.125 M. Line width : M = 1 : 10. ISO 14617 uses M = 2.5 mm. | text | paywalled |
| ISO 10628-2 (P&ID) | 296 symbols, each with an ISO 14617 registration number | yes: Baltakatei's Commons SVGs, mm scale | CC BY-SA 4.0 |
| IEC 60617 database | about 1900 symbols | GIF / DWG / EPS via paid subscription (CHF 280/yr) | subscription |
| ISA 5.1 | illustrative drawings, no dimensions | no | paywalled |
| KiCad-IEC-60617 | about 30 IEC-style symbols on a 2.54 mm grid | yes | Unlicense |
| QElectroTech elements | large IEC-style set | probably | CC-BY 3.0, forbids use as ML sample data |
| Commons "IEC 60617" | 4 files, semiconductors only | yes | mixed |

Facts about the ISO 81714-1 rules come from search snippets. Its sample PDFs are copy-protected and
were not read. Schematika's 5 mm grid with 0.5 mm strokes keeps the 1 : 10 ratio but is 2 M, twice
ISO's scale. Extracted geometry needs a fixed ×2.

What was checked directly: Sheet 6 of the P&ID transcription has 385 paths and 171 text labels in
mm coordinates. 61 labels have the form `REG#:C0096 DESC:Orifice plate`, so registration number and
name come with the geometry. In the five symbol layers, each text label has one sibling `<g>`
(24 labels and 24 groups in one layer, 9 and 9 in another; 60 in total, plus one label outside the
layers). Pairing them looks straightforward but has not been proven.

## Decision: transcribe from the open SVGs

You chose direct transcription. Consequences to settle before any transcribed file is committed:

- The repo is MIT. CC BY-SA 4.0 requires adaptations to stay CC BY-SA 4.0 with attribution.
  Transcribed data and code generated from it count as adaptations.
- Keep transcribed data in its own directory with a `LICENSE` and `NOTICE`, and mark generated
  factories with their origin. The wheel then ships mixed licences, clearly labelled.
- Do not transcribe from QElectroTech: its licence forbids use as ML sample data.
- Electrical has no open source of comparable size. KiCad-IEC covers about 30 symbols, and its
  2.54 mm grid must be snapped to M = 2.5 mm.
- This is a licensing question, not legal advice. Get your explicit sign-off first.

## Architecture: a Layer-1 `symbols` package

Domain packages may not import each other. `pcb/symbols` exists as a separate copy for that reason,
and overview has no symbols at all. A single source therefore needs a package below the domains.

```
core            Symbol, Port, primitives                        layer 0
symbols  (new)  kit + families + specs + registry               layer 1
electrical / pid / pcb / overview   import symbols, re-export   layer 2
```

- **Kit** (`symbols/kit`): shared building blocks such as lead, body box, circle body, diagonal cross,
  contact blade, actuator glyphs, arrows, spring. Values are in M units.
- **Families**: IEC symbols are a general shape plus qualifiers, and ISO 14617 valves are a body times
  an actuator. Families compose kit parts, so a new symbol is a declaration and many symbols come
  from few parts.
- **`SymbolSpec`** (frozen dataclass): `id`, `standard` (registration number when known), `domain`,
  `factory`, port IDs with side (N/E/S/W), envelope in M, `icon` flag.
- **Registry**: the one place that lists every symbol. Docs, the LLM catalog, tests, contact sheets
  and overview icons are all generated from it.
- Domain packages keep their current public names as re-exports, so consumers do not change.
  Alpha status allows a breaking rename if a re-export is awkward.

Overview draws node icons by rendering a `Symbol` to SVG and passing it to Cytoscape as a
`background-image` data URI (URL-encoded, not base64). Icon variants drop pin numbers and labels and
use a heavier stroke so they survive at 16 to 24 px. Nodes with no standard symbol (board, harness,
PLC) get plain glyphs in the same kit.

## Verification without you in the loop

| # | Gate | What it catches | Replaces |
|---|---|---|---|
| 1 | Conformance linter | ports off the 0.125 M grid, port direction not outward, lead not touching body, elements outside envelope, stroke width outside the allowed set, text below minimum size, label over body, missing `Ports:` docstring | hand-pinned numeric tests in `tests/unit/symbols/` |
| 2 | Reference diff | shape differs from the reference symbol | your eyes |
| 3 | Snapshot | unintended change after a symbol is accepted | nothing today for new symbols |
| 4 | Contact sheet | anything the first three miss | per-symbol review; I read the PNG myself |

Gate 1 builds on `core/geometry_lint.py` and `pid/validation.py`. Gate 2 rasterises both symbols,
fits them to the same bounding box, and compares chamfer distance. References live in a gitignored
cache, so local CI needs no network. Calibrate the threshold on the 15 existing P&ID symbols, and
add a deliberately broken symbol to prove the gate can fail. You sign off one contact sheet per
batch, if at all.

Limit: electrical symbols with no reference only get gates 1, 3 and 4. Fidelity there rests on the
kit, the linter and my reading of the sheet. Buying the IEC 60617 database would close that gap if it
proves too weak. Its reuse terms have not been checked.

## Transcription pipeline (P&ID first)

1. Fetch a sheet SVG. Parse text labels for `REG#` and description.
2. Pair each label with its sibling geometry group. Apply the transform stack.
3. Flatten paths to lines, arcs and polygons in mm. Divide by 2.5 to get M, then snap to 0.125 M.
4. Emit a spec file per symbol (registration number, primitives, ports guessed from connection
   marks) plus a factory that builds it from the kit.
5. Run gates 1 to 4.

Open risk: ports. The sheets mark preferred connection points, but extracting them is unproven.

## Pilot before mass production

Every step ends in a check.

1. Parse sheet 6 and compare against our six existing valves. Verify: pairing finds all 61 labels,
   and the diff reports a number per valve. This calibrates gate 2.
2. Transcribe relief valve, orifice plate and filter. Verify: gates 1 to 4 pass and `just ci` is green.
3. Author `indicator_light` and `transformer` from the kit and compare against KiCad-IEC. Verify: same.
4. Render five overview icons from existing symbols. Verify: the overview module's existing tests pass
   and a screenshot shows them at node size.

Stop and reassess if step 1 cannot pair labels to geometry reliably.

## Open questions

- Repo licence handling for transcribed data (above). Blocks step 2 onward.
- PCB scope. Guess: resistor, capacitor, diode, LED, transistor, IC block, crystal and power symbols for
  SKiDL review diagrams, reversing the earlier "out of scope" verdict. Confirm.
- Whether to make the new `symbols` package a Layer-1 sibling of `catalog`, or fold the kit into `core`.
  The package is the cleaner fit; `core` would only hold the kit.
