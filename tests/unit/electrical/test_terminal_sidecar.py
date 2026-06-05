"""C3a: TerminalSidecar carries the terminal-CSV residue Wires can't."""

import pytest

from schematika.electrical.terminal_sidecar import TerminalSidecar, TerminalWireFact


def test_fact_is_frozen() -> None:
    f = TerminalWireFact(anchor="source", side="top")
    assert f.anchor == "source"
    assert f.side == "top"
    with pytest.raises(AttributeError):
        f.side = "bottom"  # ty: ignore[invalid-assignment]


def test_sidecar_holds_residue() -> None:
    sc = TerminalSidecar(
        facts=(TerminalWireFact(anchor="target", side="bottom"),),
        allocated_pin_keys=(("X1", "1"), ("X1", "2")),
        bridge_defs={"X1": "all"},
        prefix_bridge_tags=frozenset({"X2"}),
    )
    assert sc.facts[0].anchor == "target"
    assert ("X1", "2") in sc.allocated_pin_keys
    assert sc.bridge_defs["X1"] == "all"
    assert "X2" in sc.prefix_bridge_tags
    with pytest.raises(AttributeError):
        sc.facts = ()  # ty: ignore[invalid-assignment]
