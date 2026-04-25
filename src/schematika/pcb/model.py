"""Frozen dataclasses for the SKiDL -> Schematika mapping and build result."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final, Literal

from schematika.core.symbol import Symbol, SymbolFactory

from .adapter import template_name as _template_name
from .errors import (
    DuplicateMappingError,
    IncompleteSliceError,
    MultiPinSliceError,
    PinNotOnTemplateError,
    PortNotOnSymbolError,
)

# Each slice maps exactly two pins: one from each symbol in the slice pair.
_PINS_PER_SLICE: Final = 2


def _template_pin_nums(template: Any) -> list[str]:  # noqa: ANN401
    return [str(p.num) for p in getattr(template, "pins", ())]


def _symbol_port_names(symbol: Symbol) -> list[str]:
    return list(symbol.ports.keys())


@dataclass(frozen=True)
class SymbolSlice:
    """A single symbol factory paired with a KiCad pin-to-port mapping."""

    symbol: SymbolFactory
    pin_map: Mapping[str, str]


@dataclass(frozen=True)
class SymbolMap:
    """KiCad netlist template → one or more ``SymbolSlice`` instances."""

    template: Any
    slices: tuple[SymbolSlice, ...]


@dataclass(frozen=True)
class ConnectorMap:
    """KiCad connector template → per-pin symbol factory + board position."""

    template: Any
    pin_symbol: SymbolFactory
    position: Literal["top", "bottom"]


@dataclass(frozen=True)
class PowerNetMap:
    """Mapping from a KiCad power net name to the symbol factory used to render it."""

    net_name: str
    symbol: SymbolFactory


@dataclass(frozen=True)
class SymbolMapping:
    """Full mapping config: KiCad netlist components → schematic symbols."""

    symbols: tuple[SymbolMap, ...]
    connectors: tuple[ConnectorMap, ...]
    power_nets: tuple[PowerNetMap, ...] = ()

    def __post_init__(self) -> None:
        """Validate the mapping for duplicate templates and port/pin consistency."""
        self._check_duplicate_symbol_templates()
        self._check_duplicate_connector_templates()
        self._check_duplicate_power_net_names()
        for smap in self.symbols:
            self._validate_symbol_map(smap)
        for cmap in self.connectors:
            self._validate_connector_map(cmap)
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
            if pnet.net_name in seen:
                raise DuplicateMappingError(
                    mapping_type="power_net",
                    identifier=pnet.net_name,
                )
            seen.add(pnet.net_name)

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
                        symbol_name=getattr(slc.symbol, "__name__", "symbol"),
                        port_name=port_name,
                        available_ports=port_names,
                    )
        if sorted(mapped_pins) != sorted(template_pins):
            raise IncompleteSliceError(
                template_name=template_name,
                mapped_pins=mapped_pins,
                all_pins=template_pins,
            )

    def _validate_connector_map(self, cmap: ConnectorMap) -> None:
        sym = cmap.pin_symbol()
        if len(sym.ports) != 1:
            raise PortNotOnSymbolError(
                symbol_name=getattr(cmap.pin_symbol, "__name__", "pin_symbol"),
                port_name="<exactly-one-port-required>",
                available_ports=_symbol_port_names(sym),
            )

    def _validate_power_net_map(self, pnet: PowerNetMap) -> None:
        sym = pnet.symbol()
        if len(sym.ports) != 1:
            raise PortNotOnSymbolError(
                symbol_name=getattr(pnet.symbol, "__name__", "power_symbol"),
                port_name="<exactly-one-port-required>",
                available_ports=_symbol_port_names(sym),
            )


@dataclass(frozen=True)
class PCBBuildResult:
    """Frozen result returned by the PCB builder after a successful build."""

    state: Any
    columns: tuple[tuple[str, Any], ...]
    pages: tuple[tuple[str, tuple[str, ...]], ...] = ()
