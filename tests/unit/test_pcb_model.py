"""Tests for schematika.pcb.model frozen dataclasses and validation rules."""

import pytest
from _factories import (  # noqa: E402 — rootdir-relative import
    factory_with_ports,
    make_fake_template,
)

from schematika.pcb.errors import (
    DuplicateMappingError,
    IncompleteSliceError,
    MultiPinSliceError,
    PinNotOnTemplateError,
    PortNotOnSymbolError,
)
from schematika.pcb.model import (
    ConnectorMap,
    PCBBuildResult,
    PowerNetMap,
    SymbolMap,
    SymbolMapping,
    SymbolSlice,
)

# Common factories used in multiple tests.
two_port_factory = factory_with_ports(("1", "2"))
one_port_factory = factory_with_ports(("1",))
three_port_factory = factory_with_ports(("1", "2", "3"))


# --- dataclass behavior ----------------------------------------------------


def test_symbol_slice_is_frozen():
    slc = SymbolSlice(symbol=two_port_factory, pin_map={"1": "1", "2": "2"})
    with pytest.raises((AttributeError, Exception)):
        slc.symbol = None  # type: ignore[misc]


def test_symbol_mapping_minimal_constructs():
    tpl = make_fake_template("R1", ("1", "2"))
    mapping = SymbolMapping(
        symbols=(
            SymbolMap(
                template=tpl,
                slices=(
                    SymbolSlice(symbol=two_port_factory, pin_map={"1": "1", "2": "2"}),
                ),
            ),
        ),
        connectors=(),
    )
    assert mapping.symbols[0].template is tpl


def test_symbol_mapping_equality():
    tpl = make_fake_template("R1", ("1", "2"))
    a = SymbolMapping(
        symbols=(
            SymbolMap(
                template=tpl,
                slices=(
                    SymbolSlice(symbol=two_port_factory, pin_map={"1": "1", "2": "2"}),
                ),
            ),
        ),
        connectors=(),
    )
    b = SymbolMapping(
        symbols=(
            SymbolMap(
                template=tpl,
                slices=(
                    SymbolSlice(symbol=two_port_factory, pin_map={"1": "1", "2": "2"}),
                ),
            ),
        ),
        connectors=(),
    )
    assert a == b


def test_pcb_build_result_defaults_pages_empty():
    result = PCBBuildResult(state=None, columns=())
    assert result.pages == ()


def test_pcb_build_result_frozen():
    result = PCBBuildResult(state=None, columns=())
    with pytest.raises((AttributeError, Exception)):
        result.state = "x"  # type: ignore[misc]


# --- internal builder-module frozen dataclasses ----------------------------
# Wave 3: mutants 17, 19, 21, 23 flip @dataclass(frozen=True) → frozen=False
# on _PlacedSymbol, _Column, _ConnectorTerminator, _NetEndpointTerminator.


def test_placed_symbol_is_frozen():
    from dataclasses import FrozenInstanceError

    from schematika.pcb.builder import _PlacedSymbol

    ps = _PlacedSymbol(
        part_ref="R1",
        symbol_factory=two_port_factory,
        entry_pin="1",
        tag_prefix="R1",
        rotated=False,
    )
    with pytest.raises(FrozenInstanceError):
        ps.part_ref = "R2"  # type: ignore[misc]


def test_column_is_frozen():
    from dataclasses import FrozenInstanceError

    from schematika.pcb.builder import _Column

    col = _Column(
        key="k",
        placed_symbols=(),
        width_mm=50.0,
        height_mm=40.0,
    )
    with pytest.raises(FrozenInstanceError):
        col.key = "other"  # type: ignore[misc]


def test_connector_terminator_is_frozen():
    from dataclasses import FrozenInstanceError

    from schematika.pcb.builder import _ConnectorTerminator

    c1 = make_fake_template("J1", ("1",))
    cmap = ConnectorMap(template=c1, pin_symbol=one_port_factory, position="top")
    t = _ConnectorTerminator(cmap=cmap, pin_name="1", part_ref="J1")
    with pytest.raises(FrozenInstanceError):
        t.part_ref = "J2"  # type: ignore[misc]


def test_net_endpoint_terminator_is_frozen():
    from dataclasses import FrozenInstanceError
    from types import SimpleNamespace

    from schematika.pcb.builder import _NetEndpointTerminator

    net = SimpleNamespace(name="n", pins=())
    t = _NetEndpointTerminator(net=net, pin_part_ref="R1", pin_name="1")
    with pytest.raises(FrozenInstanceError):
        t.pin_name = "2"  # type: ignore[misc]


# --- rule 1: no duplicate SymbolMap.template -------------------------------


