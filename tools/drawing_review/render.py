"""Rendering utilities for converting SVG and PDF drawings to PNG."""

from pathlib import Path


def render_svg_to_png(
    svg_path: str,
    output_path: str | None = None,
    dpi: int = 300,
) -> str:
    """Render SVG to PNG. Returns PNG path.

    Tries cairosvg first, falls back to Playwright (Chromium) on Windows
    where the native Cairo library is often unavailable.

    Args:
        svg_path: Path to the source SVG file.
        output_path: Destination PNG path. Defaults to SVG path with .png suffix.
        dpi: Resolution in dots per inch (default: 300).

    Returns:
        The path to the rendered PNG file.
    """
    svg = Path(svg_path)
    png = Path(output_path) if output_path else svg.with_suffix(".png")

    try:
        import cairosvg

        cairosvg.svg2png(
            url=str(svg.resolve()),
            write_to=str(png),
            dpi=dpi,
        )
    except (ImportError, OSError):
        from playwright.sync_api import sync_playwright

        width = int(420 * dpi / 96)
        height = int(297 * dpi / 96)

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": width, "height": height})
            page.goto(f"file:///{svg.resolve().as_posix()}")
            page.wait_for_timeout(2000)
            page.screenshot(path=str(png), timeout=60000)
            browser.close()

    return str(png)


def render_pdf_page_to_png(
    pdf_path: str,
    page: int = 0,
    output_path: str | None = None,
    dpi: int = 300,
) -> str:
    """Render a PDF page to PNG using PyMuPDF. Returns PNG path.

    Args:
        pdf_path: Path to the source PDF file.
        page: Zero-based page index to render (default: 0).
        output_path: Destination PNG path. Defaults to ``<pdf_stem>_p<page>.png``.
        dpi: Resolution in dots per inch (default: 300).

    Returns:
        The path to the rendered PNG file.
    """
    import fitz

    pdf = Path(pdf_path)
    if output_path:
        png = Path(output_path)
    else:
        png = pdf.with_name(f"{pdf.stem}_p{page}.png")

    doc = fitz.open(str(pdf))
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    pixmap = doc[page].get_pixmap(matrix=mat)
    pixmap.save(str(png))
    doc.close()

    return str(png)
