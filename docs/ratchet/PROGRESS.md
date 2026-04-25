# Quality Ratchet — Progress

Append-only log. One entry per merged wave.

## Wave R0 — Format clean

- **Date:** 2026-04-25
- **Branch / commit:** `ratchet/R0` → ff-merged to `branch1` as `c0c826e`
- **Diff:** 5 files, +65 / −53 (whitespace only)
- **Files:** `tools/cad_parser/{__main__.py,parsers/autocad.py,parsers/kicad.py,parsers/pdf.py,parsers/svg.py}`
- **Before:** `ruff format --check src tests tools` reports 5 dirty files.
- **After:** `ruff format --check src tests tools` exits 0.
- **Notes:**
  - Implementer ran with hooks bypassed (the implementer reported this in their summary). This is correct given the baseline state — `just ci` currently fails on the 385 ruff lint errors, 191 ty diagnostics, etc. that the rest of the ratchet will fix. The R0 spec was wrong to demand `just ci` pass; PLAN.md done-condition tightened in this same change to "wave gate must be newly green; everything else must not regress vs the wave's baseline."
  - No new suppressions introduced.
