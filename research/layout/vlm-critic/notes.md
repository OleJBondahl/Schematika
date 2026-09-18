# vlm-critic — test artifacts

Rendered from real Schematika example SVGs (`examples/output/*.svg`, tracked
fixtures) to have concrete PNGs to look at for the visual-balance question.

## Rendering gotcha found along the way

`scripts/pid_review.py`'s Playwright fallback (used when `cairosvg` can't load
the native `libcairo` DLL — the case on this machine: `cairocffi` raised
`OSError: no library called "cairo" was found`) opens a **fixed A3-landscape
viewport** (`297mm x 210mm` at the given DPI) and screenshots the viewport,
not the full page. That's correct for P&ID pages (which *are* laid out at
A3) but silently **crops** tall/narrow `electrical` ladder SVGs instead of
erroring — `02_dol_starter.svg` (109mm x 300mm) came back as a landscape PNG
with the bottom of the circuit (`FT1`/`M1`) cut off. Not this track's file to
fix, but worth flagging for whichever track ends up owning a general-purpose
SVG review tool: the viewport should be derived from the SVG's own `viewBox`,
not hardcoded to A3.

For this track's own PNGs I used a small one-off Playwright script sized to
each SVG's `viewBox` (4 px/mm) instead of `pid_review.py`, so the renders
below are complete and undistorted.

## Files

- `01_single_relay.svg` / `.png` — smallest fixture (67mm x 150mm): one coil,
  two terminal blocks.
- `02_dol_starter.svg` / `.png` — direct-on-line motor starter (109mm x
  300mm): 3-phase fuses, contactor, thermal overload, motor.
- `05_multi_builder.svg` / `.png` — three independent circuit fragments
  side by side (K1 coil / PLC-driven K1 / K1 contact driving X4).

See `docs/research/layout-improvement/vlm-critic.md` for the analysis these
feed into.
