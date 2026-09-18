# pcb-layout track findings

Track question: what's the right layout approach for SKiDL-sourced connector
schematics reviewed by a human (not board/copper layout)? Can it share an
engine with `electrical`'s ladder/zone layout, or does it need something
closer to force-directed/hierarchical net placement (general EDA schematic
tools)?

## TL;DR verdict: **drop** — there is no gap to fill

The premise in the spike brief ("is it manual `position` today, same as
`electrical`?") is false. `schematika.pcb` already has a fully automatic,
deterministic, non-manual layout engine (`walk.py` + `layout_spec.py` +
`render.py`), purpose-built for exactly this diagram type. It is not a
generic netlist-to-schematic layout problem in disguise — it's closer to a
wiring-harness diagram than to an EDA schematic sheet, and the existing
engine already produces the right *shape* of output. Neither a force-directed
net-length-minimizing layout, nor `electrical`'s ladder/zone engine, nor any
external netlist-layout tool (netlistsvg, KiCad, grandalf/networkx) fits this
problem better. This track found nothing to pursue; it's a confirmation, not
a proposal.

## 1. What `pcb.build()` actually does today

Entry point: `src/schematika/pcb/builder.py:15` `build(circuit, mapping, ...)`.
Pipeline: `adapter.adapt()` → `walk.build_connector_blocks()` →
`walk.find_floating_parts()` → `walk.pack_pages()` → `PCBBuildResult`.

There is **no `position: Point | None` parameter anywhere in the `pcb`
public API** — not on `build()`, not on any model field. Compare this to
`API_STYLE.md`'s parameter glossary, which reserves `position` for exactly
the "diagram coordinates, `None` means auto-layout" case; `pcb` never needs
that escape hatch because placement is never manual.

The real algorithm, in `src/schematika/pcb/walk.py`:

- `enumerate_connectors` walks every part in the netlist whose SKiDL template
  is registered as a (non-bottom-terminator) connector.
- For each connector pin, `walk_pin` → `_walk_part_to_completion` follows the
  net graph outward: pin → net → other pin → part → part's other pin → next
  net → ... — placing exactly one symbol "slice" per part it passes through,
  atomically completing multi-slice parts, and stopping at one of four
  terminator kinds decided by `classify.classify_net` (`src/schematika/pcb/classify.py:17`):
  `POWER` (net name matches a registered power rail — draws the rail
  symbol), `LABEL` (net has 3+ pins, or crosses into another connector's
  territory — draws a text cross-reference, **not a wire**), `NC` (dead
  end), or a project-specific `PIN_AT_BOTTOM` terminator for
  bottom-terminator connectors.
- `slice_ownership` (first-touch-wins) prevents the same physical part from
  being drawn twice if two different connector pins' chains would otherwise
  both reach it; the loser gets a `LABEL` cross-reference instead.
- `pack_pages` greedily packs `ConnectorBlock`s left-to-right into rows,
  opens a second row when the first row's chains are short enough to leave
  vertical room, and inlines "floating" (unreached) parts' slices next to
  whichever connector they're most associated with.

This is a **hierarchical, per-connector-pin column layout with deterministic
tie-breaking and cross-reference labels instead of long wires** — a close
cousin of relay-ladder/cable-harness diagram conventions, not of general
schematic capture. It is backed by 44 unit test files under
`tests/unit/test_pcb_*.py`, including dedicated walk/pack/render/check
suites (`test_pcb_walk_chain.py`, `test_pcb_pack_pages.py`,
`test_pcb_check_pcb0*.py`, etc.) — this is mature, exercised code, not a
stub.

## 2. What SKiDL offers for layout: nothing

`src/schematika/pcb/adapter.py`'s module docstring says it plainly: "SKiDL
objects are duck-typed... no `skidl` import is needed here." `adapt()` only
ever reads `circuit.parts`, `circuit.nets`, `circuit.NC`, and each part's
`.ref`/`.name`/`.pins`/`.description` — there is no coordinate, no
`position`, no hint field of any kind touched anywhere in the adapter or
`CircuitIR` (`adapter.py:44`). This matches SKiDL's actual purpose: it's a
Python DSL for **netlist capture** (parts + connectivity) that exports to a
KiCad netlist for PCB *copper* layout; SKiDL has never had a schematic-sheet
layout concept, because in its own workflow schematic capture is skipped
entirely (Python code *is* the schematic). There is no spatial information
to recover from a SKiDL circuit under any circumstance — any layout has to
be synthesized from the netlist topology alone, same as `pcb.build()` does.

## 3. External prior art survey

- **KiCad eeschema**: has zero schematic auto-placement. KiCad's
  auto-*routing* only applies to PCB copper traces; symbol placement on a
  schematic sheet is 100% manual, always has been. The tool this project is
  closest to in spirit offers no prior art for auto-placing schematic
  symbols at all.
- **netlistsvg** (Yosys ecosystem): renders a Yosys-JSON gate-level netlist
  as SVG using ELK (Eclipse Layout Kernel) for layered/orthogonal placement.
  It's aimed at **digital gate-level** netlists (LUTs, flip-flops, muxes)
  with a fixed "skin" vocabulary, not arbitrary electromechanical parts.
  Using it here would mean: (a) translating `CircuitIR` into Yosys-JSON, (b)
  authoring a skin for every connector/relay/fuse symbol, (c) taking on the
  same Node/ELK bridge cost this repo's separate `elk-bridge` track is
  already evaluating for `electrical` — for a generic layered-graph layout
  that still wouldn't know to draw `LABEL` cross-references instead of wires
  across page boundaries, because that's a domain rule, not a graph-drawing
  concern.
- **Pure-Python graph layout** (`networkx` spring/spectral layouts,
  `grandalf` Sugiyama — surveyed in depth by the sibling
  `pure-python-graph-layout` track): all of these solve "minimize wire
  crossings / edge length over an arbitrary graph." That is a genuinely
  different objective from "for connector J1, in pin order, show what each
  pin does" — see the prototype in §4.

None of these tools, or the general force-directed/hierarchical net-layout
family they represent, solve the problem `pcb.build()` already solves: an
answer keyed by **connector + pin number**, not by graph topology.

## 4. Prototype

Code: `research/layout/pcb-layout/synthetic_circuit.py` (duck-typed
SKiDL-shaped circuit — 2 connectors, a fuse, a relay coil, a floating test
point, covering all four `NetKind`s: `POWER`, `CHAIN` incl. one cross-block
chain J1→F1→J2, `LABEL` junction, and the implicit `DROPPED` case) and
`research/layout/pcb-layout/run_prototype.py`.

Run: `uv run python research/layout/pcb-layout/run_prototype.py` (from this
worktree's root). Output SVGs land in `research/layout/pcb-layout/out/` but
are not committed — this repo's root `.gitignore:7` (`*.svg`) blankets all
SVGs, generated or not, so they aren't part of this commit; regenerate with
the command above. stdout:

```
connector_blocks: ['J1', 'J2']
floating_parts:   []
pages:            1
  page 'Connectors starting at J1': placements=(('J1', 0.0, 30.0), ('J2', 70.0, 30.0))
```

`out/connector_anchored.svg` — the real `schematika.pcb` pipeline
(`build()` → `render_connector_block()`/`render_floating_part()` →
`render_system()`). Verified by inspecting the emitted SVG coordinates
directly (this worktree has neither `cairosvg` nor `playwright` installed,
and installing either just for a one-page spike sanity check wasn't
warranted): J1 renders as a 50mm-wide 4-pin connector box (`4 × 10mm
pin_spacing + 2 × 5mm side_padding`, matching `LayoutSpec` exactly); pin 1
gets the `+24V` rail symbol; pin 2 gets the 3-bar `GND` symbol; pin 3's
chain draws a single continuous wire from y=40 to y=165 through the (empty
stub) fuse symbol, then a `SIG_F1_OUT` cross-reference label — both near the
connector (for at-a-glance reading) and again at the chain's far end (for
tracing) — instead of a wire running across the page to J2; J2 independently
shows the matching `SIG_F1_OUT` label on its own pin 1. That two-sided
label-instead-of-wire behavior is the single clearest piece of evidence that
this is wiring-harness-diagram logic, not generic schematic capture: a
force-directed or Sugiyama layout has no concept of "these two things are
the same net but should be drawn as a cross-reference, not an edge."

`out/force_directed.svg` — a **hand-rolled** 200-iteration
Fruchterman-Reingold spring embedding of the same 5-part netlist graph
(pure Python, no `networkx`/`scipy` — neither is installed in this worktree
and adding either just for a comparison script isn't worth it given
`core`'s zero-runtime-dep rule). This is explicitly *not* wired through
Schematika's `Symbol`/`Port` renderer — nodes are drawn as bare circles with
straight edges, because a spring layout produces continuous (x, y)
positions with no notion of which side of a symbol a port faces, so there is
no principled way to snap it onto Schematika's port-and-wire model at all.
The output is a topology cloud (J1 as a hub connecting to F1/K1, which
connect on to J2/TP1) with no pin ordering, no per-connector reading order,
and no left-to-right/top-to-bottom convention a technician could follow with
a multimeter. This is what "force-directed net-length minimization" gets
you, and it's a strictly worse fit for "human review of a connector
pinout" than what `pcb.build()` already does.

## 5. Does `electrical`'s ladder/zone approach fit `pcb` instead?

No — for the opposite reason force-directed layout doesn't fit.
`electrical`'s zone model (power rail → protection → control → coils →
terminals, per the `grid-astar-router` track) encodes **one global
left-to-right functional-stage ordering** that assumes a single dominant
power-flow direction across the whole diagram. A SKiDL-sourced connector
schematic has no such global flow: each connector pin's chain is an
independent, self-terminating unit (it might hit `POWER`, a `LABEL`
cross-reference, an `NC` dead end, or a bottom-terminator pin), and
different pins on the *same* connector routinely serve unrelated purposes
(power in on pin 1, a relay coil on pin 4, a cross-referenced signal on pin
3). Retrofitting zone-based placement here would require one zone-ordering
*per pin*, which just reconstructs `walk_pin`'s per-pin column — i.e., you'd
end up re-deriving `walk.py` on top of a different vocabulary, for no gain.

## 6. Integration effort / shared-engine assessment

Sharing a placement *engine* between `pcb` and `electrical` (or bridging
either to ELK/netlistsvg/grandalf) would be net-negative effort here:

- `pcb`'s domain rules (slice ownership/first-touch-wins, bottom-terminator
  special-casing, label-vs-wire cross-referencing, two-row page packing with
  inline floating-slice anchoring) are not generic graph-layout concerns —
  they'd have to be reimplemented as constraints/post-processing on top of
  whatever generic engine won, for a result no better than what `walk.py`
  produces today.
