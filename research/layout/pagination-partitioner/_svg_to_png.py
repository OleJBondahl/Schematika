"""SVG->PNG helper sized to the SVG's own intrinsic mm dimensions.

`scripts/pid_review.py` assumes a fixed A3 viewport, which clips this
prototype's wider multi-rung power page. Uses the CSS mm->px ratio
(96/25.4) since that's how a browser sizes a raw `<svg width="Nmm">`
document -- a plain 1mm=1px guess under-sizes the viewport and silently
crops content past its edge.
"""

import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

PX_PER_MM = 96 / 25.4  # CSS mm->px, matching how a browser sizes a raw <svg width="Nmm">


def main() -> None:
    svg_path = Path(sys.argv[1])
    text = svg_path.read_text(encoding="utf-8")
    width_match = re.search(r'width="([\d.]+)mm"', text)
    height_match = re.search(r'height="([\d.]+)mm"', text)
    if width_match is None or height_match is None:
        msg = f"could not find width/height in mm on {svg_path}"
        raise ValueError(msg)
    w = float(width_match.group(1))
    h = float(height_match.group(1))
    width_px = max(int(w * PX_PER_MM), 200)
    height_px = max(int(h * PX_PER_MM), 200)

    png_path = svg_path.with_suffix(".png")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": width_px, "height": height_px})
        page.goto(f"file:///{svg_path.resolve().as_posix()}")
        page.wait_for_timeout(500)
        page.screenshot(path=str(png_path), timeout=120000)
        browser.close()
    print(f"wrote {png_path}")


if __name__ == "__main__":
    main()
