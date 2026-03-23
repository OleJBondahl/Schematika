"""Tests for reuse_tags on CircuitBuilder.build()."""

import pytest

from schematika.electrical.builder import CircuitBuilder
from schematika.electrical.exceptions import TagReuseError
from schematika.electrical.symbols.coils import coil_symbol
from schematika.electrical.symbols.contacts import normally_open_symbol
from schematika.electrical.utils.autonumbering import create_autonumberer


def test_reuse_tags_yields_tags_from_source():
    """Build coils, then build contacts with reuse_tags, verify same K tags."""
    state = create_autonumberer()

    # Build coils (allocates K tags: K1, K2, K3)
    coil_builder = CircuitBuilder(state)
    coil_builder.set_layout(x=0, y=0, spacing=80)
    coil_builder.add_symbol(coil_symbol, "K", pins=("A1", "A2"))
    coil_result = coil_builder.build(count=3)

    assert coil_result.component_map["K"] == ["K1", "K2", "K3"]

    # Build contacts reusing K tags
    contact_builder = CircuitBuilder(coil_result.state)
    contact_builder.set_layout(x=0, y=0, spacing=80)
    contact_builder.add_symbol(normally_open_symbol, "K", pins=("13", "14"))
    contact_result = contact_builder.build(count=3, reuse_tags={"K": coil_result})

    assert contact_result.component_map["K"] == ["K1", "K2", "K3"]


def test_reuse_tags_exhaustion_raises():
    """Building more instances than source tags should raise TagReuseError."""
    state = create_autonumberer()

    coil_builder = CircuitBuilder(state)
    coil_builder.set_layout(x=0, y=0, spacing=80)
    coil_builder.add_symbol(coil_symbol, "K", pins=("A1", "A2"))
    coil_result = coil_builder.build(count=2)

    contact_builder = CircuitBuilder(coil_result.state)
    contact_builder.set_layout(x=0, y=0, spacing=80)
    contact_builder.add_symbol(normally_open_symbol, "K", pins=("13", "14"))

    with pytest.raises(TagReuseError):
        contact_builder.build(count=3, reuse_tags={"K": coil_result})


def test_build_result_reuse_tags_method():
    """BuildResult.reuse_tags() should return a callable generator."""
    state = create_autonumberer()

    builder = CircuitBuilder(state)
    builder.set_layout(x=0, y=0, spacing=80)
    builder.add_symbol(coil_symbol, "K", pins=("A1", "A2"))
    result = builder.build(count=2)

    gen = result.reuse_tags("K")
    assert callable(gen)

    s, tag1 = gen(state)
    s, tag2 = gen(s)
    assert tag1 == "K1"
    assert tag2 == "K2"


def test_reuse_tags_with_tag_generators_coexist():
    """reuse_tags and explicit tag_generators should coexist."""
    state = create_autonumberer()

    builder = CircuitBuilder(state)
    builder.set_layout(x=0, y=0, spacing=80)
    builder.add_symbol(coil_symbol, "K", pins=("A1", "A2"))
    coil_result = builder.build(count=2)

    builder2 = CircuitBuilder(coil_result.state)
    builder2.set_layout(x=0, y=0, spacing=80)
    builder2.add_symbol(normally_open_symbol, "K", pins=("13", "14"))
    builder2.add_symbol(normally_open_symbol, "S", pins=("3", "4"))

    def fixed_s(s):
        return s, "S_FIXED"

    result = builder2.build(
        count=2,
        reuse_tags={"K": coil_result},
        tag_generators={"S": fixed_s},
    )

    assert result.component_map["K"] == ["K1", "K2"]
    assert result.component_map["S"] == ["S_FIXED", "S_FIXED"]


# ---------------------------------------------------------------------------
# fixed_tags tests
# ---------------------------------------------------------------------------


def test_fixed_tags_basic():
    """build() with fixed_tags produces the specified tag."""
    state = create_autonumberer()

    builder = CircuitBuilder(state)
    builder.set_layout(x=0, y=0, spacing=80)
    builder.add_symbol(coil_symbol, "K", pins=("A1", "A2"))
    result = builder.build(fixed_tags={"K": "K1"})

    assert result.component_map["K"] == ["K1"]