- The `pcb` package already respects every relevant repo invariant: `build()`
  returns a frozen `PCBBuildResult` (no manual `position`, no `None`
  return), `pcb` imports only `core`/`electrical` (layer 2, per
  `docs/ARCHITECTURE.md`), and `LayoutSpec` is the sanctioned
  spacing-override mechanism already following the `set_<property>`
  parameter-glossary pattern.
- One legitimate, pre-existing caveat (not a layout-engine gap): the
  `LayoutSpec` defaults are explicitly "tuned for the juicebox PCB on an A4
  landscape page" (`src/schematika/pcb/layout_spec.py:10`). That's a
  calibration/config concern solvable by tuning `LayoutSpec` per project,
  not evidence the placement *algorithm* is wrong.

## Verdict

**Drop.** `schematika.pcb` does not need a new layout engine, does not need
to share one with `electrical`, and does not need force-directed/hierarchical
net placement borrowed from general EDA tooling. The existing
connector-anchored walk (`walk.py`) + greedy page packer
(`pack_pages`) + `LayoutSpec` already implement the right *kind* of
algorithm for "SKiDL netlist reviewed as a wiring-harness-style connector
schematic," it's automatic (no manual `position` anywhere in the public
API), and it's backed by 44 existing unit test files. The spike's own
prototype confirms the alternative (spring/force-directed layout on the same
netlist) produces a strictly worse artifact for this specific review task.
No further work is recommended on this track.
