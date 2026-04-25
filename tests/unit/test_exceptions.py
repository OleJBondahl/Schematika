"""Tests for custom exception classes (Task 10A)."""

import pytest

from schematika.electrical.exceptions import (
    CircuitValidationError,
    ComponentNotFoundError,
    PortNotFoundError,
    TagReuseError,
    WireLabelMismatchError,
)


def test_port_not_found_includes_available():
    """PortNotFoundError should include component tag, port, and available ports."""
    err = PortNotFoundError("F1", "PE", ["1", "2", "3", "4"])
    assert "PE" in str(err)
    assert "F1" in str(err)
    assert "['1', '2', '3', '4']" in str(err)
    assert err.component_tag == "F1"
    assert err.port_id == "PE"
    assert err.available_ports == ["1", "2", "3", "4"]


def test_component_not_found_message():
    """ComponentNotFoundError should include index and valid range."""
    err = ComponentNotFoundError(5, 3)
    assert "5" in str(err)
    assert "0-3" in str(err)


def test_tag_reuse_exhausted_message():
    """TagReuseError should include prefix and source tags."""
    err = TagReuseError("K", ["K1", "K2"])
    assert "K" in str(err)
    assert "K1" in str(err)
    assert "K2" in str(err)
    assert "2 tags" in str(err)
    assert err.prefix == "K"
    assert err.available_tags == ["K1", "K2"]


def test_wire_label_count_mismatch_message():
    """WireLabelMismatchError should include expected/actual counts."""
    err = WireLabelMismatchError(expected=5, actual=3, circuit_key="pumps")
    assert "5" in str(err)
    assert "3" in str(err)
    assert "pumps" in str(err)
    assert err.expected == 5
    assert err.actual == 3


def test_wire_label_count_mismatch_no_circuit_key():
    """WireLabelMismatchError should work without circuit_key."""
    err = WireLabelMismatchError(expected=5, actual=3)
    assert "5" in str(err)
    assert "3" in str(err)


def test_all_inherit_from_circuit_validation_error():
    """All custom exceptions should inherit from CircuitValidationError."""
    assert issubclass(PortNotFoundError, CircuitValidationError)
    assert issubclass(ComponentNotFoundError, CircuitValidationError)
    assert issubclass(TagReuseError, CircuitValidationError)
    assert issubclass(WireLabelMismatchError, CircuitValidationError)


def test_circuit_validation_error_is_exception():
    """CircuitValidationError should be a standard Exception."""
    assert issubclass(CircuitValidationError, Exception)
    with pytest.raises(CircuitValidationError):
        msg = "test error"
        raise CircuitValidationError(msg)
