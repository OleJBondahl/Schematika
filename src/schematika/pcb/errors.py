"""Errors for schematika.pcb module."""


class PCBBuildError(ValueError):
    """Base exception for PCB building and mapping errors.

    Inherits from ``ValueError`` for backward-compat with call sites that
    catch ``ValueError``; new code should catch ``PCBBuildError`` (or a
    subclass) explicitly.

    Examples:
        >>> from schematika.pcb import PCBBuildError
        >>> try:
        ...     raise PCBBuildError("bad mapping")
        ... except PCBBuildError as e:
        ...     str(e)
        'bad mapping'
    """


class PinNotOnTemplateError(PCBBuildError):
    """Raised when a SymbolSlice references a pin not on the SKiDL template."""

    def __init__(
        self,
        template_name: str,
        pin_name: str,
        available_pins: list[str],
    ) -> None:
        """Capture template/pin/available-pins context for the error message."""
        self.template_name = template_name
        self.pin_name = pin_name
        self.available_pins = available_pins
        super().__init__(
            f"Pin '{pin_name}' not found on template '{template_name}'. "
            f"Available pins: {available_pins}. "
            f"Check the SKiDL part definition."
        )


class PortNotOnSymbolError(PCBBuildError):
    """Raised when a SymbolSlice maps to a port not on the Schematika symbol."""

    def __init__(
        self,
        symbol_name: str,
        port_name: str,
        available_ports: list[str],
    ) -> None:
        """Capture symbol/port/available-ports context for the error message."""
        self.symbol_name = symbol_name
        self.port_name = port_name
        self.available_ports = available_ports
        super().__init__(
            f"Port '{port_name}' not found on symbol '{symbol_name}'. "
            f"Available ports: {available_ports}. "
            f"Update the pin_map to use a valid port name."
        )


class MultiPinSliceError(PCBBuildError):
    """Raised when a SymbolSlice pin_map has !=2 entries (v1: 2-pin only)."""

    def __init__(
        self,
        template_name: str,
        pin_count: int,
    ) -> None:
        """Capture template name + actual pin count for the error message."""
        self.template_name = template_name
        self.pin_count = pin_count
        super().__init__(
            f"SymbolSlice for template '{template_name}' has {pin_count} pins, "
            f"but v1 only supports exactly 2 pins per slice. "
            f"Use separate SymbolSlice objects or add multi-pin support."
        )


class IncompleteSliceError(PCBBuildError):
    """Raised when slices don't cover all pins or duplicate pins of a template."""

    def __init__(
        self,
        template_name: str,
        mapped_pins: list[str],
        all_pins: list[str],
    ) -> None:
        """Diff mapped vs all pins to surface missing or duplicated entries."""
        self.template_name = template_name
        self.mapped_pins = mapped_pins
        self.all_pins = all_pins
        missing = set(all_pins) - set(mapped_pins)
        duplicated = [p for p in mapped_pins if mapped_pins.count(p) > 1]
        detail = ""
        if missing:
            detail += f"Missing pins: {list(missing)}. "
        if duplicated:
            detail += f"Duplicated pins: {list(set(duplicated))}. "
        super().__init__(
            f"Incomplete pin mapping for template '{template_name}'. "
            f"{detail}Ensure all pins are mapped exactly once."
        )


class DuplicateMappingError(PCBBuildError):
    """Raised when a template or net_name is mapped more than once."""

    def __init__(
        self,
        mapping_type: str,
        identifier: str,
    ) -> None:
        """Capture which mapping kind + key was duplicated."""
        self.mapping_type = mapping_type
        self.identifier = identifier
        super().__init__(
            f"Duplicate {mapping_type} '{identifier}' in mapping. "
            f"Remove the duplicate entry."
        )


class UnmappedPartError(PCBBuildError):
    """Raised when a SKiDL part has no corresponding SymbolMap or ConnectorMap."""

    def __init__(
        self,
        part_ref: str,
        template_name: str,
    ) -> None:
        """Capture the unmapped part_ref + its SKiDL template name."""
        self.part_ref = part_ref
        self.template_name = template_name
        super().__init__(
            f"Part '{part_ref}' (template '{template_name}') has no mapping. "
            f"Add a SymbolMap or ConnectorMap entry."
        )


class BottomTerminatorOrphanNetError(PCBBuildError):
    """A net touches only bottom-terminator connectors and non-connectors.

    There's no header block to root the chain from — the net cannot be walked.

    Examples:
        >>> err = BottomTerminatorOrphanNetError(net_name="/foo", parts=["J7", "K1"])
        >>> "foo" in str(err)
        True
    """

    def __init__(self, net_name: str, parts: list[str]) -> None:
        """Capture net name and the parts it touches."""
        self.net_name = net_name
        self.parts = parts
        super().__init__(
            f"Net {net_name!r} touches only bottom-terminator connectors and "
            f"non-connector parts {parts}. "
            f"At least one non-bottom-terminator connector must connect to this net."
        )


class UnnamedNetError(PCBBuildError):
    """Raised when strict_net_names is True and a multi-pin net would render as N$N.

    Args:
        net_id: SKiDL's auto-generated net identifier (e.g. "N$4").
        pin_count: Number of pins on the offending net.

    Examples:
        >>> err = UnnamedNetError(net_id="N$4", pin_count=3)
        >>> "N$4" in str(err)
        True
    """

    def __init__(self, *, net_id: str, pin_count: int) -> None:
        """Store net_id and pin_count; provide actionable error message."""
        self.net_id = net_id
        self.pin_count = pin_count
        super().__init__(
            f"net {net_id!r} has {pin_count} pins but no explicit name — "
            "give it a name via Net('/my_signal') or set strict_net_names=False",
        )
