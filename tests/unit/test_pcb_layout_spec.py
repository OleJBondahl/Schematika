"""Tests for the LayoutSpec dataclass."""

import pytest

from schematika.pcb import LayoutSpec


def test_layout_spec_defaults() -> None:
    s = LayoutSpec()
    assert s.pin_spacing_mm == 10.0
    assert s.side_padding_mm == 5.0
    assert s.block_height_mm == 10.0
    assert s.slice_height_mm == 15.0
    assert s.section_gap_mm == 5.0
    assert s.inter_block_gap_mm == 20.0
    assert s.horizontal_margin_mm == 30.0
    assert s.vertical_margin_mm == 30.0
    assert s.power_terminator_offset_mm == 5.0
    assert s.connector_to_first_label_gap_mm == 2.5
    assert s.connector_to_first_symbol_gap_mm == 120.0


def test_layout_spec_label_and_symbol_gaps_distinct() -> None:
    s = LayoutSpec()
    assert s.connector_to_first_label_gap_mm == 2.5
    assert s.connector_to_first_symbol_gap_mm == 120.0


def test_connector_to_first_gaps_override() -> None:
    s = LayoutSpec(
        connector_to_first_label_gap_mm=20.0, connector_to_first_symbol_gap_mm=80.0
    )
    assert s.connector_to_first_label_gap_mm == 20.0
    assert s.connector_to_first_symbol_gap_mm == 80.0
    assert s.slice_height_mm == 15.0  # unchanged


def test_layout_spec_is_frozen() -> None:
    s = LayoutSpec()
    with pytest.raises((AttributeError, TypeError)):
        s.pin_spacing_mm = 99.0  # type: ignore


def test_layout_spec_overrides() -> None:
    s = LayoutSpec(pin_spacing_mm=12.0, vertical_margin_mm=40.0)
    assert s.pin_spacing_mm == 12.0
    assert s.vertical_margin_mm == 40.0
    assert s.side_padding_mm == 5.0


def test_layout_spec_wire_to_label_gap_default() -> None:
    assert LayoutSpec().wire_to_label_gap_mm == 5.0


def test_layout_spec_floating_top_label_gap_default() -> None:
    assert LayoutSpec().floating_top_label_gap_mm == 50.0


def test_layout_spec_floating_top_label_gap_override() -> None:
    assert LayoutSpec(floating_top_label_gap_mm=12.5).floating_top_label_gap_mm == 12.5
