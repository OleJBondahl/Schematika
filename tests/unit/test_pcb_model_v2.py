"""Tests for the rewritten schematika.pcb.model dataclasses."""

import pytest

from schematika.pcb.builder import create_initial_state
from schematika.pcb.errors import DuplicateMappingError
from schematika.pcb.layout_spec import LayoutSpec
from schematika.pcb.model import (  # noqa: F401
    Column,
    ConnectorBlock,
    ConnectorMap,
    Page,
    PCBBuildResult,
    PlacedSlice,
    PowerNetMap,
    SymbolMap,
    SymbolMapping,
    SymbolSlice,
    Terminator,
)
from schematika.pcb.symbols.power import gnd, power_24v


def test_power_net_map_supports_aliases() -> None:
    pm = PowerNetMap(canonical_name="+24V", symbol=power_24v, aliases=("/v24", "/V24"))
    assert pm.aliases == ("/v24", "/V24")


def test_power_net_map_alias_default_is_empty() -> None:
    pm = PowerNetMap(canonical_name="GND", symbol=gnd)
    assert pm.aliases == ()


def test_symbol_mapping_rejects_duplicate_power_canonical_names() -> None:
    pm1 = PowerNetMap(canonical_name="GND", symbol=gnd)
    pm2 = PowerNetMap(canonical_name="GND", symbol=gnd)
    with pytest.raises(DuplicateMappingError):
        SymbolMapping(symbols=(), connectors=(), power_nets=(pm1, pm2))


def test_terminator_kinds_enumerated() -> None:
    assert Terminator.POWER.value == "power"
    assert Terminator.LABEL.value == "label"
    assert Terminator.NC.value == "nc"
    assert Terminator.CONTINUATION.value == "continuation"


def test_pcb_build_result_default_floating_parts_empty() -> None:
    result = PCBBuildResult(
        state=create_initial_state(),
        connector_blocks=(),
        floating_parts=(),
        pages=(),
    )
    assert result.floating_parts == ()


def test_connector_map_is_marker_only() -> None:
    template_sentinel = object()
    cmap = ConnectorMap(template=template_sentinel)
    assert cmap.template is template_sentinel


def test_pcbbuildresult_carries_layout_max_per_col_and_page_size() -> None:
    r = PCBBuildResult(
        state=create_initial_state(),
        connector_blocks=(),
        floating_parts=(),
        pages=(),
        mapping=SymbolMapping(symbols=(), connectors=(), power_nets=()),
        layout=LayoutSpec(),
        max_symbols_per_column=4,
        page_size=(250.0, 297.0),
    )
    assert r.layout.pin_spacing_mm == 10.0
    assert r.max_symbols_per_column == 4
    assert r.page_size == (250.0, 297.0)
