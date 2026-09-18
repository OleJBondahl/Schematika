# Symbol Standards — Geometry & Gap Analysis

Track: `symbol-standards`. Research spike, no production code changed.

## 1. What Schematika already encodes today

This is the most important finding: **Schematika's own `constants.py` files are
already a more complete, more explicit geometric spec than anything freely
available from the standards bodies themselves.** IEC/ISO/ISA sell the
official symbol databases; they do not publish the proportion/grid rules as
open text. Every open-source symbol library found during this research
(Acheron, chille/electricalsymbols, KiCad libraries) explicitly admits it
invented its own grid because *the standard doesn't specify one*. Schematika
did the same thing, but documented it far better than the average open
library.

### Core grid (`src/schematika/core/constants.py`)

| Constant | Value | Note |
|---|---|---|
| `GRID_SIZE` | 5.0 mm | Base module unit for every domain |
| `TERMINAL_RADIUS` | 1.25 mm (0.25×grid) | Terminal dot |
| `LINE_WIDTH_THIN` | 0.25 mm (0.05×grid) | Thinnest line class |
| `DEFAULT_POLE_SPACING` | 10 mm (2×grid) | Electrical pole pitch |
| `TEXT_SIZE_MAIN` | 5 mm | Main label text |

### Electrical (`electrical/model/constants.py`)

`LINE_WIDTH_THICK = 0.1×grid` (0.5 mm), `GRID_SUBDIVISION = grid/2` (2.5 mm,
used for lead-line length on coils/breakers), reference-arrow geometry
(`REF_ARROW_LENGTH` = 2×grid = 10 mm). Symbol factories (`contacts.py`,
`coils.py`) build everything from `GRID_SIZE`/`GRID_SUBDIVISION` — e.g. a
1-pole contact has a 5 mm gap (`±GRID_SIZE/2`) between the two leads, each
lead 5 mm long (`h_half = GRID_SIZE`); a coil body is `2×grid × 1×grid`
(10×5 mm) with 2.5 mm leads.

### P&ID (`pid/constants.py`) — the richest of the three

This file already cites ISO 14617 Part 1/6/8 and ISA 5.1 Clause 4/5.2/5.4 and
ISO 3098 Clause 4.1 by section, and derives every dimension from `GRID_SIZE`.
Highlights:

| Constant | Value | Standard basis |
|---|---|---|
| `PID_LINE_WEIGHT` (process pipe) | 0.7 mm | ISO 14617-1 §4, heaviest of 3 weights |
| `PID_EQUIPMENT_STROKE` | 0.5 mm | medium weight, equipment bodies |
| `PID_SIGNAL_LINE_WEIGHT` | 0.25 mm | thinnest, instrument/signal lines |
| `INSTRUMENT_BUBBLE_RADIUS` | 6 mm (12 mm diameter) | ISA 5.1 §5.2 |
| `PID_PUMP_RADIUS` | 10 mm (20 mm diameter) | ISO 14617-6 |
| `PID_STUB_LENGTH` | 5 mm | port-to-body pipe stub |
| `PID_TEXT_SIZE_*` | 2.5 mm | ISO 3098 §4.1 minimum lettering height for A3/A4 |
| `PID_MIN_EQUIPMENT_GAP` | 30 mm | ISO 14617-1 §5 |
| `PID_MIN_LEG_SPACING` | 40 mm | ISO 14617-1 §5 |

Only three stroke widths are permitted on a P&ID and `pid/validation.py`
enforces this (`_ALLOWED_STROKE_WIDTHS`). This is a real, useful invariant —
better than most open libraries bother with.

## 2. External sources checked

Official IEC/ISO/ISA standard *text* is paywalled (confirmed: IEC webstore
requires purchase; ANSI/ISA-5.1 full text likewise). What's open:

- **Acheron Docs / `AcheronProject/electrical_template`** (verified real,
  https://github.com/AcheronProject/electrical_template,
  https://acheronproject.com/electric_symbols/electric_symbols/) — an
  Inkscape SVG symbol library. It documents: 1 mm grid with a thicker line
  every 1 cm, 1 mm uniform line weight, 0.5 mm anchor-cross trace width, and
  explicitly states it follows **IEEE/ANSI 315-1975**, not IEC 60617, and
  that *"the standard does not indicate grid or sizes, so some liberties
  were taken."* Useful confirmation that proportions are a house convention
  everywhere, not a standards mandate — but its actual numbers (1 mm grid,
  screen/vector-art oriented) aren't directly portable to Schematika's
  real-mm print-oriented 5 mm grid.
- **`chille/electricalsymbols`** (GitHub) — another open IEC-flavored SVG
  set; no documented grid convention found in the repo itself.
- **ISO 81714-1** (graphical symbol design standard, found via secondary
  citation, not fetched from the primary text) — reportedly specifies a
  **1:10 line-width-to-module ratio**. Cross-checking against Schematika:
  `PID_EQUIPMENT_STROKE` (0.5 mm) : `GRID_SIZE` (5 mm) = 1:10 exactly.
  `PID_LINE_WEIGHT` (0.7 mm) is closer to 1:7. `LINE_WIDTH_THIN` (0.25 mm) is
  1:20 (thinner than the ratio, appropriate for the *thinnest* class). This
  is a real, if secondhand, data point suggesting Schematika's ratios are in
  the right neighborhood, not arbitrary.
- **KiCad-derived EDA libraries** (`KarelT1/KiCad-IEC-60617-symbol-library`,
  `LibreSolar/kicad-symbols`) use a 2.54 mm (100 mil) grid/pin pitch — the
  EDA-industry norm, unrelated to IEC/ISO/ISA and not applicable to
  Schematika's cabinet/P&ID domains (it *is* the right ballpark for `pcb/`
  if that module ever needs finer pin pitch, but today `pcb/layout_spec.py`
  already defaults `pin_spacing_mm=10.0`, matching `DEFAULT_POLE_SPACING`).
- No dimensional numbers for the ISA 5.1 bubble were found in any open
  source beyond what Schematika's own docstring already states (12 mm
  diameter) — could not independently corroborate or contradict it from a
  free source; the 1992-reaffirmed ANSI/ISA scan found in search results
  was not fetched (scanned PDF, low confidence of extracting numbers, and
  reproducing extracted standard dimensions verbatim would defeat the
  "don't reproduce copyrighted text" goal anyway).

**Verdict on external standards research**: there is nothing to import.
Schematika's constants files are already better documented than the open
alternatives. The only actionable output of this part of the research is
the ISO 81714-1 line-width-ratio cross-check above, which is corroborating,
not corrective.

## 3. Gap analysis: existing symbols vs. what a real drawing needs

### Electrical (`src/schematika/electrical/symbols/`)

Existing factories (12 files, exported from `electrical/__init__.py`):
`no_contact`, `nc_contact`, `spdt_contact`, `coil`, `breaker`,
`thermal_overload`, `fuse`, `motor`, `contactor`, `estop`, `estop_button`,
`turn_switch`, `turn_actuator`, `terminal`, `terminal_box`, `psu`, `block`,
`ref_symbol`, `ct`, `ct_assembly`, `connector_pin`.

| Missing symbol | Why it matters | Notes |
|---|---|---|
| **Indicator light / pilot lamp** | Every start/stop station in a real cabinet has run/fault/power lamps. Currently **zero** lamp symbol exists despite `StandardTags.INDICATOR = "H"` already being reserved. | Highest-value gap — full spec below. |
| **Control transformer** | Cabinets routinely step 400V→230V or 230V→24V for control circuits. `StandardTags.TRANSFORMER = "T"` is reserved but **no factory exists at all**. | Full spec below. |
| Selector switch (multi-position, e.g. HOA) | Ubiquitous on motor control panels. `turn_switch`/`turn_actuator` only cover a 2-position turn switch + one NO contact, not a 3-position selector with multiple contact blocks. | Medium value |
| Timer relay (on-delay/off-delay) | Very common (motor star-delta, conveyor sequencing). | Medium value — IEC's actual delay pictograph is intricate; lower priority than lamp/transformer for a first cut |
| Disconnect/isolator switch | Distinct from `breaker` (no trip mechanism, just isolation, often padlockable). | Medium value |
| Ground/earth (functional/protective) symbol | `motor` exposes a `PE` port but there's no standalone earth symbol to terminate a PE conductor elsewhere on a page. | Medium value |
| Limit switch / proximity sensor | `StandardTags.SENSOR = "B"` is reserved; no sensor symbol exists (only CT for current sensing). | Lower value (large family, IEC has many variants) |
| Surge protective device (SPD) | Common on incoming supply pages. | Lower value / niche |

### P&ID (`src/schematika/pid/symbols/`)

Existing factories (5 files): `instrument_bubble`, `pipe_segment`,
`pipe_tee`, `pipe_reducer`, `pipe_cap`, `centrifugal_pump`,
`positive_displacement_pump`, `gate_valve`, `globe_valve`, `control_valve`,
`check_valve`, `ball_valve`, `three_way_valve`, `tank`, `heat_exchanger`.

This domain is already **surprisingly complete** — valve coverage in
particular (6 variants) exceeds what most hobbyist P&ID tools ship.