def test_rule1_pass_distinct_symbol_templates():
    t1 = make_fake_template("R1", ("1", "2"))
    t2 = make_fake_template("R2", ("1", "2"))
    SymbolMapping(
        symbols=(
            SymbolMap(
                template=t1,
                slices=(
                    SymbolSlice(symbol=two_port_factory, pin_map={"1": "1", "2": "2"}),
                ),
            ),
            SymbolMap(
                template=t2,
                slices=(
                    SymbolSlice(symbol=two_port_factory, pin_map={"1": "1", "2": "2"}),
                ),
            ),
        ),
        connectors=(),
    )


def test_rule1_fail_duplicate_symbol_template():
    t1 = make_fake_template("R1", ("1", "2"))
    with pytest.raises(DuplicateMappingError) as exc:
        SymbolMapping(
            symbols=(
                SymbolMap(
                    template=t1,
                    slices=(
                        SymbolSlice(
                            symbol=two_port_factory, pin_map={"1": "1", "2": "2"}
                        ),
                    ),
                ),
                SymbolMap(
                    template=t1,
                    slices=(
                        SymbolSlice(
                            symbol=two_port_factory, pin_map={"1": "1", "2": "2"}
                        ),
                    ),
                ),
            ),
            connectors=(),
        )
    assert exc.value.mapping_type == "symbol"


# --- rule 2: no duplicate ConnectorMap.template ----------------------------


def test_rule2_pass_distinct_connector_templates():
    c1 = make_fake_template("J1", ("1",))
    c2 = make_fake_template("J2", ("1",))
    SymbolMapping(
        symbols=(),
        connectors=(
            ConnectorMap(template=c1, pin_symbol=one_port_factory, position="top"),
            ConnectorMap(template=c2, pin_symbol=one_port_factory, position="bottom"),
        ),
    )


def test_rule2_fail_duplicate_connector_template():
    c1 = make_fake_template("J1", ("1",))
    with pytest.raises(DuplicateMappingError) as exc:
        SymbolMapping(
            symbols=(),
            connectors=(
                ConnectorMap(template=c1, pin_symbol=one_port_factory, position="top"),
                ConnectorMap(
                    template=c1, pin_symbol=one_port_factory, position="bottom"
                ),
            ),
        )
    assert exc.value.mapping_type == "connector"


# --- rule 3: no duplicate PowerNetMap.net_name -----------------------------


def test_rule3_pass_distinct_power_net_names():
    SymbolMapping(
        symbols=(),
        connectors=(),
        power_nets=(
            PowerNetMap(net_name="v24", symbol=one_port_factory),
            PowerNetMap(net_name="gnd", symbol=one_port_factory),
        ),
    )


def test_rule3_fail_duplicate_power_net_name():
    with pytest.raises(DuplicateMappingError) as exc:
        SymbolMapping(
            symbols=(),
            connectors=(),
            power_nets=(
                PowerNetMap(net_name="v24", symbol=one_port_factory),
                PowerNetMap(net_name="v24", symbol=one_port_factory),
            ),
        )
    assert exc.value.mapping_type == "power_net"
    assert exc.value.identifier == "v24"


# --- rule 4: pin_map has exactly 2 entries ---------------------------------


def test_rule4_pass_two_entry_pin_map():
    tpl = make_fake_template("R1", ("1", "2"))
    SymbolMapping(
        symbols=(
            SymbolMap(
                template=tpl,
                slices=(
                    SymbolSlice(symbol=two_port_factory, pin_map={"1": "1", "2": "2"}),
                ),
            ),
        ),
        connectors=(),
    )


def test_rule4_fail_one_entry_pin_map():
    tpl = make_fake_template("R1", ("1", "2"))
    with pytest.raises(MultiPinSliceError):
        SymbolMapping(
            symbols=(
                SymbolMap(
                    template=tpl,
                    slices=(SymbolSlice(symbol=one_port_factory, pin_map={"1": "1"}),),
                ),
            ),
            connectors=(),
        )


def test_rule4_fail_three_entry_pin_map():
    tpl = make_fake_template("U1", ("1", "2", "3"))
    with pytest.raises(MultiPinSliceError) as exc:
        SymbolMapping(
            symbols=(
                SymbolMap(
                    template=tpl,
                    slices=(
                        SymbolSlice(
                            symbol=three_port_factory,
                            pin_map={"1": "1", "2": "2", "3": "3"},
                        ),
                    ),
                ),
            ),
            connectors=(),
        )
    assert exc.value.pin_count == 3


# --- rule 5: pin_map key exists on template --------------------------------


def test_rule5_pass_pin_key_present_on_template():
    tpl = make_fake_template("R1", ("1", "2"))
    SymbolMapping(
        symbols=(
            SymbolMap(
                template=tpl,
                slices=(
                    SymbolSlice(symbol=two_port_factory, pin_map={"1": "1", "2": "2"}),
                ),
            ),
        ),
        connectors=(),
    )