def test_fixed_tags_lower_priority_than_tag_generators():
    """tag_generators should override fixed_tags for the same prefix."""
    state = create_autonumberer()

    def custom_gen(s):
        return s, "K99"

    builder = CircuitBuilder(state)
    builder.set_layout(x=0, y=0, spacing=80)
    builder.add_symbol(coil_symbol, "K", pins=("A1", "A2"))
    result = builder.build(
        fixed_tags={"K": "K1"},
        tag_generators={"K": custom_gen},
    )

    assert result.component_map["K"] == ["K99"]


def test_fixed_tags_higher_priority_than_internal():
    """fixed_tags should override _fixed_tag_generators (internal)."""
    state = create_autonumberer()

    builder = CircuitBuilder(state)
    builder.set_layout(x=0, y=0, spacing=80)
    builder.add_symbol(coil_symbol, "K", pins=("A1", "A2"))
    # Simulate internal fixed tag via add_reference
    builder._fixed_tag_generators["K"] = lambda s: (s, "K_INTERNAL")
    result = builder.build(fixed_tags={"K": "K_OVERRIDE"})

    assert result.component_map["K"] == ["K_OVERRIDE"]


def test_deprecated_string_in_tag_generators():
    """String value in tag_generators should emit DeprecationWarning."""
    import warnings

    state = create_autonumberer()

    builder = CircuitBuilder(state)
    builder.set_layout(x=0, y=0, spacing=80)
    builder.add_symbol(coil_symbol, "K", pins=("A1", "A2"))

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = builder.build(tag_generators={"K": "K1"})

    deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
    assert len(deprecation_warnings) == 1
    assert "tag_generators" in str(deprecation_warnings[0].message)
    assert result.component_map["K"] == ["K1"]


def test_deprecated_callable_in_reuse_tags():
    """Passing a callable to reuse_tags should emit DeprecationWarning."""
    import warnings

    state = create_autonumberer()

    def my_gen(s):
        return s, "K_CALLABLE"

    builder = CircuitBuilder(state)
    builder.set_layout(x=0, y=0, spacing=80)
    builder.add_symbol(coil_symbol, "K", pins=("A1", "A2"))

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = builder.build(reuse_tags={"K": my_gen})

    deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
    assert len(deprecation_warnings) == 1
    assert "callable" in str(deprecation_warnings[0].message).lower()
    assert result.component_map["K"] == ["K_CALLABLE"]


def test_deprecated_circuit_builder_in_reuse_tags():
    """Passing a CircuitBuilder to reuse_tags should emit DeprecationWarning."""
    import warnings

    state = create_autonumberer()

    # Build a coil circuit first
    coil_builder = CircuitBuilder(state)
    coil_builder.set_layout(x=0, y=0, spacing=80)
    coil_builder.add_symbol(coil_symbol, "K", pins=("A1", "A2"))
    coil_result = coil_builder.build(count=1)

    # Create a new builder to pass as CircuitBuilder (not BuildResult)
    reuse_builder = CircuitBuilder(state)
    reuse_builder.set_layout(x=0, y=0, spacing=80)
    reuse_builder.add_symbol(coil_symbol, "K", pins=("A1", "A2"))
    reuse_builder.build(count=1)  # Must build first so it has component_map

    contact_builder = CircuitBuilder(coil_result.state)
    contact_builder.set_layout(x=0, y=0, spacing=80)
    contact_builder.add_symbol(normally_open_symbol, "K", pins=("13", "14"))

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        contact_builder.build(count=1, reuse_tags={"K": reuse_builder})

    deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
    assert len(deprecation_warnings) == 1
    assert "CircuitBuilder" in str(deprecation_warnings[0].message)


def test_merge_reuse_tags_helper():
    """merge_reuse_tags builds a dict from (prefix, result) pairs."""
    from schematika.electrical.builder_models import merge_reuse_tags

    state = create_autonumberer()

    builder = CircuitBuilder(state)
    builder.set_layout(x=0, y=0, spacing=80)
    builder.add_symbol(coil_symbol, "K", pins=("A1", "A2"))
    builder.add_symbol(coil_symbol, "Q", pins=("A1", "A2"))
    result = builder.build(count=1)

    merged = merge_reuse_tags(("K", result), ("Q", result))

    assert isinstance(merged, dict)
    assert set(merged.keys()) == {"K", "Q"}
    assert merged["K"] is result
    assert merged["Q"] is result
