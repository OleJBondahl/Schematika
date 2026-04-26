#!/usr/bin/env python3
"""P&ID review tool — converts SVG to PNG for visual inspection.

Delegates to ``scripts/_render.py``; shared with
``scripts/system_diagram_review.py``.
"""

import sys
from pathlib import Path

from _render import svg_to_png


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
