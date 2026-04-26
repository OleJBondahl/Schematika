"""Unit tests for core/options.py frozen dataclasses."""

import dataclasses

import pytest

from schematika.core.options import (
    ConnectionOptions,
    PlacementOptions,
    SpdtConfig,
    SymbolConfig,
    TerminalConfig,
    TerminalDisplayOptions,
)

# Classes that can be constructed with no args.
_ALL_CLASSES_NO_REQUIRED = [
    PlacementOptions,
    TerminalDisplayOptions,
    ConnectionOptions,
    TerminalConfig,
    SpdtConfig,
]

# (factory, field) pairs for frozen checks — one per class.
_FROZEN_CASES = [
    (lambda: PlacementOptions(), "x_offset"),
    (lambda: TerminalDisplayOptions(), "label_pos"),
    (lambda: ConnectionOptions(), "connect_to_next"),
    (lambda: TerminalConfig(), "poles"),
    (lambda: SymbolConfig(tag_prefix="K"), "poles"),
    (lambda: SpdtConfig(), "poles"),
]

# (factory,) for slots checks — one per class.
_SLOTS_FACTORIES = [
    lambda: PlacementOptions(),
    lambda: TerminalDisplayOptions(),
    lambda: ConnectionOptions(),
    lambda: TerminalConfig(),
    lambda: SymbolConfig(tag_prefix="K"),
    lambda: SpdtConfig(),
]


class TestConstructorSmoke:
    """Each dataclass constructs with all defaults."""

    @pytest.mark.parametrize("cls", _ALL_CLASSES_NO_REQUIRED)
    def test_default_construction(self, cls):
        cls()


class TestFrozenSmoke:
    """Assigning to a field raises FrozenInstanceError."""

    @pytest.mark.parametrize(("factory", "field"), _FROZEN_CASES)
    def test_frozen(self, factory, field):
        obj = factory()
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(obj, field, None)


class TestSlotsSmoke:
    """Instances do not have __dict__ (slots=True)."""

    @pytest.mark.parametrize("factory", _SLOTS_FACTORIES)
    def test_no_dict(self, factory):
        obj = factory()
        assert not hasattr(obj, "__dict__")


class TestKwOnlySmoke:
    """Passing positional args raises TypeError."""

    @pytest.mark.parametrize("cls", _ALL_CLASSES_NO_REQUIRED)
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


class TestSymbolConfig:
    """Smoke tests for SymbolConfig dataclass."""

    def test_required_tag_prefix(self):
        """SymbolConfig() raises TypeError when tag_prefix is missing."""
        with pytest.raises(TypeError):
            SymbolConfig()  # ty: ignore[missing-argument]

    def test_with_defaults(self):
        """SymbolConfig(tag_prefix="K") constructs with all other fields at defaults."""
        cfg = SymbolConfig(tag_prefix="K")
        assert cfg.tag_prefix == "K"
        assert cfg.poles == 1
        assert cfg.pins is None
        assert cfg.device is None
        assert cfg.wire_labels_above is None
        assert cfg.factory_kwargs is None

    def test_factory_kwargs_passthrough(self):
        """factory_kwargs field round-trips correctly."""
        cfg = SymbolConfig(tag_prefix="K", factory_kwargs={"a": 1})
        assert cfg.factory_kwargs == {"a": 1}


class TestSpdtConfig:
    """Smoke tests for SpdtConfig dataclass."""

    def test_default_construction(self):
        """SpdtConfig() constructs with all fields at defaults."""
        cfg = SpdtConfig()
        assert cfg.poles == 1
        assert cfg.pins is None
        assert cfg.inverted is False
        assert cfg.device is None
        assert cfg.wire_labels_above is None

    def test_poles_override(self):
        """SpdtConfig(poles=2) stores the value correctly."""
        cfg = SpdtConfig(poles=2)
        assert cfg.poles == 2
