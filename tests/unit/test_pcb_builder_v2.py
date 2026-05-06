"""Top-level build() integration tests."""

from types import SimpleNamespace

from schematika.core.geometry import Point, Vector
from schematika.core.symbol import Port, Symbol
from schematika.pcb import build
from schematika.pcb.layout_spec import LayoutSpec
from schematika.pcb.model import (
    Column,
    ConnectorBlock,
    ConnectorMap,
    FloatingPart,
    PCBBuildResult,
    PinColumns,
    SymbolMap,
    SymbolMapping,
    SymbolSlice,
    Terminator,
)
from schematika.pcb.walk import pack_pages


def _two_port_symbol(label: str = "") -> Symbol:
    return Symbol(
        elements=[],
        ports={
            "top": Port("1", Point(0, 0), Vector(0, 1)),
            "bottom": Port("2", Point(0, -1), Vector(0, -1)),
        },
        label=label or "component",
    )


# ---------------------------------------------------------------------------
# Shared template stubs
# ---------------------------------------------------------------------------

_conn_template = type(
    "conn_2p",
    (),
    {"name": "conn_2p", "pins": [SimpleNamespace(num="1"), SimpleNamespace(num="2")]},
)()
_fuse_template = type(
    "fuse",
    (),
    {"name": "fuse", "pins": [SimpleNamespace(num="1"), SimpleNamespace(num="2")]},
)()


def _make_circuit(parts, nets=(), nc_pins=()):
    """Make a duck-typed circuit object matching adapter.adapt() expectations."""
    part_objects = []
    for ref, template, description in parts:
        part_objects.append(
            SimpleNamespace(
                ref=ref,
                name=template_name_str(template),
                description=description,
                pins=[SimpleNamespace(num=str(i + 1)) for i in range(2)],
                template=template,
            )
        )
    net_objects = []
    for net_name, pin_list in nets:
        pin_refs = []
        for part_ref, pin_num in pin_list:
            part_obj = next(p for p in part_objects if p.ref == part_ref)
            pin_refs.append(SimpleNamespace(part=part_obj, num=str(pin_num)))
        net_objects.append(SimpleNamespace(name=net_name, pins=pin_refs))
    nc = SimpleNamespace(pins=[])
    return SimpleNamespace(parts=part_objects, nets=net_objects, NC=nc)


def template_name_str(template):
    return str(getattr(template, "name", repr(template)))


def _simple_mapping(conn_template=_conn_template):
    return SymbolMapping(
        symbols=(),
        connectors=(ConnectorMap(template=conn_template),),
        power_nets=(),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_build_returns_pcbbuildresult() -> None:
    """build() returns a PCBBuildResult with sensible top-level fields."""
    circuit = _make_circuit(
        parts=[("J1", _conn_template, None)],
    )
    mapping = _simple_mapping()
    result = build(circuit, mapping, strict_net_names=False)
    assert isinstance(result, PCBBuildResult)
    assert len(result.connector_blocks) == 1
    assert result.connector_blocks[0].connector_ref == "J1"


def test_build_returns_connector_blocks_in_declaration_order() -> None:
    """Two connectors yield two ConnectorBlocks in declaration order."""
    circuit = _make_circuit(
        parts=[("J2", _conn_template, None), ("J1", _conn_template, None)],
    )
    mapping = _simple_mapping()
    result = build(circuit, mapping, strict_net_names=False)
    refs = [b.connector_ref for b in result.connector_blocks]
    assert refs == ["J2", "J1"]


def test_build_floats_unreachable_part() -> None:
    """A non-connector part that isn't reached by any walk ends in floating_parts."""
    circuit = _make_circuit(
        parts=[
            ("J1", _conn_template, None),
            ("F1", _fuse_template, None),
        ],
    )
    mapping = SymbolMapping(
        symbols=(
            SymbolMap(
                template=_fuse_template,
                slices=(
                    SymbolSlice(
                        symbol=_two_port_symbol, pin_map={"1": "top", "2": "bottom"}
                    ),
                ),
            ),
        ),
        connectors=(ConnectorMap(template=_conn_template),),
        power_nets=(),
    )
    # F1 not on any net → floats
    result = build(circuit, mapping, strict_net_names=False)
    floating_refs = [fp.part_ref for fp in result.floating_parts]
    assert "F1" in floating_refs


def test_build_uses_part_description_as_functional_label() -> None:
    """ConnectorBlock.functional_label comes from part.description."""
    circuit = _make_circuit(
        parts=[("J1", _conn_template, "PSU + Em.Stop")],
    )
    mapping = _simple_mapping()
    result = build(circuit, mapping, strict_net_names=False)
    assert result.connector_blocks[0].functional_label == "PSU + Em.Stop"


def test_pack_pages_single_page_when_blocks_fit() -> None:
    """Two narrow blocks fit on one page."""
    narrow_pc = PinColumns(
        pin_id="1", columns=(Column(slices=(), terminator=Terminator.NC),)
    )
    b1 = ConnectorBlock(
        connector_ref="J1", functional_label=None, pin_columns=(narrow_pc,)
    )
    b2 = ConnectorBlock(
        connector_ref="J2", functional_label=None, pin_columns=(narrow_pc,)
    )
    _, pages = pack_pages((b1, b2), (), page_size=(250.0, 297.0), layout=LayoutSpec())
    assert len(pages) == 1
    refs = [r for r, _, _ in pages[0].placements]
    assert "J1" in refs
    assert "J2" in refs


def test_pack_pages_overflow_creates_new_page() -> None:
    """A block too wide for the remaining row starts a new page."""

    def _wide_block(ref: str, n_pins: int) -> ConnectorBlock:
        pin_columns = tuple(
            PinColumns(
                pin_id=str(i),
                columns=(Column(slices=(), terminator=Terminator.NC),),
            )
            for i in range(n_pins)
        )
        return ConnectorBlock(
            connector_ref=ref, functional_label=None, pin_columns=pin_columns
        )

    # Each 4-pin block is side_padding*2 + 4*pin_spacing = 5*2 + 4*10 = 50 mm.
    # available_width = 100 - 2*15 = 70mm; 50 + 20 + 50 = 120 > 70 → row1 full.
    # NC blocks have 10mm chain depth << row1_chain_budget; row 2 opens on same page.
    b1 = _wide_block("J1", 4)
    b2 = _wide_block("J2", 4)
    _, pages = pack_pages((b1, b2), (), page_size=(100.0, 297.0), layout=LayoutSpec())
    assert len(pages) == 1
    assert tuple(r for r, _, _ in pages[0].placements) == ("J1", "J2")


def test_pack_pages_floating_parts_get_their_own_page() -> None:
    """Floating parts always go on a final 'Floating' page."""
    fp = FloatingPart(part_ref="F1")
    _, pages = pack_pages((), (fp,), page_size=(250.0, 297.0), layout=LayoutSpec())
    assert len(pages) == 1
    assert pages[0].floating_part_refs == ("F1",)
    assert pages[0].floating_part_refs == ("F1",)
