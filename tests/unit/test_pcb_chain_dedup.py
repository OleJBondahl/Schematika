"""Tests for chain deduplication: a CHAIN net is walked at most once."""

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


class TestChainDedup:
    def test_single_chain_produces_one_column(self) -> None:
        """One CHAIN net between two connectors yields exactly one column."""
        c = Circuit()
        tmpl = _make_connector_template(1)
        fuse_tmpl = _make_fuse_template()

        j1 = tmpl(ref="J1", circuit=c)
        j2 = tmpl(ref="J2", circuit=c)
        f1 = fuse_tmpl(ref="F1", circuit=c)

        n1 = Net("n1", circuit=c)
        n1 += j1["1"], f1["1"]
        n2 = Net("n2", circuit=c)
        n2 += f1["2"], j2["1"]

        fuse_slice = SymbolSlice(symbol=fuse, pin_map={"1": "1", "2": "2"})
        fuse_map = SymbolMap(template=fuse_tmpl, slices=(fuse_slice,))
        cmap = ConnectorMap(template=tmpl, pin_symbol=connector_pin, position="top")

        mapping = SymbolMapping(symbols=(fuse_map,), connectors=(cmap,))
        result = build(c, mapping)

        # Only one column for this single-chain circuit
        assert len(result.columns) == 1

    def test_chain_net_not_walked_twice(self) -> None:
        """The chain net walked from J1 is not re-walked from J2."""
        c = Circuit()
        tmpl = _make_connector_template(1)
        fuse_tmpl = _make_fuse_template()

        j1 = tmpl(ref="J1", circuit=c)
        j2 = tmpl(ref="J2", circuit=c)
        f1 = fuse_tmpl(ref="F1", circuit=c)

        n1 = Net("n1", circuit=c)
        n1 += j1["1"], f1["1"]
        n2 = Net("n2", circuit=c)
        n2 += f1["2"], j2["1"]

        fuse_slice = SymbolSlice(symbol=fuse, pin_map={"1": "1", "2": "2"})
        fuse_map = SymbolMap(template=fuse_tmpl, slices=(fuse_slice,))
        cmap = ConnectorMap(template=tmpl, pin_symbol=connector_pin, position="top")
        mapping = SymbolMapping(symbols=(fuse_map,), connectors=(cmap,))

        result = build(c, mapping)
        # Both J1 and J2 are terminators, but the shared chain between them
        # is deduped — exactly one column results.
        assert len(result.columns) == 1

    def test_two_independent_chains_two_columns(self) -> None:
        """Two independent chains produce two columns (no dedup across different chains)."""
        c = Circuit()
        tmpl_a = _make_connector_template(1)
        tmpl_b = _make_connector_template(1)
        fuse_tmpl = _make_fuse_template()

        j1 = tmpl_a(ref="J1", circuit=c)
        j2 = tmpl_a(ref="J2", circuit=c)
        j3 = tmpl_b(ref="J3", circuit=c)
        j4 = tmpl_b(ref="J4", circuit=c)
        f1 = fuse_tmpl(ref="F1", circuit=c)
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
        cmap_a = ConnectorMap(template=tmpl_a, pin_symbol=connector_pin, position="top")
        cmap_b = ConnectorMap(template=tmpl_b, pin_symbol=connector_pin, position="top")

        mapping = SymbolMapping(symbols=(fuse_map,), connectors=(cmap_a, cmap_b))
        result = build(c, mapping)
        assert len(result.columns) == 2

    def test_column_keys_unique(self) -> None:
        """All column keys are unique."""
        c = Circuit()
        tmpl_a = _make_connector_template(1)
        tmpl_b = _make_connector_template(1)
        fuse_tmpl = _make_fuse_template()

        j1 = tmpl_a(ref="J1", circuit=c)
        j2 = tmpl_a(ref="J2", circuit=c)
        j3 = tmpl_b(ref="J3", circuit=c)
        j4 = tmpl_b(ref="J4", circuit=c)
        f1 = fuse_tmpl(ref="F1", circuit=c)
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
        cmap_a = ConnectorMap(template=tmpl_a, pin_symbol=connector_pin, position="top")
        cmap_b = ConnectorMap(template=tmpl_b, pin_symbol=connector_pin, position="top")

        mapping = SymbolMapping(symbols=(fuse_map,), connectors=(cmap_a, cmap_b))
        result = build(c, mapping)
        keys = [k for k, _ in result.columns]
        assert len(keys) == len(set(keys))
