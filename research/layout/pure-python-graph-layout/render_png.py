"""Rasterize an SVG to PNG for visual review (throwaway spike helper)."""

import sys

import fitz


def main() -> None:
    svg_path, png_path = sys.argv[1], sys.argv[2]
    doc = fitz.open(svg_path)
    page = doc[0]
    pix = page.get_pixmap(matrix=fitz.Matrix(4, 4))
    pix.save(png_path)


if __name__ == "__main__":
    main()
