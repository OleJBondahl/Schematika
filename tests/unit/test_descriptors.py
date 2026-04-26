"""Tests for inline circuit descriptors (Task 11A)."""

import pytest

from schematika.core.options import DescriptorBuildOptions
from schematika.electrical.descriptors import (
    CompDescriptor,
    RefDescriptor,
    TermDescriptor,
    build_from_descriptors,
    comp,
    ref,
    term,
)
from schematika.electrical.symbols.coils import coil
from schematika.electrical.symbols.contacts import no_contact
from schematika.electrical.utils.autonumbering import create_autonumberer


def test_ref_descriptor():
    """ref() should create a RefDescriptor."""
    d = ref("PLC:DO")
    assert isinstance(d, RefDescriptor)
    assert d.terminal_id == "PLC:DO"


def test_comp_descriptor():
    """comp() should create a CompDescriptor."""
    d = comp(coil, "K", pins=("A1", "A2"))
    assert isinstance(d, CompDescriptor)
    assert d.symbol_fn is coil
    assert d.tag_prefix == "K"
    assert d.pins == ("A1", "A2")


def test_comp_descriptor_no_pins():
    """comp() without pins should default to empty tuple."""
    d = comp(coil, "K")
    assert d.pins == ()


def test_term_descriptor():
    """term() should create a TermDescriptor."""
    d = term("X103")
    assert isinstance(d, TermDescriptor)
    assert d.terminal_id == "X103"
    assert d.poles == 1
    assert d.pins is None


def test_term_descriptor_with_poles():
    """term() should accept poles parameter."""
    d = term("X001", poles=3)
    assert d.poles == 3


def test_descriptors_are_frozen():
    """Descriptors should be immutable."""
    d = ref("PLC:DO")
    with pytest.raises(AttributeError):
        d.terminal_id = "PLC:AI"  # ty: ignore[invalid-assignment]

    d2 = comp(coil, "K")
    with pytest.raises(AttributeError):
        d2.tag_prefix = "Q"  # ty: ignore[invalid-assignment]

    d3 = term("X103")
    with pytest.raises(AttributeError):
        d3.terminal_id = "X104"  # ty: ignore[invalid-assignment]


def test_build_from_descriptors_simple():
    """Building from descriptors should produce a valid circuit."""
    state = create_autonumberer()

    result = build_from_descriptors(
        state,
        descriptors=[
            term("X102"),
            comp(coil, "K", pins=("A1", "A2")),
            term("X103"),
        ],
    )

    assert result.circuit is not None
    assert "K" in result.component_map
    assert result.component_map["K"] == ["K1"]


def test_build_from_descriptors_with_count():
    """count=3 should produce 3 merged instances."""
    state = create_autonumberer()

    result = build_from_descriptors(
        state,
        descriptors=[
            term("X102"),
            comp(coil, "K", pins=("A1", "A2")),
            term("X103"),
        ],
        options=DescriptorBuildOptions(count=3),
    )

    assert result.component_map["K"] == ["K1", "K2", "K3"]


def test_build_from_descriptors_with_ref():
    """RefDescriptor should create a reference symbol with fixed tag."""
    state = create_autonumberer()

    result = build_from_descriptors(
        state,
        descriptors=[
            ref("PLC:DO"),
            comp(coil, "K", pins=("A1", "A2")),
            term("X103"),
        ],
        options=DescriptorBuildOptions(count=2),
    )

    # K tags should be K1, K2
    assert result.component_map["K"] == ["K1", "K2"]
    # PLC:DO should appear as a fixed tag for all instances
    assert result.component_map["PLC:DO"] == ["PLC:DO", "PLC:DO"]


def test_build_from_descriptors_with_reuse_tags():
    """reuse_tags should work with build_from_descriptors."""
    state = create_autonumberer()

    # First: build coils
    coil_result = build_from_descriptors(
        state,
        descriptors=[
            term("X102"),
            comp(coil, "K", pins=("A1", "A2")),
            term("X103"),
        ],
        options=DescriptorBuildOptions(count=3),
    )

    assert coil_result.component_map["K"] == ["K1", "K2", "K3"]

    # Second: build contacts reusing K tags
    contact_result = build_from_descriptors(
        coil_result.state,
        descriptors=[
            term("X102"),
            comp(no_contact, "K", pins=("13", "14")),
            term("X103"),
        ],
        options=DescriptorBuildOptions(count=3, reuse_tags={"K": coil_result}),
    )

    assert contact_result.component_map["K"] == ["K1", "K2", "K3"]


def test_build_from_descriptors_with_wire_labels():
    """wire_labels should be applied to the built circuit."""
    state = create_autonumberer()

    result = build_from_descriptors(
        state,
        descriptors=[
            term("X102"),
            comp(coil, "K", pins=("A1", "A2")),
            term("X103"),
        ],
        options=DescriptorBuildOptions(wire_labels=("RD 2.5mm2", "BK 2.5mm2")),
    )

    # The circuit should have been built successfully with wire labels
    assert result.circuit is not None
