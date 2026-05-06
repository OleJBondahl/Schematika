"""Frozen dataclasses for the SKiDL → Schematika.pcb mapping and build result.

This is the v2 shape — connector-anchored layout, alias-matched power nets,
ConnectorBlock-as-anchor.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Final

from schematika.core.symbol import Symbol, SymbolFactory

from .adapter import template_name as _template_name
from .errors import (
    DuplicateMappingError,
    IncompleteSliceError,
    MultiPinSliceError,
    PinNotOnTemplateError,
    PortNotOnSymbolError,
)
from .layout_spec import LayoutSpec

_PINS_PER_SLICE: Final = 2


def _template_pin_nums(template: Any) -> list[str]:  # noqa: ANN401
    return [str(p.num) for p in getattr(template, "pins", ())]


def _symbol_port_names(symbol: Symbol) -> list[str]:
    return list(symbol.ports.keys())


# --- Mapping inputs -------------------------------------------------------


@dataclass(frozen=True)
class SymbolSlice:
    """A single symbol factory paired with a pin-to-port mapping (exactly 2 pins)."""

    symbol: SymbolFactory
    pin_map: Mapping[str, str]


@dataclass(frozen=True)
class SymbolMap:
    """SKiDL template → tuple of SymbolSlices (1+ slices)."""

    template: Any
    slices: tuple[SymbolSlice, ...]


@dataclass(frozen=True)
class ConnectorMap:
    """Marker dataclass: presence flags this template as a connector.

    Functional label comes from ``part.description``, not from the map.
    Future hint fields (e.g. orientation) extend this dataclass.
    """

    template: Any
    bottom_terminator: bool = False


@dataclass(frozen=True)
class PowerNetMap:
    """SKiDL net name (canonical + aliases) → power symbol factory."""

    canonical_name: str
    symbol: SymbolFactory
    aliases: tuple[str, ...] = ()

    def matches(self, net_name: str) -> bool:
        """Return True if ``net_name`` (with leading slash stripped) matches."""
        stripped = net_name.lstrip("/")
        if stripped == self.canonical_name.lstrip("/"):
            return True
        return any(stripped == a.lstrip("/") for a in self.aliases)


@dataclass(frozen=True)
class SymbolMapping:
    """Full mapping config: SKiDL components → schematic symbols."""

    symbols: tuple[SymbolMap, ...]
    connectors: tuple[ConnectorMap, ...]
    power_nets: tuple[PowerNetMap, ...] = ()

    def __post_init__(self) -> None:
        """Validate mapping for duplicate templates and port/pin consistency."""
        self._check_duplicate_symbol_templates()
        self._check_duplicate_connector_templates()
        self._check_duplicate_power_net_names()
        for smap in self.symbols:
            self._validate_symbol_map(smap)
        for pnet in self.power_nets:
            self._validate_power_net_map(pnet)

    def _check_duplicate_symbol_templates(self) -> None:
        seen: set[int] = set()
        for smap in self.symbols:
            key = id(smap.template)
            if key in seen:
                raise DuplicateMappingError(
                    mapping_type="symbol",
                    identifier=_template_name(smap.template),
                )
            seen.add(key)

    def _check_duplicate_connector_templates(self) -> None:
        seen: set[int] = set()
        for cmap in self.connectors:
            key = id(cmap.template)
            if key in seen:
                raise DuplicateMappingError(
                    mapping_type="connector",
                    identifier=_template_name(cmap.template),
                )
            seen.add(key)

    def _check_duplicate_power_net_names(self) -> None:
        seen: set[str] = set()
        for pnet in self.power_nets:
            if pnet.canonical_name in seen:
                raise DuplicateMappingError(
                    mapping_type="power_net",
                    identifier=pnet.canonical_name,
                )
            seen.add(pnet.canonical_name)

    def _validate_symbol_map(self, smap: SymbolMap) -> None:
        template_name = _template_name(smap.template)
        template_pins = _template_pin_nums(smap.template)
        mapped_pins: list[str] = []
        for slc in smap.slices:
            if len(slc.pin_map) != _PINS_PER_SLICE:
                raise MultiPinSliceError(
                    template_name=template_name,
                    pin_count=len(slc.pin_map),
                )
            for pin_key in slc.pin_map:
                if pin_key not in template_pins:
                    raise PinNotOnTemplateError(
                        template_name=template_name,
                        pin_name=pin_key,
                        available_pins=template_pins,
                    )
                mapped_pins.append(pin_key)
            sym = slc.symbol()
            port_names = _symbol_port_names(sym)
            for port_name in slc.pin_map.values():
                if port_name not in sym.ports:
                    raise PortNotOnSymbolError(
                        symbol_name=_template_name(slc.symbol),
                        port_name=port_name,
                        available_ports=port_names,
                    )
        if sorted(mapped_pins) != sorted(template_pins):
            raise IncompleteSliceError(
                template_name=template_name,
                mapped_pins=mapped_pins,
                all_pins=template_pins,
            )

    def _validate_power_net_map(self, pnet: PowerNetMap) -> None:
        sym = pnet.symbol()
        if len(sym.ports) != 1:
            raise PortNotOnSymbolError(
                symbol_name=_template_name(pnet.symbol),
                port_name="<exactly-one-port-required>",
                available_ports=_symbol_port_names(sym),
            )


# --- Build outputs --------------------------------------------------------


class Terminator(Enum):
    """How a column ends visually."""

    POWER = "power"
    LABEL = "label"
    NC = "nc"
    CONTINUATION = "continuation"
    PIN_AT_BOTTOM = "pin_at_bottom"


@dataclass(frozen=True)
class PinPlacement:
    """Where a slice's pin sits within the column."""

    pin_id: str
    port_name: str