| Missing symbol | Why it matters | Notes |
|---|---|---|
| **Pressure/safety relief valve (PSV)** | Safety-critical; appears on nearly every real P&ID with a pressurized vessel or line. Distinct spring-loaded symbol, not a variant of the 6 existing valves. | Highest-value P&ID gap — full spec below. |
| Filter / strainer | Extremely common inline element (pump suction strainers, instrument air filters). | High value, simple geometry (diamond or triangle inline symbol) |
| Compressor | Only pumps exist; compressors are common in utility/air systems. | Medium value — could largely reuse `_pump_symbol` internals with a different body shape |
| Orifice plate / restriction orifice | Common flow-measurement primitive, pairs with `FE`/`FT` instrument tags. | Medium value |
| Agitator/mixer (on a tank) | Common on reactor/mixing-vessel P&IDs. | Lower value — compositing onto `tank()` rather than a standalone symbol |

### PCB (`src/schematika/pcb/symbols/`)

Existing: `connector_block`, `connector_pin`, `power_24v`, `gnd`. This
module is **not** a schematic-capture/board-layout tool — per
`docs/ARCHITECTURE.md` it bridges a SKiDL netlist into a connector-level
review diagram, not a full symbolic schematic. Passive-component symbols
(resistor/capacitor/diode bodies) are out of scope by design, not a gap:
`pcb/model.py`'s job is which connector pins land on which nets, not what's
between them. No action recommended here.

## 4. Fully-specified missing symbols

All three below reuse existing constants (`GRID_SIZE`, `GRID_SUBDIVISION`,
`PID_STUB_LENGTH`, `VALVE_SIZE`, `PID_ACTUATOR_STEM_HEIGHT`, `PID_TEXT_SIZE_TAG`)
so no new constant file needs inventing — only a handful of new named
constants at the top of each new module, in the same
`GRID_SIZE * ratio  # Xmm — comment` idiom already used throughout.

### 4.1 `indicator_light` (electrical) — highest priority

IEC-family convention: a circle containing an inscribed diagonal cross
("X"), with two leads like a coil.

```
Body:     Circle, center (0, 0), radius = 0.6 * GRID_SIZE   # 3mm
Cross:    two Lines corner-to-corner of the square inscribed in the
          circle, i.e. endpoints at (±r*sin45°, ±r*sin45°):
            Line((-2.12, -2.12), (2.12, 2.12))
            Line((-2.12,  2.12), (2.12, -2.12))
Leads:    pin_len = GRID_SIZE - radius = 2.0mm
          top lead:    Line((0, -3.0), (0, -5.0))
          bottom lead: Line((0,  3.0), (0,  5.0))
Ports:    "1": Point(0, -5.0), Vector(0, -1)   # top, supply
          "2": Point(0,  5.0), Vector(0,  1)   # bottom, return
Label:    at Point(GRID_SIZE * 0.9, 0), left-anchored, e.g. "H1" tag
Color:    optional `color: str | None` kwarg ("R"/"G"/"Y"/"W"/"B");
          rendered as a one-letter Text at Point(-GRID_SIZE*0.9, 0)
          when given (mirrors how `coil` offsets its label for a wider body)
```

Signature (matching the established symbol-factory convention used by
`coil`/`no_contact` — plain positional/keyword args, not the stricter
builder `add_*` rule from `API_STYLE.md`, since these are pure factory
functions, not mutable-builder methods):

```python
def indicator_light(
    label: str = "",
    pins: tuple[str, str] = ("1", "2"),
    *,
    color: str | None = None,
) -> Symbol: ...
```

Docstring `Ports:` block: `1` (top lead, supply), `2` (bottom lead, return)
— numeric convention, same family as `breaker`/`fuse`.

### 4.2 `transformer` (electrical) — two-winding control transformer

Two vertical coil-style rectangles (primary left, secondary right)
separated by a laminated-core gap (two parallel vertical lines) — directly
reuses the geometric language `coil.py` already established, just rotated
90° and duplicated.

```
New constants (electrical/model/constants.py idiom):
  CORE_GAP        = GRID_SUBDIVISION            # 2.5mm, gap between windings
  WINDING_WIDTH   = GRID_SIZE                    # 5mm
  WINDING_HEIGHT  = 2 * GRID_SIZE                 # 10mm

Primary winding box:   box(center=(-3.75, 0), width=WINDING_WIDTH,
                            height=WINDING_HEIGHT)     # x spans [-6.25,-1.25]
Secondary winding box: box(center=( 3.75, 0), width=WINDING_WIDTH,
                            height=WINDING_HEIGHT)     # x spans [ 1.25, 6.25]
Core lines (2x):  Line((-0.625, -4.0), (-0.625, 4.0))
                  Line(( 0.625, -4.0), ( 0.625, 4.0))
Leads (pin_len = GRID_SUBDIVISION = 2.5mm, same as coil.py):
  primary top:    Line((-3.75, -5.0), (-3.75, -7.5))  -> port "1", Vector(0,-1)
  primary bottom: Line((-3.75,  5.0), (-3.75,  7.5))  -> port "2", Vector(0, 1)
  secondary top:    Line((3.75, -5.0), (3.75, -7.5))  -> port "3", Vector(0,-1)
  secondary bottom: Line((3.75,  5.0), (3.75,  7.5))  -> port "4", Vector(0, 1)
Label: at Point(-3.75 - GRID_SIZE, 0), mirrors coil.py's "offset left because
       body is wider than a single lead" rule.
```

