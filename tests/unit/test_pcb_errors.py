"""Tests for schematika.pcb error classes."""

import pytest

from schematika.pcb.errors import (
    DuplicateMappingError,
    HeightOverflowError,
    IncompleteSliceError,
    MultiPinSliceError,
    OrphanSliceError,
    PCBBuildError,
    PinNotOnTemplateError,
    PortNotOnSymbolError,
    UnmappedPartError,
)


def test_pcb_build_error_is_exception():
    """PCBBuildError should be a standard Exception."""
    assert issubclass(PCBBuildError, Exception)
    with pytest.raises(PCBBuildError):
        msg = "test error"
        raise PCBBuildError(msg)


def test_pin_not_on_template_error():
    """PinNotOnTemplateError includes template, pin, available pins, and fix hint."""
    err = PinNotOnTemplateError(
        template_name="RelayK1",
        pin_name="99",
        available_pins=["1", "2", "3", "4"],
    )
    assert err.template_name == "RelayK1"
    assert err.pin_name == "99"
    assert err.available_pins == ["1", "2", "3", "4"]
    msg = str(err)
    assert "99" in msg
    assert "RelayK1" in msg
    assert "check" in msg.lower() or "available" in msg.lower()


def test_port_not_on_symbol_error():
    """PortNotOnSymbolError includes symbol, port, available ports, and fix hint."""
    err = PortNotOnSymbolError(
        symbol_name="no_contact",
        port_name="invalid_port",
        available_ports=["a", "b"],
    )
    assert err.symbol_name == "no_contact"
    assert err.port_name == "invalid_port"
    assert err.available_ports == ["a", "b"]
    msg = str(err)
    assert "invalid_port" in msg
    assert "no_contact" in msg
    assert "update" in msg.lower() or "use" in msg.lower()


def test_multi_pin_slice_error():
    """MultiPinSliceError includes template and pin count with fix hint."""
    err = MultiPinSliceError(
        template_name="SwitchS1",
        pin_count=3,
    )
    assert err.template_name == "SwitchS1"
    assert err.pin_count == 3
    msg = str(err)
    assert "SwitchS1" in msg
    assert "3" in msg
    assert "add" in msg.lower() or "support" in msg.lower()


def test_incomplete_slice_error_missing():
    """IncompleteSliceError with missing pins."""
    err = IncompleteSliceError(
        template_name="ConnectorJ1",
        mapped_pins=["1", "2"],
        all_pins=["1", "2", "3", "4"],
    )
    assert err.template_name == "ConnectorJ1"
    assert err.mapped_pins == ["1", "2"]
    assert err.all_pins == ["1", "2", "3", "4"]
    msg = str(err)
    assert "ConnectorJ1" in msg
    assert "missing" in msg.lower() or "mapped" in msg.lower()


def test_incomplete_slice_error_duplicates():
    """IncompleteSliceError with duplicated pins."""
    err = IncompleteSliceError(
        template_name="ConnectorJ2",
        mapped_pins=["1", "1", "2"],
        all_pins=["1", "2", "3"],
    )
    msg = str(err)
    assert "ConnectorJ2" in msg
    assert "duplicate" in msg.lower() or "mapped" in msg.lower()


def test_duplicate_mapping_error():
    """DuplicateMappingError includes type and identifier with fix hint."""
    err = DuplicateMappingError(
        mapping_type="SymbolMap",
        identifier="RelayK1",
    )
    assert err.mapping_type == "SymbolMap"
    assert err.identifier == "RelayK1"
    msg = str(err)
    assert "RelayK1" in msg
    assert "SymbolMap" in msg
    assert "remove" in msg.lower() or "duplicate" in msg.lower()


def test_unmapped_part_error():
    """UnmappedPartError includes part ref and template name with fix hint."""
    err = UnmappedPartError(
        part_ref="U1",
        template_name="OpAmpOPA2134",
    )
    assert err.part_ref == "U1"
    assert err.template_name == "OpAmpOPA2134"
    msg = str(err)
    assert "U1" in msg
    assert "OpAmpOPA2134" in msg
    assert "add" in msg.lower() or "mapping" in msg.lower()


def test_orphan_slice_error():
    """OrphanSliceError includes part ref and slice index with fix hint."""
    err = OrphanSliceError(
        part_ref="R1",
        slice_index=0,
    )
    assert err.part_ref == "R1"
    assert err.slice_index == 0
    msg = str(err)
    assert "R1" in msg
    assert "0" in msg
    assert "check" in msg.lower() or "reachable" in msg.lower()


def test_height_overflow_error():
    """HeightOverflowError includes column key, height, and max height with fix hint."""
    err = HeightOverflowError(
        column_key="col_1",
        height_mm=250.0,
        max_height_mm=210.0,
    )
    assert err.column_key == "col_1"
    assert err.height_mm == 250.0
    assert err.max_height_mm == 210.0
    msg = str(err)
    assert "col_1" in msg
    assert "250" in msg
    assert "210" in msg
    assert "decompose" in msg.lower() or "increase" in msg.lower()


def test_all_errors_inherit_from_pcb_build_error():
    """All custom PCB errors should inherit from PCBBuildError."""
    assert issubclass(PinNotOnTemplateError, PCBBuildError)
    assert issubclass(PortNotOnSymbolError, PCBBuildError)
    assert issubclass(MultiPinSliceError, PCBBuildError)
    assert issubclass(IncompleteSliceError, PCBBuildError)
    assert issubclass(DuplicateMappingError, PCBBuildError)
    assert issubclass(UnmappedPartError, PCBBuildError)
    assert issubclass(OrphanSliceError, PCBBuildError)
    assert issubclass(HeightOverflowError, PCBBuildError)
