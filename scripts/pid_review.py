#!/usr/bin/env python3
"""P&ID review tool — converts SVG to PNG for visual inspection.

Tries cairosvg first, falls back to Playwright (Chromium) on Windows
where the native Cairo library is often unavailable.
"""

import re
import sys
from pathlib import Path

_MM_DIMENSIONS = re.compile(r'width="([\d.]+)mm"\s+height="([\d.]+)mm"')
_MAX_VIEWPORT_PX = 8000  # Chromium's practical single-screenshot ceiling


def _svg_pixel_size(svg_text: str, dpi: int) -> tuple[int, int]:
    """Viewport size matching the SVG's own aspect ratio, not a fixed page size.

    A hardcoded A3-landscape viewport silently cropped tall electrical-ladder
    SVGs (portrait, often far taller than 210mm) instead of erroring --
    this is what let a broken layout ship without anyone noticing on review.
    Falls back to A3 landscape only when the SVG has no mm-denominated
    width/height to read.
    """
    match = _MM_DIMENSIONS.search(svg_text)
    if match:
        width_mm, height_mm = float(match.group(1)), float(match.group(2))
    else:
        width_mm, height_mm = 297.0, 210.0  # A3 landscape
    scale = dpi / 96
    width_px = min(int(width_mm * scale), _MAX_VIEWPORT_PX)
    height_px = min(int(height_mm * scale), _MAX_VIEWPORT_PX)
    return width_px, height_px


def svg_to_png(svg_path: str, dpi: int = 300) -> str:
    """Convert SVG to PNG, return PNG path."""
    svg = Path(svg_path)
    png = svg.with_suffix(".png")

    try:
        import cairosvg

        cairosvg.svg2png(
            url=str(svg.resolve()),
            write_to=str(png),
            dpi=dpi,
        )
    except (ImportError, OSError):
        # Fallback: Playwright with bundled Chromium
        from playwright.sync_api import sync_playwright

        width, height = _svg_pixel_size(svg.read_text(encoding="utf-8"), dpi)

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": width, "height": height})
            page.goto(f"file:///{svg.resolve().as_posix()}")
            page.wait_for_timeout(2000)
            page.screenshot(path=str(png), timeout=60000)
            browser.close()

    return str(png)


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/pid_review.py <svg_file>")
        sys.exit(1)

    svg_path = sys.argv[1]
    if not Path(svg_path).exists():
        print(f"Error: {svg_path} not found")
        sys.exit(1)

    png_path = svg_to_png(svg_path)
    print(f"PNG rendered: {png_path}")


if __name__ == "__main__":
    main()