Ports: `1`/`2` primary (top/bottom, sequential numeric — same family as a
2-pole breaker's `("1","2")×N` pattern), `3`/`4` secondary. Document at the
factory per `CLAUDE.md`'s port-ID rule.

```python
def transformer(label: str = "", pins: tuple[str, str, str, str] = ("1", "2", "3", "4")) -> Symbol: ...
```

### 4.3 `relief_valve` (P&ID) — pressure/safety relief valve (PSV)

Angle-pattern spring-loaded relief valve. Body reuses the existing
`check_valve` idiom (single triangle in flow direction + perpendicular seat
bar), rotated to vertical flow, with a spring and cap added above.

```
_H = VALVE_SIZE / 2                              # 5mm, same as existing valves

Body triangle: Polygon([(-_H, _H), (_H, _H), (0, 0)])
               # base at top (y=+5), tip at bottom (y=0) — flow enters
               # at the tip and lifts the disc toward the base
Seat bar:      Line((-_H*0.3, 0), (_H*0.3, 0))    # at the tip, mirrors
               # check_valve's downstream seat bar

Spring (new constant):
  PID_SPRING_HEIGHT = PID_ACTUATOR_STEM_HEIGHT     # 8mm, reuse existing
  3-segment zigzag from (0, _H) to (0, _H + 8.0), amplitude ±_H*0.4=±2mm:
    Line((0, 5.0), (-2.0, 6.67))
    Line((-2.0, 6.67), (2.0, 9.33))
    Line((2.0, 9.33), (0, 13.0))

Cap bar (spring housing top, mirrors pipe_cap()'s cap-bar convention):
  PID_CAP_HALF_HEIGHT-style bar at y = _H + PID_SPRING_HEIGHT = 13.0:
    Line((-_H*0.5, 13.0), (_H*0.5, 13.0))

Discharge stub + port ("out", top, discharge to atmosphere/flare):
  Line((0, 13.0), (0, 13.0 + PID_STUB_LENGTH))   # stub, PIPE_STYLE
  Port("out", Point(0, 18.0), Vector(0, 1))

Inlet stub + port ("in", bottom, from process line):
  Line((0, 0), (0, -PID_STUB_LENGTH))            # stub, PIPE_STYLE
  Port("in", Point(0, -5.0), Vector(0, -1))

Label: at Point(_H + PID_LABEL_OFFSET, 0), left-anchored (mirrors how other
       valves place their tag, e.g. gate_valve's _label_text helper, but
       offset sideways instead of above since this symbol is taller than
       it is wide).
```

Ports: `in` (bottom, inlet), `out` (top, discharge) — same two-port
`"in"`/`"out"` family already used by every valve in `valves.py`.

```python
def relief_valve(label: str = "") -> Symbol: ...
```

## 5. Verdict

- **Standards research**: nothing to port in. Schematika's own constants
  files are more rigorous than the open alternatives found. The one
  actionable cross-check (ISO 81714-1's 1:10 line-width:module ratio)
  corroborates the existing `PID_EQUIPMENT_STROKE`/`GRID_SIZE` ratio rather
  than revealing an error. **Drop further standards-document research** —
  diminishing returns, real specs are paywalled, and Schematika already
  out-documents the free alternatives.
- **Gap analysis**: real, actionable gaps exist, concentrated in electrical
  (`indicator_light`, `transformer` — both trivial extensions of the
  existing `coil.py` geometric idiom) and one safety-critical P&ID symbol
  (`relief_valve` — trivial extension of the existing `check_valve` idiom).
  PCB has no gap; it's intentionally scoped narrower than a schematic tool.
- **Top 3 to implement first** (ranked by real-cabinet/P&ID frequency ×
  implementation cost, cheapest and most-needed first):
  1. `indicator_light` — every cabinet needs it, zero existing overlap,
     ~20 lines following `coil.py`'s pattern exactly.
  2. `relief_valve` — safety-critical, appears on most real P&IDs,
     ~30 lines directly adapting `check_valve`'s triangle+seat-bar idiom.
  3. `transformer` — less frequent than a lamp but the tag prefix already
     exists with no symbol to back it, and the geometry is a direct
     side-by-side duplication of `coil.py`'s existing box+lead pattern.
- These three are recommended as a **fast-follow implementation task**
  outside this spike (this track is research-only per the spike's own
  scope), not as prototype code within this branch.
