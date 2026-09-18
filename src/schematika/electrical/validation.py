"""Electrical schematic layout validation.

Checks a `Circuit` for common layout issues: symbol overlap, text overlap,
page boundary violations, and wire geometry defects (non-orthogonal
segments, text/wire collisions, near-miss pin alignment, redundant jogs).
"""

from schematika.core.renderer import calculate_bounds
from schematika.core.symbol import Symbol
from schematika.core.validation import (
    ValidationResult,
    boxes_overlap,
    check_page_bounds,
    check_text_overlap,
    check_wire_geometry,
)
from schematika.electrical.system.system import Circuit


def _check_symbol_overlap(
    symbols: list[Symbol],
    bounds_cache: list[tuple[float, float, float, float]],
) -> list[str]:
    return [
        f"Symbol overlap: '{symbols[i].label}' and '{symbols[j].label}' "
        "bounding boxes intersect"
        for i in range(len(symbols))
        for j in range(i + 1, len(symbols))
        if boxes_overlap(bounds_cache[i], bounds_cache[j])
    ]


def validate_electrical(
    circuit: Circuit,
    page_width: float = 210.0,
    page_height: float = 297.0,
    margin: float = 10.0,
) -> ValidationResult:
    """Validate an electrical schematic layout.

    Args:
        circuit: The circuit to validate.
        page_width: Page width in mm (default A4 portrait: 210).
        page_height: Page height in mm (default A4 portrait: 297).
        margin: Minimum margin from page edge in mm (default: 10).

    Returns:
        A ValidationResult with any errors and warnings found.
    """
    symbols = circuit.symbols
    bounds_cache = [calculate_bounds(sym.elements) for sym in symbols]

    errors: list[str] = []
    warnings: list[str] = []

    errors.extend(_check_symbol_overlap(symbols, bounds_cache))
    warnings.extend(check_text_overlap(circuit.elements))
    errors.extend(
        check_page_bounds(
            symbols,
            bounds_cache,
            page_width,
            page_height,
            margin,
            label_fn=lambda sym: f"Symbol {sym.label}",
        )
    )
    warnings.extend(check_wire_geometry(circuit.elements))

    return ValidationResult(passed=len(errors) == 0, warnings=warnings, errors=errors)
