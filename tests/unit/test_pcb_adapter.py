"""Unit tests for schematika.pcb.adapter module."""

import pytest
import skidl
from skidl import Circuit, Net, Part, Pin

from schematika.pcb.adapter import NetRef, PartRef, PinRef, adapt


def _fresh_circuit() -> Circuit:
    """Create a fresh skidl Circuit; avoid global default_circuit across tests."""
    return Circuit()


def _make_fuse_template() -> Part:
    """Factory for a simple 2-pin Fuse template."""
    return Part(
        name="Fuse",
        ref_prefix="F",
        pins=[Pin(num="1", name=""), Pin(num="2", name="")],
        dest=skidl.TEMPLATE,
        tool=skidl.SKIDL,  # ty: ignore[unresolved-attribute]
    )


class TestBasicAdaptation:
    """Test basic multi-part, multi-net adaptation."""

    def test_two_fuses_two_nets(self) -> None:
        """Adapt a circuit with 2 fuses and 2 nets."""
        c = _fresh_circuit()
        fuse_template = _make_fuse_template()

        F1 = fuse_template(ref="F1", circuit=c)
        F2 = fuse_template(ref="F2", circuit=c)

        net_a = Net("net_A", circuit=c)
        net_a += F1["1"], F2["1"]

        net_b = Net("net_B", circuit=c)
        net_b += F1["2"], F2["2"]

        ir = adapt(c)

        assert len(ir.parts) == 2
        assert ir.parts[0].ref == "F1"
        assert ir.parts[0].template_name == "Fuse"
        assert ir.parts[1].ref == "F2"

        assert len(ir.nets) == 2
        assert ir.nets[0].name == "net_A"
        assert len(ir.nets[0].pins) == 2
        assert ir.nets[1].name == "net_B"
        assert len(ir.nets[1].pins) == 2

    def test_part_order_preserved(self) -> None:
        """Verify that part order from circuit.parts is preserved."""
        c = _fresh_circuit()
        fuse_template = _make_fuse_template()

        _F1 = fuse_template(ref="F1", circuit=c)
        _F3 = fuse_template(ref="F3", circuit=c)
        _F2 = fuse_template(ref="F2", circuit=c)

        ir = adapt(c)

        assert len(ir.parts) == 3
        assert [p.ref for p in ir.parts] == ["F1", "F3", "F2"]

    def test_pin_numbers_stringified(self) -> None:
        """Verify that pin numbers are coerced to strings."""
        c = _fresh_circuit()
        fuse_template = _make_fuse_template()
        _F1 = fuse_template(ref="F1", circuit=c)

        ir = adapt(c)

        assert ir.parts[0].pin_numbers == ("1", "2")
        assert all(isinstance(pn, str) for pn in ir.parts[0].pin_numbers)


class TestNCNetExclusion:
    """Test that NC (no-connect) net is excluded from CircuitIR.nets."""

    def test_nc_net_excluded(self) -> None:
        """Verify that the NC net is not included in adapted nets."""
        c = _fresh_circuit()
        fuse_template = _make_fuse_template()
        F1 = fuse_template(ref="F1", circuit=c)

        # NC is automatically created and populated; don't add to it explicitly
        # Just verify it doesn't appear in the adapted nets
        user_net = Net("my_net", circuit=c)
        user_net += F1["1"]

        ir = adapt(c)

        # Only user_net should be in the IR
        assert len(ir.nets) == 1
        assert ir.nets[0].name == "my_net"

        # Verify NC exists in circuit.nets but not in IR
        assert any(net is c.NC for net in c.nets)


class TestSinglePinNets:
    """Test that 1-pin nets are included (adapter doesn't filter them)."""

    def test_one_pin_net_included(self) -> None:
        """Adapter includes nets with only 1 pin."""
        c = _fresh_circuit()
        fuse_template = _make_fuse_template()
        F1 = fuse_template(ref="F1", circuit=c)

        net_solo = Net("solo_net", circuit=c)
        net_solo += F1["1"]

        ir = adapt(c)

        # One user net (plus NC in circuit, but excluded from IR)
        assert len(ir.nets) == 1
        assert ir.nets[0].name == "solo_net"
        assert len(ir.nets[0].pins) == 1
        assert ir.nets[0].pins[0].part_ref == "F1"
        assert ir.nets[0].pins[0].pin_name == "1"