@dataclass(frozen=True)
class PlacedSlice:
    """One symbol slice placed in a column."""

    part_ref: str
    slice_index: int
    symbol: Symbol
    pins: tuple[PinPlacement, ...]


@dataclass(frozen=True)
class Column:
    """Vertical stack of placed slices ending in a terminator."""

    slices: tuple[PlacedSlice, ...]
    terminator: Terminator
    terminator_label: str | None = None
    chain_net_name: str | None = None


@dataclass(frozen=True)
class PinColumns:
    """All columns originating from one connector pin."""

    pin_id: str
    columns: tuple[Column, ...]


@dataclass(frozen=True)
class ConnectorBlock:
    """One connector rendered as a unified anchor + per-pin column groups."""

    connector_ref: str
    functional_label: str | None
    pin_columns: tuple[PinColumns, ...]
    max_chain_height_mm: float = 0.0
    # Distance from the connector's own origin_y_mm down to the deepest
    # terminator point across all pins. Computed by the walker (see
    # walk.compute_max_chain_height_mm). Used by pack_pages to decide
    # whether a row-1 block leaves room for a row-2 below it.
    bottom_terminator: bool = False


@dataclass(frozen=True)
class FloatingPart:
    """A mapped part with at least one slice not reachable from any connector.

    ``slice_indices`` lists every unowned slice of the part. The renderer draws
    one symbol per index; the completeness check (PCB017) asserts every
    declared slice is either placed in a ConnectorBlock or appears here.
    """

    part_ref: str
    slice_indices: tuple[int, ...] = ()


@dataclass(frozen=True)
class Page:
    """One rendered page.

    Each entry in ``placements`` is ``(connector_ref, origin_x_mm, origin_y_mm)``
    where ``origin_x_mm`` is the left edge of that connector block in mm
    relative to the page left margin and ``origin_y_mm`` is the top edge of
    that connector block in mm relative to the page top margin. With
    two-row packing, blocks in row 1 share one origin_y and blocks in row 2
    share another.
    """

    title: str
    placements: tuple[tuple[str, float, float], ...]
    floating_part_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class PCBBuildResult:
    """Frozen result of pcb.build()."""

    state: Any
    connector_blocks: tuple[ConnectorBlock, ...]
    floating_parts: tuple[FloatingPart, ...] = ()
    pages: tuple[Page, ...] = ()
    mapping: "SymbolMapping | None" = None
    layout: LayoutSpec = field(default_factory=LayoutSpec)
    max_symbols_per_column: int = 2
    page_size: tuple[float, float] = (250.0, 297.0)
    ir: Any = None
