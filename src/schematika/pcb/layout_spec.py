"""LayoutSpec — every tweakable spacing/margin constant for pcb rendering."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LayoutSpec:
    """Spacing and margin constants for connector-block layout.

    Every field is in millimeters. Defaults are tuned for the juicebox PCB
    on an A4-landscape page (250 x 297 mm).

    Examples:
        >>> s = LayoutSpec()
        >>> s.pin_spacing_mm
        10.0
        >>> LayoutSpec(pin_spacing_mm=12.0).pin_spacing_mm
        12.0
    """

    pin_spacing_mm: float = 10.0
    side_padding_mm: float = 5.0
    block_height_mm: float = 10.0
    slice_height_mm: float = 15.0
    section_gap_mm: float = 5.0
    inter_block_gap_mm: float = 20.0
    horizontal_margin_mm: float = 30.0  # left + right edges (X-axis)
    vertical_margin_mm: float = 30.0  # top + bottom edges (Y-axis)
    power_terminator_offset_mm: float = 5.0
    connector_to_first_label_gap_mm: float = 2.5
    connector_to_first_symbol_gap_mm: float = 120.0
    wire_to_label_gap_mm: float = 5.0
    bottom_terminator_y_mm: float = 260.0
    row2_origin_y_offset_mm: float = 20.0
    # Offset added to page_height/2 to compute the row-2 connector origin Y.
    # Default A3 landscape (297mm): row 2 origin = 148.5 + 20 = 168.5mm.
