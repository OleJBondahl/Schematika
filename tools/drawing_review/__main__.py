"""CLI entry point for the drawing review tool.

Usage:
    uv run python -m tools.drawing_review render diagram.svg
    uv run python -m tools.drawing_review render reference.pdf --page 0
"""

import argparse
import sys
from pathlib import Path

from tools.drawing_review.render import render_pdf_page_to_png, render_svg_to_png


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="drawing_review",
        description="Render SVG or PDF drawings to PNG for visual review.",
    )
    subparsers = parser.add_subparsers(dest="command")

    render_parser = subparsers.add_parser("render", help="Render a drawing to PNG")
    render_parser.add_argument("input", help="Path to SVG or PDF file")
    render_parser.add_argument(
        "--page", type=int, default=0, help="PDF page (default: 0)"
    )
    render_parser.add_argument(
        "--dpi", type=int, default=300, help="DPI (default: 300)"
    )
    render_parser.add_argument("--output", help="Output PNG path")

    args = parser.parse_args()

    if args.command != "render":
        parser.print_help()
        sys.exit(1)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: {input_path} not found")
        sys.exit(1)

    ext = input_path.suffix.lower()
    if ext == ".svg":
        png = render_svg_to_png(str(input_path), output_path=args.output, dpi=args.dpi)
    elif ext == ".pdf":
        png = render_pdf_page_to_png(
            str(input_path), page=args.page, output_path=args.output, dpi=args.dpi
        )
    else:
        print(f"Error: unsupported file type '{ext}' (expected .svg or .pdf)")
        sys.exit(1)

    print(f"PNG rendered: {png}")


if __name__ == "__main__":
    main()
