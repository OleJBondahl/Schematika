"""Unit tests for core/options.py frozen dataclasses."""

import dataclasses

import pytest

from schematika.core.options import (
    BuildOptions,
    ConnectionOptions,
    DescriptorBuildOptions,
    EquipmentConfig,
    EquipmentPlacement,
    HorizontalLayoutConfig,
    PlacementOptions,
    SpdtConfig,
    SymbolConfig,
    TerminalConfig,
    TerminalDisplayOptions,
    _ConnectionPair,
    _WalkLoopContext,
)

# Classes that can be constructed with no args.
_ALL_CLASSES_NO_REQUIRED = [
    PlacementOptions,
    TerminalDisplayOptions,
    ConnectionOptions,
    TerminalConfig,
    SpdtConfig,
    BuildOptions,
    DescriptorBuildOptions,
]

# (factory, field) pairs for frozen checks — one per class.
_FROZEN_CASES = [
    (lambda: PlacementOptions(), "x_offset"),
    (lambda: TerminalDisplayOptions(), "label_pos"),
    (lambda: ConnectionOptions(), "connect_to_next"),
    (lambda: TerminalConfig(), "poles"),
    (lambda: SymbolConfig(tag_prefix="K"), "poles"),
    (lambda: SpdtConfig(), "poles"),
    (lambda: BuildOptions(), "count"),
    (lambda: DescriptorBuildOptions(), "spacing"),
]