def test_rule5_fail_pin_key_not_on_template():
    tpl = make_fake_template("R1", ("1", "2"))
    with pytest.raises(PinNotOnTemplateError) as exc:
        SymbolMapping(
            symbols=(
                SymbolMap(
                    template=tpl,
                    slices=(
                        SymbolSlice(
                            symbol=two_port_factory,
                            pin_map={"1": "1", "99": "2"},
                        ),
                    ),
                ),
            ),
            connectors=(),
        )
    assert exc.value.pin_name == "99"
    assert "1" in exc.value.available_pins
    assert "2" in exc.value.available_pins


# --- rule 6: pin_map value exists as a port on the symbol ------------------


def test_rule6_pass_port_present_on_symbol():
    tpl = make_fake_template("R1", ("1", "2"))
    SymbolMapping(
        symbols=(
            SymbolMap(
                template=tpl,
                slices=(
                    SymbolSlice(symbol=two_port_factory, pin_map={"1": "1", "2": "2"}),
                ),
            ),
        ),
        connectors=(),
    )


def test_rule6_fail_port_not_on_symbol():
    tpl = make_fake_template("R1", ("1", "2"))
    with pytest.raises(PortNotOnSymbolError) as exc:
        SymbolMapping(
            symbols=(
                SymbolMap(
                    template=tpl,
                    slices=(
                        SymbolSlice(
                            symbol=two_port_factory,
                            pin_map={"1": "1", "2": "nope"},
                        ),
                    ),
                ),
            ),
            connectors=(),
        )
    assert exc.value.port_name == "nope"


# --- rule 7: union of slice pin_maps covers all pins exactly once ---------


def test_rule7_pass_two_slices_cover_all_pins():
    tpl = make_fake_template("K1", ("1", "2", "3", "4"))
    SymbolMapping(
        symbols=(
            SymbolMap(
                template=tpl,
                slices=(
                    SymbolSlice(symbol=two_port_factory, pin_map={"1": "1", "2": "2"}),
                    SymbolSlice(symbol=two_port_factory, pin_map={"3": "1", "4": "2"}),
                ),
            ),
        ),
        connectors=(),
    )


def test_rule7_fail_missing_pin():
    tpl = make_fake_template("K1", ("1", "2", "3", "4"))
    with pytest.raises(IncompleteSliceError):
        SymbolMapping(
            symbols=(
                SymbolMap(
                    template=tpl,
                    slices=(
                        SymbolSlice(
                            symbol=two_port_factory,
                            pin_map={"1": "1", "2": "2"},
                        ),
                    ),
                ),
            ),
            connectors=(),
        )


def test_rule7_fail_duplicate_pin_across_slices():
    tpl = make_fake_template("K1", ("1", "2", "3", "4"))
    with pytest.raises(IncompleteSliceError):
        SymbolMapping(
            symbols=(
                SymbolMap(
                    template=tpl,
                    slices=(
                        SymbolSlice(
                            symbol=two_port_factory,
                            pin_map={"1": "1", "2": "2"},
                        ),
                        SymbolSlice(
                            symbol=two_port_factory,
                            pin_map={"1": "1", "3": "2"},
                        ),
                    ),
                ),
            ),
            connectors=(),
        )


# --- rule 8: ConnectorMap.pin_symbol() has exactly one port ----------------


def test_rule8_pass_connector_pin_symbol_single_port():
    c1 = make_fake_template("J1", ("1",))
    SymbolMapping(
        symbols=(),
        connectors=(
            ConnectorMap(template=c1, pin_symbol=one_port_factory, position="top"),
        ),
    )


def test_rule8_fail_connector_pin_symbol_multi_port():
    c1 = make_fake_template("J1", ("1",))
    with pytest.raises(PortNotOnSymbolError):
        SymbolMapping(
            symbols=(),
            connectors=(
                ConnectorMap(template=c1, pin_symbol=two_port_factory, position="top"),
            ),
        )


# --- rule 9: PowerNetMap.symbol() has exactly one port ---------------------


def test_rule9_pass_power_symbol_single_port():
    SymbolMapping(
        symbols=(),
        connectors=(),
        power_nets=(PowerNetMap(net_name="v24", symbol=one_port_factory),),
    )


def test_rule9_fail_power_symbol_multi_port():
    with pytest.raises(PortNotOnSymbolError):
        SymbolMapping(
            symbols=(),
            connectors=(),
            power_nets=(PowerNetMap(net_name="v24", symbol=two_port_factory),),
        )


def test_rule9_fail_power_symbol_zero_ports():
    zero_port_factory = factory_with_ports(())
    with pytest.raises(PortNotOnSymbolError):
        SymbolMapping(
            symbols=(),
            connectors=(),
            power_nets=(PowerNetMap(net_name="v24", symbol=zero_port_factory),),
        )
