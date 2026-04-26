"""Unit tests for core/options.py frozen dataclasses."""

import dataclasses

import pytest

from schematika.core.options import (
    ConnectionOptions,
    PlacementOptions,
    TerminalConfig,
    TerminalDisplayOptions,
)

_ALL_CLASSES = [
    PlacementOptions,
    TerminalDisplayOptions,
    ConnectionOptions,
    TerminalConfig,
]


class TestConstructorSmoke:
    """Each dataclass constructs with all defaults."""

    @pytest.mark.parametrize("cls", _ALL_CLASSES)
    def test_default_construction(self, cls):
        cls()


class TestFrozenSmoke:
    """Assigning to a field raises FrozenInstanceError."""

    @pytest.mark.parametrize(
        ("cls", "field"),
        [
            (PlacementOptions, "x_offset"),
            (TerminalDisplayOptions, "label_pos"),
            (ConnectionOptions, "connect_to_next"),
            (TerminalConfig, "poles"),
        ],
    )
    def test_frozen(self, cls, field):
        obj = cls()
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(obj, field, None)


class TestSlotsSmoke:
    """Instances do not have __dict__ (slots=True)."""

    @pytest.mark.parametrize("cls", _ALL_CLASSES)
    def test_no_dict(self, cls):
        obj = cls()
        assert not hasattr(obj, "__dict__")


class TestKwOnlySmoke:
    """Passing positional args raises TypeError."""

    @pytest.mark.parametrize("cls", _ALL_CLASSES)
    def test_positional_raises(self, cls):
        with pytest.raises(TypeError):
            cls(None)  # type: ignore[call-arg]


class TestBridgeDefault:
    """ConnectionOptions.bridge defaults to None (cycle-avoidance pattern)."""

    def test_bridge_is_none(self):
        assert ConnectionOptions().bridge is None


class TestReplaceRoundTrip:
    """dataclasses.replace works on each dataclass."""

    def test_placement_replace(self):
        orig = PlacementOptions(x_offset=5.0)
        replaced = dataclasses.replace(orig, x_offset=10.0)
        assert replaced.x_offset == 10.0
        assert orig.x_offset == 5.0

    def test_display_replace(self):
        orig = TerminalDisplayOptions(label_pos="left")
        replaced = dataclasses.replace(orig, label_pos="right")
        assert replaced.label_pos == "right"
        assert orig.label_pos == "left"

    def test_connection_replace(self):
        orig = ConnectionOptions(connect_to_next=False)
        replaced = dataclasses.replace(orig, connect_to_next=True)
        assert replaced.connect_to_next is True
        assert orig.connect_to_next is False

    def test_config_replace(self):
        orig = TerminalConfig(poles=1)
        replaced = dataclasses.replace(orig, poles=3)
        assert replaced.poles == 3
        assert orig.poles == 1