class TestSelfLoopNets:
    """Test that nets with both pins on the same part (self-loops) are included."""

    def test_self_loop_net_included(self) -> None:
        """Net with both pins on the same part is included."""
        c = _fresh_circuit()
        # Create a 3-pin part to allow a self-loop
        three_pin_template = Part(
            name="ThreePinPart",
            ref_prefix="T",
            pins=[Pin(num="1", name=""), Pin(num="2", name=""), Pin(num="3", name="")],
            dest=skidl.TEMPLATE,
            tool=skidl.SKIDL,  # ty: ignore[unresolved-attribute]
        )
        T1 = three_pin_template(ref="T1", circuit=c)

        net_internal = Net("internal", circuit=c)
        net_internal += T1["1"], T1["2"]

        net_external = Net("external", circuit=c)
        net_external += T1["3"]

        ir = adapt(c)

        # Two user nets
        assert len(ir.nets) == 2

        # Find the internal net
        internal = next(n for n in ir.nets if n.name == "internal")
        assert len(internal.pins) == 2
        # Both pins on same part
        assert internal.pins[0].part_ref == "T1"
        assert internal.pins[1].part_ref == "T1"


class TestPinRefIntegrity:
    """Test that PinRef correctly captures part reference and pin name."""

    def test_pin_refs_correct_structure(self) -> None:
        """Verify PinRef captures correct part.ref and pin.num."""
        c = _fresh_circuit()
        fuse_template = _make_fuse_template()
        F1 = fuse_template(ref="F1", circuit=c)
        F2 = fuse_template(ref="F2", circuit=c)

        net = Net("test", circuit=c)
        net += F1["1"], F2["2"]

        ir = adapt(c)

        net_ref = ir.nets[0]
        assert len(net_ref.pins) == 2

        # Verify pins reference correct parts and pin numbers
        pin_refs = {(p.part_ref, p.pin_name) for p in net_ref.pins}
        assert ("F1", "1") in pin_refs
        assert ("F2", "2") in pin_refs


class TestMultiNetIntegration:
    """Test a more complex circuit with multiple parts and nets."""

    def test_three_part_star_topology(self) -> None:
        """Circuit with 3 parts and star topology (all connected to a central net)."""
        c = _fresh_circuit()
        fuse_template = _make_fuse_template()
        F1 = fuse_template(ref="F1", circuit=c)
        F2 = fuse_template(ref="F2", circuit=c)
        F3 = fuse_template(ref="F3", circuit=c)

        # Central net connects one pin from each part
        net_star = Net("star_net", circuit=c)
        net_star += F1["1"], F2["1"], F3["1"]

        # Individual nets for other pins
        net_a = Net("net_A", circuit=c)
        net_a += F1["2"]

        net_b = Net("net_B", circuit=c)
        net_b += F2["2"]

        net_c = Net("net_C", circuit=c)
        net_c += F3["2"]

        ir = adapt(c)

        assert len(ir.parts) == 3
        assert len(ir.nets) == 4  # NC excluded

        # Verify star net has 3 pins
        star = next(n for n in ir.nets if n.name == "star_net")
        assert len(star.pins) == 3
        assert {p.part_ref for p in star.pins} == {"F1", "F2", "F3"}


class TestDataclassProperties:
    """Test that IR dataclasses are frozen and have expected properties."""

    def test_circuit_ir_frozen(self) -> None:
        """CircuitIR instances are frozen (immutable)."""
        c = _fresh_circuit()
        fuse_template = _make_fuse_template()
        _F1 = fuse_template(ref="F1", circuit=c)

        ir = adapt(c)

        with pytest.raises(AttributeError):
            ir.parts = ()  # ty: ignore[invalid-assignment]

    def test_part_ref_frozen(self) -> None:
        """PartRef instances are frozen."""
        part_ref = PartRef(ref="F1", template_name="Fuse", pin_numbers=("1", "2"))

        with pytest.raises(AttributeError):
            part_ref.ref = "F2"  # ty: ignore[invalid-assignment]

    def test_pin_ref_frozen(self) -> None:
        """PinRef instances are frozen."""
        pin_ref = PinRef(part_ref="F1", pin_name="1")

        with pytest.raises(AttributeError):
            pin_ref.part_ref = "F2"  # ty: ignore[invalid-assignment]

    def test_net_ref_frozen(self) -> None:
        """NetRef instances are frozen."""
        net_ref = NetRef(name="test", pins=())

        with pytest.raises(AttributeError):
            net_ref.name = "other"  # ty: ignore[invalid-assignment]
