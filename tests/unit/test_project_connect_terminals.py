"""connect_terminals(): two-row terminal-to-terminal emission on the native path."""

from pathlib import Path
from typing import Any

import pytest

from schematika.catalog.identifiers import DeviceTag, NetId
from schematika.catalog.refs import PinRef
from schematika.core.exceptions import CircuitValidationError
from schematika.electrical.builder import BuildResult
from schematika.electrical.system.system import Circuit
from schematika.electrical.terminal_sidecar import TerminalWireFact
from schematika.project import Project, _terminal_pairs_to_facts


def _circuit_fn(state: Any, **_kwargs: Any) -> BuildResult:
    return BuildResult(state=state, circuit=Circuit(), used_terminals=[])


def test_terminal_pairs_to_facts_emits_two_facts_on_one_wire():
    terminal_a = PinRef(device=DeviceTag("X1"), port_id="1")
    terminal_b = PinRef(device=DeviceTag("X2"), port_id="1")

    entries = _terminal_pairs_to_facts([(terminal_a, terminal_b, None)])

    assert len(entries) == 2
    wire_a, fact_a = entries[0]
    wire_b, fact_b = entries[1]
    assert wire_a is wire_b
    assert wire_a.source == terminal_a
    assert wire_a.target == terminal_b
    assert fact_a == TerminalWireFact(anchor="source", side="bottom")
    assert fact_b == TerminalWireFact(anchor="target", side="bottom")


def test_terminal_pairs_to_facts_uses_explicit_net():
    terminal_a = PinRef(device=DeviceTag("X1"), port_id="1")
    terminal_b = PinRef(device=DeviceTag("X2"), port_id="1")

    entries = _terminal_pairs_to_facts([(terminal_a, terminal_b, NetId("MY_NET"))])

    assert entries[0][0].net == "MY_NET"


def test_connect_terminals_returns_self_for_chaining():
    p = Project()

    result = p.connect_terminals(
        PinRef(device=DeviceTag("X1"), port_id="1"),
        PinRef(device=DeviceTag("X2"), port_id="1"),
    )

    assert result is p


def test_connect_terminals_emits_one_row_per_side_on_native_path(tmp_path):
    p = Project().use_native_terminal_emit()
    p.add_circuit("c1", _circuit_fn)
    p.connect_terminals(
        PinRef(device=DeviceTag("X1"), port_id="1"),
        PinRef(device=DeviceTag("X2"), port_id="1"),
    )
    p._build_all_circuits()
    p._resolve_field_devices()
    p._resolve_routes()

    csv_path = p._emit_system_csv(str(tmp_path))

    import csv

    with Path(csv_path).open(newline="", encoding="utf-8") as f:
        rows = {row["Terminal Tag"]: row for row in csv.DictReader(f)}

    assert rows["X1"]["Component To"] == "X2"
    assert rows["X1"]["Pin To"] == "1"
    assert rows["X2"]["Component To"] == "X1"
    assert rows["X2"]["Pin To"] == "1"


def test_connect_terminals_two_pairs_sharing_a_terminal_joins_not_crosswires(tmp_path):
    """Two connect_terminals() pairs targeting the same shared terminal (e.g. one
    per pole of a multi-pole terminal) must join on that shared side, not get
    merged into a fabricated pass-through between the two other-side terminals.

    Regression test: merge_terminal_csv's duplicate-key merge assumes any two
    rows sharing a (Terminal Tag, Terminal Pin) key represent a field-wire +
    external-wire pass-through and "balances" one side's excess entry onto the
    other -- correct for that case (see test_export_utils.py's
    test_duplicates_merged), but wrong here: X2's blank port is the target of
    two independent pairs, not a pass-through between X1 and X3.
    """
    p = Project().use_native_terminal_emit()
    p.add_circuit("c1", _circuit_fn)
    p.connect_terminals(
        PinRef(device=DeviceTag("X1"), port_id="L"),
        PinRef(device=DeviceTag("X2"), port_id=""),
    )
    p.connect_terminals(
        PinRef(device=DeviceTag("X3"), port_id="N"),
        PinRef(device=DeviceTag("X2"), port_id=""),
    )
    p._build_all_circuits()
    p._resolve_field_devices()
    p._resolve_routes()

    csv_path = p._emit_system_csv(str(tmp_path))

    import csv

    with Path(csv_path).open(newline="", encoding="utf-8") as f:
        rows = {row["Terminal Tag"]: row for row in csv.DictReader(f)}

    assert rows["X2"]["Component From"] == ""
    assert rows["X2"]["Pin From"] == ""
    assert rows["X2"]["Component To"] == "X1 / X3"
    assert rows["X2"]["Pin To"] == "L / N"
    assert rows["X1"]["Component To"] == "X2"
    assert rows["X1"]["Pin To"] == ""
    assert rows["X3"]["Component To"] == "X2"
    assert rows["X3"]["Pin To"] == ""


def test_connect_terminals_requires_native_terminal_emit(tmp_path):
    p = Project()
    p.add_circuit("c1", _circuit_fn)
    p.connect_terminals(
        PinRef(device=DeviceTag("X1"), port_id="1"),
        PinRef(device=DeviceTag("X2"), port_id="1"),
    )
    p._build_all_circuits()
    p._resolve_field_devices()
    p._resolve_routes()

    with pytest.raises(CircuitValidationError, match="use_native_terminal_emit"):
        p._emit_system_csv(str(tmp_path))
