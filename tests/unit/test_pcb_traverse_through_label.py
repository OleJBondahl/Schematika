"""Traverse test: LABEL net splits a chain into multiple columns."""

import skidl
from skidl import Circuit, Net, Part, Pin

from schematika.electrical.symbols import connector_pin, fuse
from schematika.pcb.adapter import adapt
from schematika.pcb.builder import _classify_nets, _NetKind, build
from schematika.pcb.model import ConnectorMap, SymbolMap, SymbolMapping, SymbolSlice


def _make_connector_template(n_pins: int = 1) -> Part:
    return Part(
        name="Connector",
        ref_prefix="J",
        pins=[Pin(num=str(i), name="") for i in range(1, n_pins + 1)],
        dest=skidl.TEMPLATE,
        tool=skidl.SKIDL,  # type: ignore[attr-defined]
    )


def _make_fuse_template() -> Part:
    return Part(
        name="Fuse",
        ref_prefix="F",
        pins=[Pin(num="1", name=""), Pin(num="2", name="")],
        dest=skidl.TEMPLATE,
        tool=skidl.SKIDL,  # type: ignore[attr-defined]
    )


class TestThroughLabel:
    def _build(self):
        """
        Circuit:
          J1 --net_a(CHAIN)--> F1 --em_stop(LABEL, 3 pins)--> F2 --net_b(CHAIN)--> J2
                                      |
                                   em_stop also connects F3["1"]
                                   F3["2"] --net_c(CHAIN)--> J3

        em_stop LABEL net: F1["2"], F2["1"], F3["1"] (3 pins).
        Three columns result:
          Column A: J1 -> F1 -> [em_stop label]
          Column B: [em_stop label] -> F2 -> J2
          Column C: [em_stop label] -> F3 -> J3
        """
        c = Circuit()
        conn_tmpl = _make_connector_template(1)
        fuse_tmpl = _make_fuse_template()

        j1 = conn_tmpl(ref="J1", circuit=c)
        j2 = conn_tmpl(ref="J2", circuit=c)
        j3 = conn_tmpl(ref="J3", circuit=c)
        f1 = fuse_tmpl(ref="F1", circuit=c)
        f2 = fuse_tmpl(ref="F2", circuit=c)
        f3 = fuse_tmpl(ref="F3", circuit=c)

        # J1 -> F1 via CHAIN
        net_a = Net("net_a", circuit=c)
        net_a += j1["1"], f1["1"]

        # em_stop LABEL net: F1.2, F2.1, F3.1 (3 pins)
        em_stop = Net("em_stop", circuit=c)
        em_stop += f1["2"], f2["1"], f3["1"]

        # F2 -> J2 via CHAIN
        net_b = Net("net_b", circuit=c)
        net_b += f2["2"], j2["1"]

        # F3 -> J3 via CHAIN (so F3 is reachable and placeable)
        net_c = Net("net_c", circuit=c)
        net_c += f3["2"], j3["1"]

        fuse_slice = SymbolSlice(symbol=fuse, pin_map={"1": "1", "2": "2"})
        fuse_map = SymbolMap(template=fuse_tmpl, slices=(fuse_slice,))
        cmap = ConnectorMap(
            template=conn_tmpl, pin_symbol=connector_pin, position="top"
        )

        mapping = SymbolMapping(
            symbols=(fuse_map,),
            connectors=(cmap,),
        )
        return c, mapping

    def test_label_net_classified_correctly(self) -> None:
        c, mapping = self._build()
        ir = adapt(c)
        kinds = _classify_nets(ir, mapping)
        assert kinds.get("em_stop") == _NetKind.LABEL
        assert kinds.get("net_a") == _NetKind.CHAIN
        assert kinds.get("net_b") == _NetKind.CHAIN

    def test_multiple_columns_produced(self) -> None:
        c, mapping = self._build()
        result = build(c, mapping)
        # Label net creates multiple columns
        assert len(result.columns) >= 2

    def test_every_column_has_a_label_placeholder(self) -> None:
        """After crit #4, each column bounded by the LABEL net contains a label symbol.

        The label-symbol carries the LABEL net's name ("em_stop") as its label.
        """
        from schematika.core.symbol import Symbol

        c, mapping = self._build()
        result = build(c, mapping)
        for _, circ in result.columns:
            labels = [e.label for e in circ.elements if isinstance(e, Symbol)]
            assert "em_stop" in labels, (
                f"column missing label placeholder; labels={labels}"
            )

    def test_columns_have_keys(self) -> None:
        c, mapping = self._build()
        result = build(c, mapping)
        for key, _ in result.columns:
            assert key.startswith("pcb_col_")

    def test_all_columns_assigned_to_pages(self) -> None:
        c, mapping = self._build()
        result = build(c, mapping)
        paged_keys = set()
        for _, keys in result.pages:
            paged_keys.update(keys)
        col_keys = {k for k, _ in result.columns}
        assert col_keys == paged_keys
