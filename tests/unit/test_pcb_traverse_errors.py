"""Tests for build-time errors: UnmappedPartError, OrphanSliceError, HeightOverflowError."""

import pytest
import skidl
from skidl import Circuit, Net, Part, Pin

from schematika.electrical.symbols import connector_pin, fuse
from schematika.pcb.builder import build
from schematika.pcb.errors import (
    HeightOverflowError,
    OrphanSliceError,
    UnmappedPartError,
)
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


class TestUnmappedPartError:
    def test_unmapped_part_raises(self) -> None:
        c = Circuit()
        conn_tmpl = _make_connector_template(1)
        fuse_tmpl = _make_fuse_template()

        j1 = conn_tmpl(ref="J1", circuit=c)
        f1 = fuse_tmpl(ref="F1", circuit=c)

        net = Net("n1", circuit=c)
        net += j1["1"], f1["1"]

        # No SymbolMap for the fuse
        cmap = ConnectorMap(
            template=conn_tmpl, pin_symbol=connector_pin, position="top"
        )
        mapping = SymbolMapping(symbols=(), connectors=(cmap,))

        with pytest.raises(UnmappedPartError) as exc_info:
            build(c, mapping)
        assert "F1" in str(exc_info.value) or "Fuse" in str(exc_info.value)

    def test_unmapped_part_error_has_ref(self) -> None:
        c = Circuit()
        conn_tmpl = _make_connector_template(1)
        fuse_tmpl = _make_fuse_template()

        j1 = conn_tmpl(ref="J1", circuit=c)
        f1 = fuse_tmpl(ref="F1", circuit=c)

        net = Net("n1", circuit=c)
        net += j1["1"], f1["1"]

        cmap = ConnectorMap(
            template=conn_tmpl, pin_symbol=connector_pin, position="top"
        )
        mapping = SymbolMapping(symbols=(), connectors=(cmap,))

        with pytest.raises(UnmappedPartError) as exc_info:
            build(c, mapping)
        err = exc_info.value
        assert hasattr(err, "part_ref") or "F1" in str(err) or "Fuse" in str(err)


class TestOrphanSliceError:
    def test_orphan_slice_raises(self) -> None:
        """A fuse that is not reachable from any terminator raises OrphanSliceError."""
        c = Circuit()
        conn_tmpl = _make_connector_template(1)
        fuse_tmpl = _make_fuse_template()

        j1 = conn_tmpl(ref="J1", circuit=c)
        # F1 exists but is not connected to any net
        fuse_tmpl(ref="F1", circuit=c)

        # J1 is not connected to f1 at all
        net_solo = Net("solo", circuit=c)
        net_solo += j1["1"]

        fuse_slice = SymbolSlice(symbol=fuse, pin_map={"1": "1", "2": "2"})
        fuse_map = SymbolMap(template=fuse_tmpl, slices=(fuse_slice,))
        cmap = ConnectorMap(
            template=conn_tmpl, pin_symbol=connector_pin, position="top"
        )
        mapping = SymbolMapping(symbols=(fuse_map,), connectors=(cmap,))

        with pytest.raises(OrphanSliceError) as exc_info:
            build(c, mapping)
        assert "F1" in str(exc_info.value)

    def test_orphan_slice_error_has_part_ref(self) -> None:
        c = Circuit()
        conn_tmpl = _make_connector_template(1)
        fuse_tmpl = _make_fuse_template()

        j1 = conn_tmpl(ref="J1", circuit=c)
        fuse_tmpl(ref="F1", circuit=c)

        net_solo = Net("solo", circuit=c)
        net_solo += j1["1"]

        fuse_slice = SymbolSlice(symbol=fuse, pin_map={"1": "1", "2": "2"})
        fuse_map = SymbolMap(template=fuse_tmpl, slices=(fuse_slice,))
        cmap = ConnectorMap(
            template=conn_tmpl, pin_symbol=connector_pin, position="top"
        )
        mapping = SymbolMapping(symbols=(fuse_map,), connectors=(cmap,))

        with pytest.raises(OrphanSliceError) as exc_info:
            build(c, mapping)
        err = exc_info.value
        assert hasattr(err, "part_ref")
        assert err.part_ref == "F1"


class TestHeightOverflowError:
    def test_height_overflow_with_tiny_page(self) -> None:
        """A column taller than the page raises HeightOverflowError."""
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
        cmap = ConnectorMap(
            template=conn_tmpl, pin_symbol=connector_pin, position="top"
        )
        mapping = SymbolMapping(symbols=(fuse_map,), connectors=(cmap,))

        # Page height of 1 mm — way smaller than any column
        tiny_page = (297.0, 1.0)

        with pytest.raises(HeightOverflowError) as exc_info:
            build(c, mapping, page_size=tiny_page)
        err = exc_info.value
        assert err.max_height_mm == 1.0
        assert err.height_mm > 1.0

    def test_height_overflow_error_has_column_key(self) -> None:
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
        cmap = ConnectorMap(
            template=conn_tmpl, pin_symbol=connector_pin, position="top"
        )
        mapping = SymbolMapping(symbols=(fuse_map,), connectors=(cmap,))

        tiny_page = (297.0, 1.0)
        with pytest.raises(HeightOverflowError) as exc_info:
            build(c, mapping, page_size=tiny_page)
        err = exc_info.value
        assert hasattr(err, "column_key")
        assert "pcb_col_" in err.column_key
