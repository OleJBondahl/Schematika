"""One-time calibration of the linter's text-width table against real
Times New Roman font metrics.

Schematika renders all label/tag/pin text with `font-family: "Times New
Roman"` (`src/schematika/core/constants.py::TEXT_FONT_FAMILY` /
`TEXT_FONT_FAMILY_AUX`, both literally "Times New Roman"). Round 1's
`estimate_text_bbox` used one hand-picked constant (`AVG_CHAR_WIDTH_EM =
0.52`) for every character -- this script replaces that guess with the
font's own advance widths, read directly from the installed Windows font
file via `fontTools`.

This is a PEP 723 standalone script (`uv run --script`), matching
`shapely_compare.py`'s pattern from round 1: fontTools is a calibration-time
tool, never a runtime dependency of `linter.py`. The output is a literal
Python dict pasted into `linter.py::CHAR_WIDTH_EM` -- baked in once, not
read from disk at lint time (keeps the linter stdlib-only and independent of
whether a given CI machine has Times New Roman installed).

Run with:
    uv run --script research/layout/deepdive-svg-geometry-linter/calibrate_text_metrics.py
"""

# /// script
# requires-python = ">=3.14"
# dependencies = ["fonttools==4.60.1"]
# ///

import string
import sys
from pathlib import Path

from fontTools.ttLib import TTFont

FONT_PATH = Path(r"C:\Windows\Fonts\times.ttf")

# The character set Schematika's own labels actually use: device tags
# ("-K1", "F1"), wire labels ("BR 2.5", "GY_0_5"), pin/port IDs ("11", "1_no"),
# terminal names ("X1", "PE", "U1"). Covers A-Z, 0-9, and the punctuation
# seen in `WireLabels`/tag formatting.
CHARSET = string.ascii_uppercase + string.digits + " .-_:()/"


def main() -> None:
    if not FONT_PATH.exists():
        print(f"font not found at {FONT_PATH}", file=sys.stderr)
        raise SystemExit(1)

    font = TTFont(str(FONT_PATH))
    units_per_em = font["head"].unitsPerEm  # type: ignore[attr-defined]
    hmtx = font["hmtx"]  # type: ignore[index]
    cmap = font.getBestCmap()
    hhea = font["hhea"]  # type: ignore[index]
    ascent_em = round(hhea.ascent / units_per_em, 4)
    descent_em = round(abs(hhea.descent) / units_per_em, 4)
    print(f"# hhea ascent={ascent_em}em descent={descent_em}em (cap-to-baseline span "
          f"currently hardcoded as TEXT_HEIGHT_EM=0.72 in linter.py)")

    widths_em: dict[str, float] = {}
    missing: list[str] = []
    for ch in CHARSET:
        codepoint = ord(ch)
        glyph_name = cmap.get(codepoint)
        if glyph_name is None:
            missing.append(ch)
            continue
        advance_width, _lsb = hmtx[glyph_name]
        widths_em[ch] = round(advance_width / units_per_em, 4)

    if missing:
        print(f"WARNING: no glyph for: {missing!r}", file=sys.stderr)

    avg = round(sum(widths_em.values()) / len(widths_em), 4)

    print(f"# Calibrated from {FONT_PATH.name}, unitsPerEm={units_per_em}")
    print(f"# {len(widths_em)} glyphs measured, avg width {avg} em")
    print("CHAR_WIDTH_EM: dict[str, float] = {")
    for ch in sorted(widths_em, key=lambda c: (not c.isalnum(), c)):
        key = repr(ch)
        print(f"    {key}: {widths_em[ch]},")
    print("}")
    print(f"DEFAULT_CHAR_WIDTH_EM = {avg}  # fallback for chars outside CHARSET")

    # Sanity spot-check: compare old single-constant estimate vs. calibrated
    # sum for a few real Schematika label strings, so the calibration's
    # practical effect is visible immediately, not just a table dump.
    old_constant = 0.52
    samples = ["BR 2.5", "GY_0_5", "-K1", "PE", "X1", "WWWW", "IIII", "11", "1_no"]
    print("\n# --- old (uniform 0.52em) vs calibrated (per-glyph) width, in font-size units ---")
    for s in samples:
        old_w = len(s) * old_constant
        new_w = sum(widths_em.get(c, avg) for c in s)
        pct = (new_w - old_w) / old_w * 100 if old_w else 0.0
        print(f"# {s!r:>10}: old={old_w:.3f}  calibrated={new_w:.3f}  ({pct:+.1f}%)")


if __name__ == "__main__":
    main()
