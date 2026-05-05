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
    page_top_margin_mm: float = 30.0
    page_left_margin_mm: float = 15.0
    power_terminator_offset_mm: float = 5.0
    connector_to_first_slice_gap_mm: float = 15.0
