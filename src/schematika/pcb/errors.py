"""Errors for schematika.pcb module."""


class PCBBuildError(ValueError):
    """Base exception for PCB building and mapping errors.

    Inherits from ``ValueError`` for backward-compat with call sites that
    catch ``ValueError``; new code should catch ``PCBBuildError`` (or a
    subclass) explicitly.
    """


class PinNotOnTemplateError(PCBBuildError):
    """Raised when a SymbolSlice references a pin not on the SKiDL template."""

    def __init__(
        self,
        template_name: str,
        pin_name: str,
        available_pins: list[str],
    ):
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
    ):
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
    ):
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
    ):
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
    ):
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
    ):
        self.part_ref = part_ref
        self.template_name = template_name
        super().__init__(
            f"Part '{part_ref}' (template '{template_name}') has no mapping. "
            f"Add a SymbolMap or ConnectorMap entry."
        )


class OrphanSliceError(PCBBuildError):
    """Raised when a mapped slice isn't reachable from any terminator."""

    def __init__(
        self,
        part_ref: str,
        slice_index: int,
    ):
        self.part_ref = part_ref
        self.slice_index = slice_index
        super().__init__(
            f"Slice {slice_index} of part '{part_ref}' not reachable from "
            f"any terminator. Circuit may have isolated loop. Check connectivity."
        )


class HeightOverflowError(PCBBuildError):
    """Raised when a single column's rendered height exceeds page height."""

    def __init__(
        self,
        column_key: str,
        height_mm: float,
        max_height_mm: float,
    ):
        self.column_key = column_key
        self.height_mm = height_mm
        self.max_height_mm = max_height_mm
        super().__init__(
            f"Column '{column_key}' height {height_mm:.1f}mm exceeds "
            f"{max_height_mm:.1f}mm. Decompose or increase page size."
        )