# (factory,) for slots checks — one per class.
_SLOTS_FACTORIES = [
    lambda: PlacementOptions(),
    lambda: TerminalDisplayOptions(),
    lambda: ConnectionOptions(),
    lambda: TerminalConfig(),
    lambda: SymbolConfig(tag_prefix="K"),
    lambda: SpdtConfig(),
    lambda: BuildOptions(),
    lambda: DescriptorBuildOptions(),
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


class TestEquipmentConfig:
    """Smoke tests for EquipmentConfig dataclass."""

    def test_required_factory_and_tag_prefix(self):
        with pytest.raises(TypeError):
            EquipmentConfig()  # ty: ignore[missing-argument]

    def test_with_factory_and_tag_prefix(self):
        """EquipmentConfig constructs with factory and tag_prefix."""
        from schematika.pid.symbols import centrifugal_pump

        cfg = EquipmentConfig(factory=centrifugal_pump, tag_prefix="P")
        assert cfg.factory is centrifugal_pump
        assert cfg.tag_prefix == "P"
        assert cfg.factory_kwargs is None

    def test_frozen(self):
        from schematika.pid.symbols import centrifugal_pump

        cfg = EquipmentConfig(factory=centrifugal_pump, tag_prefix="P")
        with pytest.raises(dataclasses.FrozenInstanceError):
            cfg.tag_prefix = "X"  # ty: ignore[invalid-assignment]

    def test_slots(self):
        from schematika.pid.symbols import centrifugal_pump

        cfg = EquipmentConfig(factory=centrifugal_pump, tag_prefix="P")
        assert not hasattr(cfg, "__dict__")

    def test_factory_kwargs_passthrough(self):
        from schematika.pid.symbols import centrifugal_pump

        cfg = EquipmentConfig(
            factory=centrifugal_pump, tag_prefix="P", factory_kwargs={"a": 1}
        )
        assert cfg.factory_kwargs == {"a": 1}


class TestEquipmentPlacement:
    """Smoke tests for EquipmentPlacement dataclass."""

    def test_default_construction(self):
        """EquipmentPlacement() constructs with all fields at defaults."""
        plc = EquipmentPlacement()
        assert plc.relative_to is None
        assert plc.from_port == "outlet"
        assert plc.to_port == "inlet"
        assert plc.offset == (0.0, 0.0)
        assert plc.position is None
        assert plc.x == 0.0
        assert plc.y == 0.0

    def test_frozen(self):
        plc = EquipmentPlacement()
        with pytest.raises(dataclasses.FrozenInstanceError):
            plc.x = 99.0  # ty: ignore[invalid-assignment]

    def test_slots(self):
        plc = EquipmentPlacement()
        assert not hasattr(plc, "__dict__")

    def test_kw_only(self):
        with pytest.raises(TypeError):
            EquipmentPlacement(None)  # ty: ignore[too-many-positional-arguments]

    def test_absolute_position(self):
        plc = EquipmentPlacement(x=10.0, y=20.0)
        assert plc.x == 10.0
        assert plc.y == 20.0

    def test_relative_placement(self):
        plc = EquipmentPlacement(
            relative_to="pump", from_port="outlet", to_port="inlet"
        )
        assert plc.relative_to == "pump"
        assert plc.from_port == "outlet"
        assert plc.to_port == "inlet"


class TestBuildOptions:
    """Smoke tests for BuildOptions dataclass."""

    def test_default_construction(self):
        """BuildOptions() constructs with all fields at defaults."""
        opts = BuildOptions()
        assert opts.count == 1
        assert opts.state is None
        assert opts.wire_labels is None
        assert opts.connection_log_path is None
        assert opts.start_indices is None
        assert opts.terminal_start_indices is None
        assert opts.tag_generators is None
        assert opts.fixed_tags is None
        assert opts.terminal_maps is None
        assert opts.reuse_tags is None
        assert opts.reuse_terminals is None

    def test_frozen(self):
        opts = BuildOptions()
        with pytest.raises(dataclasses.FrozenInstanceError):
            opts.count = 2  # ty: ignore[invalid-assignment]

    def test_slots(self):
        opts = BuildOptions()
        assert not hasattr(opts, "__dict__")

    def test_kw_only(self):
        with pytest.raises(TypeError):
            BuildOptions(None)  # ty: ignore[too-many-positional-arguments]

    def test_count_override(self):
        """BuildOptions(count=3) stores the value correctly."""
        opts = BuildOptions(count=3)
        assert opts.count == 3

    def test_wire_labels_accepts_sequence(self):
        """wire_labels field accepts both lists and tuples."""
        opts_tuple = BuildOptions(wire_labels=("L1", "L2"))
        assert opts_tuple.wire_labels == ("L1", "L2")
        opts_list = BuildOptions(wire_labels=["L1", "L2"])
        assert opts_list.wire_labels == ["L1", "L2"]


class TestDescriptorBuildOptions:
    """Smoke tests for DescriptorBuildOptions dataclass."""

    def test_default_construction(self):
        """DescriptorBuildOptions() constructs with all fields at defaults."""
        opts = DescriptorBuildOptions()
        assert opts.position is None
        assert opts.x == 0.0
        assert opts.y == 0.0
        assert opts.spacing == 80.0
        assert opts.count == 1
        assert opts.wire_labels is None
        assert opts.reuse_tags is None
        assert opts.tag_generators is None
        assert opts.start_indices is None
        assert opts.terminal_start_indices is None

    def test_frozen(self):
        opts = DescriptorBuildOptions()
        with pytest.raises(dataclasses.FrozenInstanceError):
            opts.spacing = 40.0  # ty: ignore[invalid-assignment]

    def test_slots(self):
        opts = DescriptorBuildOptions()
        assert not hasattr(opts, "__dict__")

    def test_kw_only(self):
        with pytest.raises(TypeError):
            DescriptorBuildOptions(None)  # ty: ignore[too-many-positional-arguments]

    def test_count_override(self):
        opts = DescriptorBuildOptions(count=5)
        assert opts.count == 5


class TestHorizontalLayoutConfig:
    """Smoke tests for HorizontalLayoutConfig dataclass."""

    def test_construction_with_required(self):
        """HorizontalLayoutConfig constructs with required fields."""
        cfg = HorizontalLayoutConfig(
            start_x=0.0,
            start_y=0.0,
            count=3,
            spacing=80.0,
            generator_func_single=lambda *a: (a[0], []),
            default_tag_generators={},
        )
        assert cfg.count == 3
        assert cfg.spacing == 80.0
        assert cfg.tag_generators is None
        assert cfg.terminal_maps is None

    def test_frozen(self):
        cfg = HorizontalLayoutConfig(
            start_x=0.0,
            start_y=0.0,
            count=1,
            spacing=80.0,
            generator_func_single=lambda *a: (a[0], []),
            default_tag_generators={},
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            cfg.count = 2  # ty: ignore[invalid-assignment]

    def test_slots(self):
        cfg = HorizontalLayoutConfig(
            start_x=0.0,
            start_y=0.0,
            count=1,
            spacing=80.0,
            generator_func_single=lambda *a: (a[0], []),
            default_tag_generators={},
        )
        assert not hasattr(cfg, "__dict__")

    def test_missing_required_raises(self):
        with pytest.raises(TypeError):
            HorizontalLayoutConfig()  # ty: ignore[missing-argument]


class TestWalkLoopContext:
    """Smoke tests for _WalkLoopContext dataclass."""

    def _make_ctx(self):
        return _WalkLoopContext(
            placed=[],
            ir=object(),
            mapping=object(),
            net_kinds={},
            walked_chain_nets=set(),
            placed_slices=set(),
            net_by_pin={},
        )

    def test_construction(self):
        ctx = self._make_ctx()
        assert ctx.placed == []
        assert isinstance(ctx.walked_chain_nets, set)
        assert isinstance(ctx.placed_slices, set)

    def test_mutable_collections_are_mutable(self):
        """frozen=True only freezes attribute assignment; collection contents are mutable."""
        ctx = self._make_ctx()
        ctx.placed.append("x")
        assert ctx.placed == ["x"]
        ctx.walked_chain_nets.add("net1")
        assert "net1" in ctx.walked_chain_nets

    def test_frozen_attribute_assignment(self):
        ctx = self._make_ctx()
        with pytest.raises(dataclasses.FrozenInstanceError):
            ctx.placed = []

    def test_slots(self):
        ctx = self._make_ctx()
        assert not hasattr(ctx, "__dict__")


class TestConnectionPair:
    """Smoke tests for _ConnectionPair dataclass."""

    def _make_pair(self):
        return _ConnectionPair(
            comp_from={"spec": object(), "tag": "X1", "pins": []},
            pin_from="1",
            side_from=None,
            p_from=0,
            comp_to={"spec": object(), "tag": "K1", "pins": []},
            pin_to="A1",
            side_to=None,
            p_to=0,
        )

    def test_construction(self):
        pair = self._make_pair()
        assert pair.pin_from == "1"
        assert pair.pin_to == "A1"
        assert pair.side_from is None
        assert pair.p_from == 0

    def test_frozen(self):
        pair = self._make_pair()
        with pytest.raises(dataclasses.FrozenInstanceError):
            pair.pin_from = "2"

    def test_slots(self):
        pair = self._make_pair()
        assert not hasattr(pair, "__dict__")

    def test_kw_only(self):
        with pytest.raises(TypeError):
            _ConnectionPair(None)  # ty: ignore[missing-argument, too-many-positional-arguments]
