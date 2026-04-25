# System Visualization Tool — Direction & Philosophy

## Context

We have a Python-based build pipeline that generates production drawings for an
electrical system: PDF cabinet drawings (custom Python lib), PCB netlists
(skidl), and cable drawings (wireviz). These tools are linked by shared
connector identifiers, so the underlying data is already a connected graph
across cabinets, PCBs, and cables.

Production drawings are intentionally fragmented — each shop floor needs only
its slice. R&D has the opposite need: a way to see and reason about the whole
system at once. This tool fills that gap.

## Goal

A single auto-generated, navigable view of the entire electrical system, fed
from the same source data that drives production drawings. R&D should be able
to open it, see how everything connects, and click through to the underlying
production drawings when they want detail.

## Core principles

1. **Auto-generation is non-negotiable.** Manual layout defeats the purpose.
   Humans may provide light hints (port ordering on a unit, signal-kind
   classification), but never per-diagram positioning. The tool must regenerate
   cleanly whenever source data changes, ideally as part of the existing build.

2. **Complement, don't replace, production drawings.** The system view exists
   to give context and navigation. Detail lives in the existing PDFs. Every
   node and edge should hyperlink to its underlying production drawing.

3. **Readability over prettiness.** Engineer-readable beats aesthetically
   polished. Right-angle wire routing, clear box hierarchy, color-coded signal
   types.

4. **Wire-level detail, not bundle-level.** The system has relatively few
   distinct units but many individual signal wires between them. The value of
   this view is showing each wire — collapsing wires into "cable bundles"
   removes the information R&D needs.

5. **Nested containment is required.** Units physically contain other units:
   a BMU PCB sits inside a Juicebox PCB sits inside an electrical cabinet,
   with other cabinets as peers outside. The visualization must show this
   nesting visually, with wires flowing from inner units outward across
   container boundaries.

## Recommended starting stack

**Graphviz (`dot` layout) via the Python `graphviz` package**, generating SVG.

Reasoning:
- Already installed in the project environment.
- Pure Python script → SVG file. No JS, no build toolchain, no browser
  framework. Composes naturally with the existing PDF-generation pipeline.
- Supports nested clusters for arbitrary containment hierarchy.
- Supports HTML-table node labels with named ports, which gives us
  pin-level edge attachment without needing a more complex layout engine.
- SVG hyperlinks (`href` attribute) work natively in browsers — click a
  node or edge, open the production drawing.
- `splines="ortho"` produces right-angle wire routing that reads like an
  engineering diagram.

A working proof of concept in this stack already exists (see prior
conversation / reference snippet) demonstrating nested clusters, HTML port
labels, and individual wire edges between specific ports.

## Data model

Three flat collections, derivable from existing skidl/wireviz/cabinet data:

```python
units = [
    {
        "id": "BMU",
        "label": "BMU",
        "parent": "Juicebox",        # None = top level
        "is_container": False,        # True = renders as cluster, not node
        "ports": ["VCC", "GND", "CAN_H", "CAN_L", "WAKE"],
        "kind": "pcb",                # cabinet | pcb | device | terminal | ...
        "drawing": "path/to/pdf",
    },
    # ...
]

wires = [
    {
        "from": ("BMU", "CAN_H"),     # (unit_id, port_name)
        "to":   ("X1",  "1"),
        "kind": "can",                # power | can | safety | signal | ...
        "drawing": "path/to/cable.pdf",
    },
    # ...
]
```

Containers (cabinets, parent PCBs) become Graphviz `cluster_*` subgraphs.
Leaf units become HTML-table nodes with one row per port. Wires become
edges of the form `unit:port -> unit:port`. Visual style (color, shape,
edge thickness, dashing) is derived from `kind`, not specified per-item.

## Scope for the first iteration

Build a working tool against a real subset of the system: one cabinet
containing a Juicebox containing a BMU, with two or three peer cabinets
outside, and all real signal wires between them. Iterate on layout
parameters (`splines`, `rankdir`, `nodesep`, `ranksep`) until the output
is readable. Do not over-engineer — no filtering, no layered views,
no interactivity beyond SVG hyperlinks. Validate with R&D before
expanding scope.

## Deferred / out of scope (for now)

- **Layered views** (power-only, CAN-only, safety-only). Valuable but
  separable; ship the base view first.
- **Interactive filtering** (toggle signal kinds on/off). Requires a JS
  layer; defer until base view is validated.
- **Physically accurate port placement** (connectors on the side of the
  box they're really on). Graphviz fundamentally can't do this — ports
  appear in the row order specified. If R&D requires this after seeing
  the first version, that's the trigger to migrate to ELK
  (elkjs + sprotty / reactflow / Cytoscape.js). The data model above
  is compatible with ELK, so migration would mean writing a new emitter,
  not redoing the data extraction.
- **Signal tracing tool** (query: "where does +24V_AUX go?"). Same
  underlying graph, different UI. Separate deliverable.

## Known issues to plan for

- **Edge label crowding.** With many wires, per-edge labels become
  unreadable. Plan to color-code by `kind` and only label edges that
  cross cabinet boundaries, or drop edge labels entirely.
- **Port ordering affects readability.** Graphviz renders ports in the
  order given in the HTML table. Grouping ports by destination
  (e.g. all "to-Vehicle" pins adjacent) reduces wire crossings. This is
  the one place per-unit human input genuinely helps; automate it from
  destination data where possible.
- **Diagonal wire stubs** at port attachment points are normal with
  `splines="ortho"`. Acceptable.
- **Cluster ports don't exist in Graphviz.** Terminal blocks that act
  as the cabinet's "boundary" must be modeled as regular nodes placed
  inside the cluster, not as ports on the cluster itself.

## Definition of done (first iteration)

- Single Python script (or module) that reads the existing linked
  unit/wire data and emits `system.svg`.
- Output renders nested cabinet → Juicebox → BMU containment correctly.
- All individual signal wires shown as separate edges, color-coded by kind.
- Clicking a unit opens its production drawing; clicking a wire opens
  its cable drawing.
- Regenerates as part of (or alongside) the existing build pipeline.
- Reviewed with at least two R&D engineers; their feedback determines
  whether to extend in Graphviz or migrate to ELK.