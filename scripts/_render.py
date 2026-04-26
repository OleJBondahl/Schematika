"""Shared SVG→PNG renderer.

Tries ``cairosvg`` first, falls back to Playwright (Chromium) when Cairo's
native libraries are unavailable on the host (typical on Windows).
"""

from __future__ import annotations

from pathlib import Path


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
        from playwright.sync_api import sync_playwright

        # A3 landscape at approximate DPI
        width = int(297 * dpi / 96)
        height = int(210 * dpi / 96)

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": width, "height": height})
            page.goto(f"file:///{svg.resolve().as_posix()}")
            page.wait_for_timeout(2000)
            page.screenshot(path=str(png), timeout=60000)
            browser.close()

    return str(png)
