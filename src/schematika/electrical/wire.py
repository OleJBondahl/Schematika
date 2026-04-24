"""Wire specification helper.

Provides a shorthand `wire()` function for creating wire label strings,
replacing the verbose `format_wire_specification()` calls.
"""

from schematika.electrical.layout.wire_labels import format_wire_specification


class _Wire:
    """Callable wire helper with an EMPTY constant."""

    EMPTY: str = ""

    def __call__(self, color: str, size: str) -> str:
        """Create a wire specification label string.

        Shorthand for format_wire_specification().

        Args:
            color: Wire color code (e.g., "RD", "BK", "BR").
            size: Wire size specification (e.g., "2.5mm2", "0.5mm2").

        Returns:
            Formatted wire specification string.

        Example:
            >>> wire("RD", "2.5mm2")
            'RD 2.5mm2'
        """
        return format_wire_specification(color, size)


wire = _Wire()
