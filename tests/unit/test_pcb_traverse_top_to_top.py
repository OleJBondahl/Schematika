"""Traverse test: J1.pin1 -> fuse -> J2.pin1, one column of 3 placed symbols."""

import pytest
import skidl  # ty: ignore[unresolved-import]
from skidl import Circuit, Net, Part, Pin  # ty: ignore[unresolved-import]

from schematika.electrical.symbols import connector_pin, fuse
from schematika.pcb.builder import build
from schematika.pcb.model import ConnectorMap, SymbolMap, SymbolMapping, SymbolSlice


def _make_connector_template(n_pins: int = 1) -> Part:
    return Part(
        name="Connector",
        ref_prefix="J",
        pins=[Pin(num=str(i), name="") for i in range(1, n_pins + 1)],
        dest=skidl.TEMPLATE,
        tool=skidl.SKIDL,
    )


def _make_fuse_template() -> Part:
    return Part(
        name="Fuse",
        ref_prefix="F",
        pins=[Pin(num="1", name=""), Pin(num="2", name="")],
        dest=skidl.TEMPLATE,
        tool=skidl.SKIDL,
    )


class TestTopToTop:
    def _build_circuit_and_mapping(self):
        c = Circuit()
        conn_tmpl = _make_connector_template(1)
        fuse_tmpl = _make_fuse_template()

        j1 = conn_tmpl(ref="J1", circuit=c)
        j2 = conn_tmpl(ref="J2", circuit=c)
        f1 = fuse_tmpl(ref="F1", circuit=c)

        net_in = Net("net_in", circuit=c)
        net_in += j1["1"], f1["1"]

        net_out = Net("net_out", circuit=c)
        net_out += f1["2"], j2["1"]

        fuse_slice = SymbolSlice(symbol=fuse, pin_map={"1": "1", "2": "2"})
        fuse_map = SymbolMap(template=fuse_tmpl, slices=(fuse_slice,))

        conn_map1 = ConnectorMap(
            template=conn_tmpl, pin_symbol=connector_pin, position="top"
        )

        mapping = SymbolMapping(
            symbols=(fuse_map,),
            connectors=(conn_map1,),
        )
        return c, mapping

    def test_produces_one_column(self) -> None:
        from schematika.core.symbol import Symbol

        c, mapping = self._build_circuit_and_mapping()
        result = build(c, mapping)
        assert len(result.columns) == 1
        # Exact symbol sequence: J1 (connector-pin), F1 (fuse), J2 (connector-pin)
        _, circ = result.columns[0]
        labels = [e.label for e in circ.elements if isinstance(e, Symbol)]
        assert labels == ["J1", "F1", "J2"]

    def test_column_has_inter_symbol_wires(self) -> None:
        """Symbols are wired via add_symbol(pins=) — wires populated beyond symbols."""
        from schematika.core.symbol import Symbol

        c, mapping = self._build_circuit_and_mapping()
        result = build(c, mapping)
        _, circ = result.columns[0]
        # 3 symbols + at least 2 connecting wire elements between them
        sym_count = sum(1 for e in circ.elements if isinstance(e, Symbol))
        assert len(circ.elements) > sym_count

    def test_column_key_format(self) -> None:
        c, mapping = self._build_circuit_and_mapping()
        result = build(c, mapping)
        key = result.columns[0][0]
        assert key.startswith("pcb_col_")

    def test_one_page_produced(self) -> None:
        c, mapping = self._build_circuit_and_mapping()
        result = build(c, mapping)
        assert len(result.pages) == 1
        assert result.pages[0][0] == "Page 1"

    def test_page_contains_the_column(self) -> None:
        c, mapping = self._build_circuit_and_mapping()
        result = build(c, mapping)
        page_keys = result.pages[0][1]
        col_key = result.columns[0][0]
        assert col_key in page_keys

    def test_result_is_frozen(self) -> None:
        c, mapping = self._build_circuit_and_mapping()
        result = build(c, mapping)
        with pytest.raises(AttributeError):
            result.columns = ()  # ty: ignore[invalid-assignment]

    def test_two_connectors_two_fuses_two_columns(self) -> None:
        """Two independent chains each produce their own column."""
        c = Circuit()
        conn_tmpl = _make_connector_template(1)
        fuse_tmpl = _make_fuse_template()

        conn_tmpl2 = _make_connector_template(1)

        j1 = conn_tmpl(ref="J1", circuit=c)
        j2 = conn_tmpl(ref="J2", circuit=c)
        f1 = fuse_tmpl(ref="F1", circuit=c)
        j3 = conn_tmpl2(ref="J3", circuit=c)
        j4 = conn_tmpl2(ref="J4", circuit=c)
        f2 = fuse_tmpl(ref="F2", circuit=c)

        n1 = Net("n1", circuit=c)
        n1 += j1["1"], f1["1"]
        n2 = Net("n2", circuit=c)
        n2 += f1["2"], j2["1"]
        n3 = Net("n3", circuit=c)
        n3 += j3["1"], f2["1"]
        n4 = Net("n4", circuit=c)
        n4 += f2["2"], j4["1"]

        fuse_slice = SymbolSlice(symbol=fuse, pin_map={"1": "1", "2": "2"})
        fuse_map = SymbolMap(template=fuse_tmpl, slices=(fuse_slice,))
        cmap1 = ConnectorMap(
            template=conn_tmpl, pin_symbol=connector_pin, position="top"
        )
        cmap2 = ConnectorMap(
            template=conn_tmpl2, pin_symbol=connector_pin, position="top"
        )

        mapping = SymbolMapping(
            symbols=(fuse_map,),
            connectors=(cmap1, cmap2),
        )
        result = build(c, mapping)
        assert len(result.columns) == 2
