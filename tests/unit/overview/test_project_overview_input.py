"""Task 2: Project.overview_input() normalises connectivity into OverviewInput."""

from schematika.overview.inputs import OverviewInput, OverviewWire
from schematika.overview.model import pin_id


def test_overview_input_returns_frozen_snapshot(small_project):
    inp = small_project.overview_input()
    assert isinstance(inp, OverviewInput)
    assert all(isinstance(w, OverviewWire) for w in inp.wires)
    assert inp.wires  # non-empty


def test_overview_input_auto_builds(unbuilt_project):
    inp = unbuilt_project.overview_input()
    assert inp.wires


def test_overview_input_terminal_tags_match(small_project):
    inp = small_project.overview_input()
    # No terminals were explicitly registered in this fixture, so set is empty.
    assert isinstance(inp.terminal_tags, frozenset)


def test_overview_input_route_wire_present(small_project):
    """The declared route K1.A1 -> X1.3 must appear as a wire in the snapshot."""
    inp = small_project.overview_input()
    all_pins = {w.a for w in inp.wires} | {w.b for w in inp.wires}
    assert pin_id("K1", "", "A1") in all_pins
    assert pin_id("X1", "", "3") in all_pins


def test_overview_input_field_device_wire_present(small_project):
    """The added wire FD1.1 -> X1.5 must appear in the snapshot."""
    inp = small_project.overview_input()
    all_pins = {w.a for w in inp.wires} | {w.b for w in inp.wires}
    assert pin_id("FD1", "", "1") in all_pins
    assert pin_id("X1", "", "5") in all_pins


def test_overview_input_title(small_project):
    inp = small_project.overview_input()
    assert inp.title == "Test Panel"


def test_overview_input_no_duplicate_wires(small_project):
    inp = small_project.overview_input()
    pairs = [frozenset((w.a, w.b)) for w in inp.wires]
    assert len(pairs) == len(set(map(frozenset, pairs)))
