"""Tests for the Terminal type."""

import pytest

from schematika.electrical.builder_models import BridgeMode
from schematika.electrical.terminal import Terminal


def test_terminal_str_returns_id():
    """str(Terminal) should return the terminal ID."""
    t = Terminal("X001", "Main 400V AC")
    assert str(t) == "X001"


def test_terminal_equality_with_string():
    """Terminal should be equal to its ID string."""
    t = Terminal("X001")
    assert t == "X001"
    assert t == "X001"


def test_terminal_hash_matches_string_hash():
    """Terminal hash should match string hash for dict key interchangeability."""
    t = Terminal("X001")
    assert hash(t) == hash("X001")


def test_terminal_in_set_with_strings():
    """Terminal should work in sets with strings."""
    t = Terminal("X001")
    assert t in {"X001", "X002"}
    assert "X001" in {t}


def test_terminal_as_dict_key():
    """Terminal should work as a dictionary key interchangeable with string."""
    t = Terminal("X001")
    d = {t: "value"}
    assert d["X001"] == "value"  # ty: ignore[invalid-argument-type]

    d2 = {"X001": "value"}
    assert d2[t] == "value"


def test_terminal_bridge_all():
    """Terminal with bridge=BridgeMode.ALL should store the bridge value."""
    t = Terminal("X003", bridge=BridgeMode.ALL)
    assert t.bridge == BridgeMode.ALL


def test_terminal_bridge_ranges():
    """Terminal with bridge ranges should store the list."""
    t = Terminal("X003", bridge=[(1, 3)])
    assert t.bridge == [(1, 3)]


def test_terminal_bridge_none_by_default():
    """Terminal bridge should default to None."""
    t = Terminal("X001")
    assert t.bridge is None


def test_terminal_reference_flag():
    """Terminal with reference=True should be marked as reference."""
    t = Terminal("PLC:DO", reference=True)
    assert t.reference is True


def test_terminal_reference_false_by_default():
    """Terminal reference should default to False."""
    t = Terminal("X001")
    assert t.reference is False


def test_terminal_frozen():
    """Terminal should be immutable (frozen dataclass)."""
    t = Terminal("X001", "Main 400V AC")
    with pytest.raises(AttributeError):
        t.id = "X002"


def test_terminal_title():
    """Terminal should store title."""
    t = Terminal("X001", "Main 400V AC")
    assert t.title == "Main 400V AC"


def test_terminal_importable_from_package():
    """Terminal should be importable from the top-level package."""
    from schematika.electrical import Terminal as T

    t = T("X001")
    assert str(t) == "X001"


def test_terminal_description():
    """Terminal should store product description."""
    t = Terminal("X001", "Main 400V AC", description="Terminal block")
    assert t.description == "Terminal block"


def test_terminal_description_default_empty():
    """Terminal description should default to empty string."""
    t = Terminal("X001", "Main 400V AC")
    assert t.description == ""


def test_terminal_mpn_field():
    t = Terminal("X001", "Main 400V", mpn="WAGO 2002-1401")
    assert t.mpn == "WAGO 2002-1401"


def test_terminal_mpn_default_empty():
    t = Terminal("X001", "Main 400V")
    assert t.mpn == ""
