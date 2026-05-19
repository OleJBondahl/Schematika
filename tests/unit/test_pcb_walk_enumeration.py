"""Tests for connector enumeration in declaration order."""

from types import SimpleNamespace

from schematika.pcb.model import ConnectorMap, SymbolMapping
from schematika.pcb.walk import enumerate_connectors


def _ir_with_parts(*refs_and_templates):
    parts = tuple(
        SimpleNamespace(
            ref=ref, template_name=tpl, description=None, pin_numbers=("1", "2")
        )
        for ref, tpl in refs_and_templates
    )
    return SimpleNamespace(parts=parts, nets=(), nc_pins=())


def test_enumerates_connectors_in_declaration_order() -> None:
    template_a = type("conn_2p", (), {"name": "conn_2p"})
    mapping = SymbolMapping(
        symbols=(),
        connectors=(ConnectorMap(template=template_a),),
        power_nets=(),
    )
    ir = _ir_with_parts(("J3", "conn_2p"), ("J1", "conn_2p"), ("J2", "conn_2p"))
    refs = [c.ref for c in enumerate_connectors(ir, mapping)]
    assert refs == ["J3", "J1", "J2"]


def test_skips_non_connector_parts() -> None:
    conn_template = type("conn_2p", (), {"name": "conn_2p"})
    mapping = SymbolMapping(
        symbols=(),
        connectors=(ConnectorMap(template=conn_template),),
        power_nets=(),
    )
    ir = _ir_with_parts(("F1", "fuse"), ("J1", "conn_2p"), ("K1", "relay_spst"))
    refs = [c.ref for c in enumerate_connectors(ir, mapping)]
    assert refs == ["J1"]
