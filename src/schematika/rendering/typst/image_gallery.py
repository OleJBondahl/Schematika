"""Typst page-body builders for image galleries (renders, placement drawings)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


def page_wrapper(
    title: str,
    body: str,
    /,
    *,
    pad_left_mm: int = 15,
    pad_right_mm: int = 15,
    pad_top_mm: int = 15,
    pad_bottom_mm: int = 20,
) -> str:
    """Wrap `body` in a page with a centered bold title and standard padding.

    Examples:
        >>> "Title" in page_wrapper("Title", "body")
        True
    """
    return (
        f"#pad(left: {pad_left_mm}mm, right: {pad_right_mm}mm, "
        f"top: {pad_top_mm}mm, bottom: {pad_bottom_mm}mm)[\n"
        "  #align(center)[\n"
        f'    #text(size: 18pt, weight: "bold")[{title}]\n'
        "  ]\n"
        "  #v(1em)\n\n"
        f"  {body}\n"
        "]"
    )


def image_row_page(
    images: Sequence[tuple[str, str]],
    title: str,
    /,
    *,
    page_width_mm: int = 380,
    gutter_mm: int = 4,
    max_height_mm: int = 200,
    empty_message: str = "No images available.",
) -> str:
    """One page with `images` (path, caption) shown side by side, equal width.

    Each image is capped by both width and height (`fit: "contain"`) so a
    tall-aspect image can't overflow a page sized for wide ones.

    Args:
        images: `(image_path, caption)` pairs, already filtered to existing
            files by the caller -- this function does no filesystem checks.
        title: Page title.
        page_width_mm: Total width the row of images splits across.
        gutter_mm: Gap between adjacent images.
        max_height_mm: Height cap applied to every image.
        empty_message: Body text shown when `images` is empty.

    Examples:
        >>> "No images" in image_row_page([], "Renders")
        True
    """
    if not images:
        return page_wrapper(title, empty_message)
    n = len(images)
    col_width_mm = (page_width_mm - gutter_mm * (n - 1)) // n
    cells = [
        f'[#align(center)[#image("{path}", '
        f'width: {col_width_mm}mm, height: {max_height_mm}mm, fit: "contain")\n'
        f"  #v(0.5em) {caption}]]"
        for path, caption in images
    ]
    cell_list = ",\n    ".join(cells)
    body = (
        f"#grid(\n    columns: {n},\n    gutter: {gutter_mm}mm,\n    {cell_list}\n  )"
    )
    return page_wrapper(title, body)


def image_full_page(
    image_path: str,
    caption: str,
    title: str,
    /,
    *,
    width_mm: int = 380,
    height_mm: int = 220,
) -> str:
    """One page with a single full-size image and caption.

    Examples:
        >>> "diagram.svg" in image_full_page("diagram.svg", "Top", "Placement")
        True
    """
    body = (
        f'#align(center)[#image("{image_path}", '
        f'width: {width_mm}mm, height: {height_mm}mm, fit: "contain")\n'
        f"  #v(0.5em) {caption}]"
    )
    return page_wrapper(title, body)
