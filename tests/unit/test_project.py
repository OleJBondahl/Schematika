"""Tests for the Project class."""

import os
import tempfile
from dataclasses import replace
from unittest.mock import MagicMock, patch

import pytest

from schematika.electrical import BridgeMode, Terminal
from schematika.electrical.builder import BuildResult
from schematika.electrical.system.system import Circuit
from schematika.project import Project


def test_project_creation():
    """Project should initialize with defaults."""
    p = Project()
    assert p.title == ""
    assert p.font == "Times New Roman"
    assert p._state is not None


def test_project_custom_params():
    """Project should accept custom parameters."""
    p = Project(
        title="Test",
        drawing_number="T-001",
        author="Author",
        project="Proj",
        revision="A1",
        font="Arial",
    )
    assert p.title == "Test"
    assert p.drawing_number == "T-001"
    assert p.font == "Arial"


def test_terminal_registration():
    """Terminals should be registered and retrievable."""
    p = Project()
    p.terminals(
        Terminal("X1", "Main Power"),
        Terminal("X2", "AC Input"),
        Terminal("X3", "24V", bridge=BridgeMode.ALL),
    )
    assert len(p._terminals) == 3
    assert "X1" in p._terminals
    assert p._terminals["X3"].bridge == BridgeMode.ALL


def test_set_pin_start():
    """set_pin_start should update terminal counter in state."""
    p = Project()
    p.set_pin_start("X1", 5)
    assert p._state.terminal_counters["X1"] == 5


def test_page_registration():
    """Pages should be registered in order."""
    p = Project()
    p.page("Motor Circuits", "motors")
    p.page("PSU", "psu")
    assert len(p._pages) == 2
    assert p._pages[0].title == "Motor Circuits"
    assert p._pages[1].circuit_key == "psu"


def test_terminal_report_registration():
    """terminal_report should add a page definition."""
    p = Project()
    p.terminal_report()
    assert len(p._pages) == 1
    assert p._pages[0].page_type == "terminal_report"


def test_front_page_registration():
    """front_page should add a page definition."""
    p = Project()
    p.front_page("readme.md", notice="Test notice")
    assert p._pages[0].page_type == "front"
    assert p._pages[0].notice == "Test notice"


def test_circuit_descriptor_registration():
    """circuit() with descriptors should register correctly."""
    from schematika.electrical import comp, ref, term
    from schematika.electrical.symbols.coils import coil

    p = Project()
    p.circuit(
        "valve_coils",
        components=[
            ref("PLC:DO"),
            comp(coil, "K", pins=("A1", "A2")),
            term("X4"),
        ],
        count=3,
    )
    assert p._circuit_defs[0].factory == "descriptors"
    components = p._circuit_defs[0].components
    assert components is not None
    assert len(components) == 3


def test_build_svgs():
    """build_svgs should generate SVG files for each circuit."""

    def my_builder(state, **kwargs):
        return BuildResult(state=state, circuit=Circuit(), used_terminals=["X3", "X4"])

    with tempfile.TemporaryDirectory() as tmpdir:
        p = Project()
        p.terminals(Terminal("X3", "24V"), Terminal("X4", "GND"))
        p.add_circuit("estop", my_builder)

        output_dir = os.path.join(tmpdir, "output")
        p.build_svgs(output_dir)

        # Check that SVG was generated
        svg_path = os.path.join(output_dir, "estop.svg")
        assert os.path.exists(svg_path), f"SVG not found at {svg_path}"

        # Check that system terminals CSV was generated
        csv_path = os.path.join(output_dir, "system_terminals.csv")
        assert os.path.exists(csv_path), f"CSV not found at {csv_path}"


def test_build_multiple_circuits():
    """build_svgs should handle multiple circuits."""

    def builder_a(state, **kwargs):
        return BuildResult(state=state, circuit=Circuit(), used_terminals=["X3", "X4"])

    def builder_b(state, **kwargs):
        return BuildResult(state=state, circuit=Circuit(), used_terminals=["X5", "X6"])

    with tempfile.TemporaryDirectory() as tmpdir:
        p = Project()
        p.terminals(
            Terminal("X3", "24V"),
            Terminal("X4", "GND"),
            Terminal("X5", "Supply 1"),
            Terminal("X6", "Supply 2"),
        )

        p.add_circuit("estop", builder_a)
        p.add_circuit("co", builder_b)

        output_dir = os.path.join(tmpdir, "output")
        p.build_svgs(output_dir)

        assert os.path.exists(os.path.join(output_dir, "estop.svg"))
        assert os.path.exists(os.path.join(output_dir, "co.svg"))


def test_build_with_descriptors():
    """build_svgs should work with descriptor-based circuits."""
    from schematika.electrical import comp, term
    from schematika.electrical.symbols.coils import coil

    with tempfile.TemporaryDirectory() as tmpdir:
        p = Project()
        p.terminals(Terminal("X3", "24V"), Terminal("X4", "GND"))

        p.circuit(
            "coils",
            components=[
                term("X3"),
                comp(coil, "K", pins=("A1", "A2")),
                term("X4"),
            ],
            count=2,
        )

        output_dir = os.path.join(tmpdir, "output")
        p.build_svgs(output_dir)

        assert os.path.exists(os.path.join(output_dir, "coils.svg"))


def test_reuse_tags_between_circuits():
    """reuse_tags should resolve circuit dependencies correctly."""
    from schematika.electrical import comp, term
    from schematika.electrical.symbols.coils import coil
    from schematika.electrical.symbols.contacts import no_contact

    with tempfile.TemporaryDirectory() as tmpdir:
        p = Project()
        p.terminals(Terminal("X3", "24V"), Terminal("X4", "GND"))

        # Coils circuit (allocates K tags)
        p.circuit(
            "coils",
            components=[
                term("X3"),
                comp(coil, "K", pins=("A1", "A2")),
                term("X4"),
            ],
            count=2,
        )

        # Contacts circuit (reuses K tags from coils)
        p.circuit(
            "contacts",
            components=[
                term("X3"),
                comp(no_contact, "K", pins=("13", "14")),
                term("X4"),
            ],
            count=2,
            reuse_tags={"K": "coils"},
        )

        output_dir = os.path.join(tmpdir, "output")
        p.build_svgs(output_dir)

        assert os.path.exists(os.path.join(output_dir, "coils.svg"))
        assert os.path.exists(os.path.join(output_dir, "contacts.svg"))


# =========================================================================
# Additional tests for coverage improvement
# =========================================================================


class TestProjectInit:
    """Tests for Project.__init__() defaults and attributes."""

    def test_defaults_all_attributes(self):
        """All default values should be set correctly."""
        p = Project()
        assert p.title == ""
        assert p.drawing_number == ""
        assert p.author == ""
        assert p.project == ""
        assert p.revision == "00"
        assert p.logo is None
        assert p.font == "Times New Roman"
        assert p._terminals == {}
        assert p._circuit_defs == []
        assert p._pages == []
        assert p._results == {}

    def test_logo_param(self):
        """Project should accept a logo path."""
        p = Project(logo="/path/to/logo.png")
        assert p.logo == "/path/to/logo.png"


class TestTerminalRegistration:
    """Tests for terminal registration edge cases."""

    def test_overwrite_terminal(self):
        """Registering a terminal with same ID should overwrite."""
        p = Project()
        p.terminals(Terminal("X1", "First"))
        p.terminals(Terminal("X1", "Second"))
        assert len(p._terminals) == 1
        assert p._terminals["X1"].title == "Second"

    def test_empty_terminal_registration(self):
        """Calling terminals() with no args should not fail."""
        p = Project()
        p.terminals()
        assert len(p._terminals) == 0

    def test_reference_terminal(self):
        """Reference terminals should store reference=True."""
        p = Project()
        p.terminals(Terminal("PLC:DO", "PLC Output", reference=True))
        assert p._terminals["PLC:DO"].reference is True

    def test_terminal_with_pin_prefixes(self):
        """Terminal with pin_prefixes should be stored correctly."""
        p = Project()
        p.terminals(Terminal("X1", "Power", pin_prefixes=("L1", "L2", "L3")))
        assert p._terminals["X1"].pin_prefixes == ("L1", "L2", "L3")


class TestSetPinStart:
    """Tests for set_pin_start including prefix counter updates."""

    def test_set_pin_start_updates_prefix_counters(self):
        """set_pin_start should update all existing prefix counters for the terminal."""
        p = Project()
        # First, create prefix counters by building a circuit that uses prefixed terminals
        # Manually set up state with prefix counters
        p._state = replace(
            p._state,
            terminal_prefix_counters={
                "X1": {"L1": 2, "L2": 2, "L3": 2},
            },
        )
        p.set_pin_start("X1", 5)
        assert p._state.terminal_counters["X1"] == 5
        # All prefix counters should be updated to 5
        assert p._state.terminal_prefix_counters["X1"]["L1"] == 5
        assert p._state.terminal_prefix_counters["X1"]["L2"] == 5
        assert p._state.terminal_prefix_counters["X1"]["L3"] == 5

    def test_set_pin_start_without_prefix_counters(self):
        """set_pin_start should work when no prefix counters exist."""
        p = Project()
        p.set_pin_start("X2", 10)
        assert p._state.terminal_counters["X2"] == 10
        # prefix_counters should remain unchanged (empty)
        assert "X2" not in p._state.terminal_prefix_counters

    def test_set_pin_start_multiple_terminals(self):
        """set_pin_start for different terminals should not interfere."""
        p = Project()
        p.set_pin_start("X1", 5)
        p.set_pin_start("X2", 10)
        assert p._state.terminal_counters["X1"] == 5
        assert p._state.terminal_counters["X2"] == 10


class TestCircuitRegistration:
    """Tests for all circuit registration methods."""

    def test_custom_registration(self):
        """custom() should register a custom builder function circuit."""

        def my_builder(state, **kwargs):
            return BuildResult(
                state=state,
                circuit=Circuit(),
                used_terminals=[],
            )

        p = Project()
        p.add_circuit("my_circuit", my_builder, count=2, some_param="value")
        assert len(p._circuit_defs) == 1
        assert p._circuit_defs[0].key == "my_circuit"
        assert p._circuit_defs[0].factory == "custom"
        assert p._circuit_defs[0].count == 2
        assert p._circuit_defs[0].builder_fn is my_builder
        assert p._circuit_defs[0].params == {"some_param": "value"}

    def test_circuit_with_wire_labels(self):
        """Circuit registration should store wire_labels correctly."""
        from schematika.electrical import comp, term
        from schematika.electrical.symbols.coils import coil

        p = Project()
        p.circuit(
            "coils",
            components=[
                term("X3"),
                comp(coil, "K", pins=("A1", "A2")),
                term("X4"),
            ],
            count=2,
            wire_labels=["L1", "L2"],
        )
        assert p._circuit_defs[0].wire_labels == ["L1", "L2"]

    def test_circuit_with_reuse_tags(self):
        """Circuit registration should store reuse_tags correctly."""
        from schematika.electrical import comp, term
        from schematika.electrical.symbols.contacts import no_contact

        p = Project()
        p.circuit(
            "contacts",
            components=[
                term("X3"),
                comp(no_contact, "K", pins=("13", "14")),
                term("X4"),
            ],
            count=2,
            reuse_tags={"K": "coils"},
        )
        assert p._circuit_defs[0].reuse_tags == {"K": "coils"}

    def test_circuit_descriptor_with_start_indices(self):
        """circuit() should accept start_indices and terminal_start_indices."""
        from schematika.electrical import comp, term
        from schematika.electrical.symbols.coils import coil

        p = Project()
        p.circuit(
            "coils",
            components=[
                term("X3"),
                comp(coil, "K", pins=("A1", "A2")),
                term("X4"),
            ],
            count=2,
            start_indices={"K": 5},
            terminal_start_indices={"X3": 10},
        )
        assert p._circuit_defs[0].start_indices == {"K": 5}
        assert p._circuit_defs[0].terminal_start_indices == {"X3": 10}

    def test_multiple_circuits_registered_in_order(self):
        """Multiple circuits should be registered in order."""
        from schematika.electrical import comp, term
        from schematika.electrical.symbols.coils import coil

        p = Project()
        for key in ("estop", "coils", "contacts"):
            p.circuit(
                key,
                components=[
                    term("X3"),
                    comp(coil, "K", pins=("A1", "A2")),
                    term("X4"),
                ],
            )
        assert len(p._circuit_defs) == 3
        assert p._circuit_defs[0].key == "estop"
        assert p._circuit_defs[1].key == "coils"
        assert p._circuit_defs[2].key == "contacts"


class TestPageRegistration:
    """Tests for all page registration methods."""

    def test_plc_report_registration(self):
        """plc_report should add a page definition."""
        p = Project()
        p.plc_report(csv_path="plc_data.csv")
        assert len(p._pages) == 1
        assert p._pages[0].page_type == "plc_report"
        assert p._pages[0].csv_path == "plc_data.csv"

    def test_plc_report_default_csv(self):
        """plc_report with no csv_path should default to empty string."""
        p = Project()
        p.plc_report()
        assert p._pages[0].csv_path == ""

    def test_custom_page_registration(self):
        """custom_page should add a page with raw Typst content."""
        p = Project()
        p.custom_page("My Custom Page", "#text(size: 20pt)[Hello World]")
        assert len(p._pages) == 1
        assert p._pages[0].page_type == "custom"
        assert p._pages[0].title == "My Custom Page"
        assert p._pages[0].typst_content == "#text(size: 20pt)[Hello World]"

    def test_front_page_without_notice(self):
        """front_page without notice should default to None."""
        p = Project()
        p.front_page("readme.md")
        assert p._pages[0].notice is None

    def test_page_ordering(self):
        """Pages should be appended in registration order."""
        p = Project()
        p.front_page("readme.md")
        p.page("Motors", "motors")
        p.terminal_report()
        p.plc_report()
        p.custom_page("Notes", "content")
        assert len(p._pages) == 5
        assert p._pages[0].page_type == "front"
        assert p._pages[1].page_type == "schematic"
        assert p._pages[2].page_type == "terminal_report"
        assert p._pages[3].page_type == "plc_report"
        assert p._pages[4].page_type == "custom"


class TestBuildOneCircuit:
    """Tests for _build_one_circuit error paths and dispatching."""

    def test_reuse_tags_missing_source_raises(self):
        """Referencing a non-existent circuit via reuse_tags should raise ValueError."""
        from schematika.electrical import comp, term
        from schematika.electrical.symbols.coils import coil

        p = Project()
        p.terminals(Terminal("X3", "24V"), Terminal("X4", "GND"))
        p.circuit(
            "contacts",
            components=[
                term("X3"),
                comp(coil, "K", pins=("A1", "A2")),
                term("X4"),
            ],
            count=2,
            reuse_tags={"K": "nonexistent"},
        )
        with pytest.raises(ValueError, match="hasn't been built yet"):
            p.build_svgs(tempfile.mkdtemp())

    def test_unknown_factory_raises(self):
        """An unknown factory name should raise ValueError."""
        p = Project()
        # Manually inject an invalid factory name
        from schematika.project import _CircuitDef

        p._circuit_defs.append(
            _CircuitDef(key="bad", factory="nonexistent_factory", params={})
        )
        with pytest.raises(ValueError, match="Unknown circuit factory"):
            p.build_svgs(tempfile.mkdtemp())

    def test_descriptor_circuit_without_components_raises(self):
        """Descriptor circuit with no components should raise ValueError."""
        p = Project()
        from schematika.project import _CircuitDef

        p._circuit_defs.append(
            _CircuitDef(key="bad", factory="descriptors", components=None)
        )
        with pytest.raises(ValueError, match="has no components defined"):
            p.build_svgs(tempfile.mkdtemp())

    def test_custom_circuit_without_builder_fn_raises(self):
        """Custom circuit with no builder_fn should raise ValueError."""
        p = Project()
        from schematika.project import _CircuitDef

        p._circuit_defs.append(
            _CircuitDef(key="bad", factory="custom", builder_fn=None)
        )
        with pytest.raises(ValueError, match="has no builder_fn defined"):
            p.build_svgs(tempfile.mkdtemp())


class TestBuildCustomCircuit:
    """Tests for _build_custom_circuit method."""

    def test_custom_circuit_with_build_result(self):
        """Custom builder returning BuildResult should work."""
        from schematika.electrical.utils.autonumbering import create_autonumberer

        create_autonumberer()

        def my_builder(state, **kwargs):
            return BuildResult(
                state=state,
                circuit=Circuit(),
                used_terminals=[],
            )

        p = Project()
        p.terminals(Terminal("X3", "24V"))
        p.add_circuit("my_circuit", my_builder)

        with tempfile.TemporaryDirectory() as tmpdir:
            p.build_svgs(tmpdir)
            assert os.path.exists(os.path.join(tmpdir, "my_circuit.svg"))

    def test_custom_circuit_with_tuple_return(self):
        """Custom builder returning a tuple should be wrapped in BuildResult."""

        def my_builder(state, **kwargs):
            return (state, Circuit(), [])

        p = Project()
        p.add_circuit("my_circuit", my_builder)

        with tempfile.TemporaryDirectory() as tmpdir:
            p.build_svgs(tmpdir)
            assert os.path.exists(os.path.join(tmpdir, "my_circuit.svg"))

    def test_custom_circuit_with_kwargs(self):
        """Custom builder should receive extra kwargs from params."""
        received_kwargs = {}

        def my_builder(state, **kwargs):
            received_kwargs.update(kwargs)
            return BuildResult(
                state=state,
                circuit=Circuit(),
                used_terminals=[],
            )

        p = Project()
        p.add_circuit("my_circuit", my_builder, foo="bar", baz=42)

        with tempfile.TemporaryDirectory() as tmpdir:
            p.build_svgs(tmpdir)
        assert received_kwargs == {"foo": "bar", "baz": 42}


class TestBuildSvgs:
    """Tests for build_svgs method."""

    def test_build_svgs_with_bridge_defs(self):
        """build_svgs should apply bridge definitions from non-reference terminals."""

        def my_builder(state, **kwargs):
            return BuildResult(
                state=state, circuit=Circuit(), used_terminals=["X3", "X4"]
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            p = Project()
            p.terminals(
                Terminal("X3", "24V", bridge=BridgeMode.ALL),
                Terminal("X4", "GND", bridge=BridgeMode.ALL),
            )
            p.add_circuit("estop", my_builder)

            output_dir = os.path.join(tmpdir, "output")
            p.build_svgs(output_dir)

            # Check SVG and CSV exist
            assert os.path.exists(os.path.join(output_dir, "estop.svg"))
            assert os.path.exists(os.path.join(output_dir, "system_terminals.csv"))

    def test_build_svgs_reference_terminals_excluded_from_bridges(self):
        """Reference terminals should not contribute bridge definitions."""

        def my_builder(state, **kwargs):
            return BuildResult(
                state=state, circuit=Circuit(), used_terminals=["X3", "X4"]
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            p = Project()
            p.terminals(
                Terminal("PLC:DO", "PLC Output", reference=True, bridge=BridgeMode.ALL),
                Terminal("X3", "24V"),
                Terminal("X4", "GND"),
            )
            p.add_circuit("estop", my_builder)

            output_dir = os.path.join(tmpdir, "output")
            p.build_svgs(output_dir)

            assert os.path.exists(os.path.join(output_dir, "estop.svg"))

    def test_build_svgs_with_no_used_terminals(self):
        """build_svgs should skip per-circuit CSV when used_terminals is empty."""

        def my_builder(state, **kwargs):
            return BuildResult(
                state=state,
                circuit=Circuit(),
                used_terminals=[],
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            p = Project()
            p.add_circuit("my_circuit", my_builder)

            p.build_svgs(tmpdir)

            # SVG should exist, but no per-circuit terminals CSV
            assert os.path.exists(os.path.join(tmpdir, "my_circuit.svg"))
            assert not os.path.exists(os.path.join(tmpdir, "my_circuit_terminals.csv"))

    def test_build_svgs_creates_output_dir(self):
        """build_svgs should create the output directory if it does not exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = os.path.join(tmpdir, "deep", "nested", "output")
            p = Project()

            def my_builder(state, **kwargs):
                return BuildResult(state=state, circuit=Circuit(), used_terminals=[])

            p.add_circuit("test", my_builder)
            p.build_svgs(output_dir)

            assert os.path.isdir(output_dir)

    def test_build_svgs_with_wire_labels(self):
        """build_svgs should work with wire_labels on std circuits."""
        from schematika.electrical import comp, term
        from schematika.electrical.symbols.coils import coil

        with tempfile.TemporaryDirectory() as tmpdir:
            p = Project()
            p.terminals(Terminal("X3", "24V"), Terminal("X4", "GND"))
            p.circuit(
                "coils",
                components=[
                    term("X3"),
                    comp(coil, "K", pins=("A1", "A2")),
                    term("X4"),
                ],
                count=2,
                wire_labels=["BKWH1", "BKWH2", "BKWH3", "BKWH4"],
            )

            p.build_svgs(tmpdir)
            assert os.path.exists(os.path.join(tmpdir, "coils.svg"))


class TestAddPageToCompiler:
    """Tests for _add_page_to_compiler with mocked compiler."""

    def _make_project_with_results(self):
        """Helper: create a Project with a mock build result."""
        p = Project()
        p.terminals(
            Terminal("X3", "24V"),
            Terminal("X4", "GND"),
            Terminal("PLC:DO", "PLC Output", reference=True),
        )
        p._results = {
            "estop": BuildResult(
                state=p._state,
                circuit=Circuit(),
                used_terminals=["X3", "X4"],
            ),
        }
        return p

    def test_schematic_page(self):
        """Schematic page should call add_schematic_page on the compiler."""
        from schematika.project import _PageDef

        p = self._make_project_with_results()
        compiler = MagicMock()
        svg_paths = {"estop": "/tmp/estop.svg"}
        csv_paths = {"estop": "/tmp/estop_terminals.csv"}

        page_def = _PageDef(page_type="schematic", title="E-Stop", circuit_key="estop")
        p._add_page_to_compiler(
            compiler, page_def, svg_paths, csv_paths, "/tmp/system.csv"
        )

        compiler.add_schematic_page.assert_called_once_with(
            "E-Stop", "/tmp/estop.svg", "/tmp/estop_terminals.csv"
        )

    def test_schematic_page_without_csv(self):
        """Schematic page without CSV should pass None."""
        from schematika.project import _PageDef

        p = self._make_project_with_results()
        compiler = MagicMock()
        svg_paths = {"estop": "/tmp/estop.svg"}
        csv_paths = {}  # No CSV for this circuit

        page_def = _PageDef(page_type="schematic", title="E-Stop", circuit_key="estop")
        p._add_page_to_compiler(
            compiler, page_def, svg_paths, csv_paths, "/tmp/system.csv"
        )

        compiler.add_schematic_page.assert_called_once_with(
            "E-Stop", "/tmp/estop.svg", None
        )

    def test_schematic_page_missing_key(self):
        """Schematic page with missing circuit key should not call add_schematic_page."""
        from schematika.project import _PageDef

        p = self._make_project_with_results()
        compiler = MagicMock()

        page_def = _PageDef(
            page_type="schematic", title="Missing", circuit_key="missing"
        )
        p._add_page_to_compiler(compiler, page_def, {}, {}, "/tmp/system.csv")

        compiler.add_schematic_page.assert_not_called()

    def test_front_page(self):
        """Front page should call add_front_page on the compiler."""
        from schematika.project import _PageDef

        p = self._make_project_with_results()
        compiler = MagicMock()

        page_def = _PageDef(
            page_type="front", md_path="readme.md", notice="Test notice"
        )
        p._add_page_to_compiler(compiler, page_def, {}, {}, "/tmp/system.csv")

        compiler.add_front_page.assert_called_once_with(
            "readme.md", notice="Test notice"
        )

    def test_terminal_report_page(self):
        """Terminal report should call add_terminal_report with descriptions, excluding references."""
        from schematika.project import _PageDef

        p = self._make_project_with_results()
        compiler = MagicMock()

        page_def = _PageDef(page_type="terminal_report")
        p._add_page_to_compiler(compiler, page_def, {}, {}, "/tmp/system.csv")

        compiler.add_terminal_report.assert_called_once()
        call_args = compiler.add_terminal_report.call_args
        assert call_args[0][0] == "/tmp/system.csv"
        descriptions = call_args[0][1]
        # Reference terminal should be excluded
        assert "PLC:DO" not in descriptions
        assert "X3" in descriptions
        assert "X4" in descriptions

    def test_plc_report_page_with_csv(self):
        """PLC report with a CSV path should call add_plc_report."""
        from schematika.project import _PageDef

        p = self._make_project_with_results()
        compiler = MagicMock()

        page_def = _PageDef(page_type="plc_report", csv_path="/tmp/plc.csv")
        p._add_page_to_compiler(compiler, page_def, {}, {}, "/tmp/system.csv")

        compiler.add_plc_report.assert_called_once_with("/tmp/plc.csv")

    def test_plc_report_page_without_csv(self):
        """PLC report without CSV path should not call add_plc_report."""
        from schematika.project import _PageDef

        p = self._make_project_with_results()
        compiler = MagicMock()

        page_def = _PageDef(page_type="plc_report", csv_path="")
        p._add_page_to_compiler(compiler, page_def, {}, {}, "/tmp/system.csv")

        compiler.add_plc_report.assert_not_called()

    def test_custom_page(self):
        """Custom page should call add_custom_page on the compiler."""
        from schematika.project import _PageDef

        p = self._make_project_with_results()
        compiler = MagicMock()

        page_def = _PageDef(
            page_type="custom",
            title="Notes",
            typst_content="#text[Hello]",
        )
        p._add_page_to_compiler(compiler, page_def, {}, {}, "/tmp/system.csv")

        compiler.add_custom_page.assert_called_once_with("Notes", "#text[Hello]")


class TestBuildMethod:
    """Tests for the build() method (PDF compilation) with mocked Typst."""

    def _mock_build(self, project, output_pdf, temp_dir, keep_temp=True):
        """Helper to run build() with mocked Typst compiler."""
        mock_typst_module = MagicMock()
        mock_compiler_inst = MagicMock()
        mock_typst_module.TypstCompiler.return_value = mock_compiler_inst
        mock_typst_module.TypstCompilerConfig = MagicMock()

        with patch.dict(
            "sys.modules",
            {
                "schematika.rendering.typst.compiler": mock_typst_module,
            },
        ):
            project.build(output_pdf, temp_dir=temp_dir, keep_temp=keep_temp)

        return mock_typst_module, mock_compiler_inst

    def test_build_calls_typst_compiler(self):
        """build() should create TypstCompiler, add pages, and compile."""

        def my_builder(state, **kwargs):
            return BuildResult(
                state=state, circuit=Circuit(), used_terminals=["X3", "X4"]
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_pdf = os.path.join(tmpdir, "output.pdf")
            temp_dir = os.path.join(tmpdir, "temp")

            p = Project(
                title="Test",
                drawing_number="T-001",
                author="Author",
                project="Proj",
                revision="A1",
                font="Arial",
            )
            p.terminals(Terminal("X3", "24V"), Terminal("X4", "GND"))
            p.add_circuit("estop", my_builder)
            p.page("Test Page", "estop")

            mock_module, mock_compiler = self._mock_build(
                p, output_pdf, temp_dir, keep_temp=True
            )

            mock_module.TypstCompiler.assert_called_once()
            mock_compiler.compile.assert_called_once_with(output_pdf)

    def test_build_generates_per_circuit_csv(self):
        """build() should generate per-circuit terminal CSV for circuits with used_terminals."""

        def my_builder(state, **kwargs):
            return BuildResult(
                state=state, circuit=Circuit(), used_terminals=["X3", "X4"]
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_pdf = os.path.join(tmpdir, "output.pdf")
            temp_dir = os.path.join(tmpdir, "temp")

            p = Project()
            p.terminals(Terminal("X3", "24V"), Terminal("X4", "GND"))
            p.add_circuit("estop", my_builder)

            self._mock_build(p, output_pdf, temp_dir, keep_temp=True)

            # Per-circuit CSV should be generated (estop has used_terminals)
            csv_path = os.path.join(temp_dir, "estop_terminals.csv")
            assert os.path.exists(csv_path)

    def test_build_with_bridge_defs(self):
        """build() should apply bridge definitions from terminals."""

        def my_builder(state, **kwargs):
            return BuildResult(
                state=state, circuit=Circuit(), used_terminals=["X3", "X4"]
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_pdf = os.path.join(tmpdir, "output.pdf")
            temp_dir = os.path.join(tmpdir, "temp")

            p = Project()
            p.terminals(
                Terminal("X3", "24V", bridge=BridgeMode.ALL),
                Terminal("X4", "GND", bridge=BridgeMode.ALL),
            )
            p.add_circuit("estop", my_builder)

            self._mock_build(p, output_pdf, temp_dir, keep_temp=True)

            # System CSV should exist
            system_csv = os.path.join(temp_dir, "system_terminals.csv")
            assert os.path.exists(system_csv)

    def test_build_cleans_temp_dir_by_default(self):
        """build() should remove temp_dir when keep_temp=False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_pdf = os.path.join(tmpdir, "output.pdf")
            temp_dir = os.path.join(tmpdir, "temp_build")

            def my_builder(state, **kwargs):
                return BuildResult(state=state, circuit=Circuit(), used_terminals=[])

            p = Project()
            p.add_circuit("test_circuit", my_builder)

            self._mock_build(p, output_pdf, temp_dir, keep_temp=False)

            # temp_dir should have been cleaned up
            assert not os.path.exists(temp_dir)

    def test_build_keeps_temp_dir_when_requested(self):
        """build() should keep temp_dir when keep_temp=True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_pdf = os.path.join(tmpdir, "output.pdf")
            temp_dir = os.path.join(tmpdir, "temp_build")

            def my_builder(state, **kwargs):
                return BuildResult(state=state, circuit=Circuit(), used_terminals=[])

            p = Project()
            p.add_circuit("test_circuit", my_builder)

            self._mock_build(p, output_pdf, temp_dir, keep_temp=True)

            # temp_dir should still exist
            assert os.path.exists(temp_dir)

    def test_build_with_logo(self):
        """build() should handle logo path configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_pdf = os.path.join(tmpdir, "output.pdf")
            temp_dir = os.path.join(tmpdir, "temp")
            logo_path = os.path.join(tmpdir, "logo.png")
            # Create a dummy logo file
            with open(logo_path, "w") as f:
                f.write("dummy")

            def my_builder(state, **kwargs):
                return BuildResult(state=state, circuit=Circuit(), used_terminals=[])

            p = Project(logo=logo_path)
            p.add_circuit("test", my_builder)

            self._mock_build(p, output_pdf, temp_dir, keep_temp=True)


class TestBuildAllCircuits:
    """Tests for _build_all_circuits method."""

    def test_state_threading_between_circuits(self):
        """State should be threaded from one circuit to the next."""
        from schematika.electrical import comp, term
        from schematika.electrical.symbols.coils import coil

        with tempfile.TemporaryDirectory() as tmpdir:
            p = Project()
            p.terminals(Terminal("X3", "24V"), Terminal("X4", "GND"))

            # Register two circuits that both use "K" prefix
            p.circuit(
                "coils1",
                components=[
                    term("X3"),
                    comp(coil, "K", pins=("A1", "A2")),
                    term("X4"),
                ],
                count=2,
            )
            p.circuit(
                "coils2",
                components=[
                    term("X3"),
                    comp(coil, "K", pins=("A1", "A2")),
                    term("X4"),
                ],
                count=2,
            )

            p.build_svgs(tmpdir)

            # Both circuits should be built
            assert "coils1" in p._results
            assert "coils2" in p._results

            # Second circuit should have K3, K4 (since first used K1, K2)
            assert "K" in p._results["coils2"].component_map
            assert p._results["coils2"].component_map["K"] == ["K3", "K4"]

    def test_results_cleared_on_each_build(self):
        """_build_all_circuits should clear results before building."""

        def my_builder(state, **kwargs):
            return BuildResult(state=state, circuit=Circuit(), used_terminals=[])

        with tempfile.TemporaryDirectory() as tmpdir:
            p = Project()
            p.add_circuit("circuit1", my_builder)

            p.build_svgs(os.path.join(tmpdir, "out1"))
            assert "circuit1" in p._results

            # Build again - results should be re-created, not appended
            p.build_svgs(os.path.join(tmpdir, "out2"))
            assert len(p._results) == 1


class TestEdgeCases:
    """Edge case and integration tests."""

    def test_empty_project_build(self):
        """Building a project with no circuits should succeed (just system CSV)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Project()
            p.build_svgs(tmpdir)
            # Only system CSV should be generated
            assert os.path.exists(os.path.join(tmpdir, "system_terminals.csv"))

    def test_circuit_def_dataclass_defaults(self):
        """_CircuitDef should have correct defaults."""
        from schematika.project import _CircuitDef

        cdef = _CircuitDef(key="test", factory="coil")
        assert cdef.count == 1
        assert cdef.wire_labels is None
        assert cdef.reuse_tags is None
        assert cdef.components is None
        assert cdef.builder_fn is None
        assert cdef.start_indices is None
        assert cdef.terminal_start_indices is None
        assert cdef.params == {}

    def test_page_def_dataclass_defaults(self):
        """_PageDef should have correct defaults."""
        from schematika.project import _PageDef

        pdef = _PageDef(page_type="schematic")
        assert pdef.title == ""
        assert pdef.circuit_key == ""
        assert pdef.md_path == ""
        assert pdef.notice is None
        assert pdef.csv_path == ""
        assert pdef.typst_content == ""

    def test_build_svgs_no_bridge_when_no_bridge_defs(self):
        """build_svgs should not call update_csv when no bridge defs exist."""

        def my_builder(state, **kwargs):
            return BuildResult(
                state=state, circuit=Circuit(), used_terminals=["X3", "X4"]
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            p = Project()
            # Terminals without bridge
            p.terminals(Terminal("X3", "24V"), Terminal("X4", "GND"))
            p.add_circuit("estop", my_builder)
            p.build_svgs(tmpdir)
            # Should succeed without issues
            assert os.path.exists(os.path.join(tmpdir, "system_terminals.csv"))


# =========================================================================
# Tests for plc_rack() and external_connections()
# =========================================================================


class TestPlcRack:
    """Tests for Project.plc_rack() and Project.external_connections()."""

    def _make_di_module(self):
        """Return a simple DI module for testing."""
        from schematika.electrical.plc_resolver import PlcModuleType

        return PlcModuleType(
            mpn="750-1405",
            signal_type="DI",
            channels=4,
            pins_per_channel=("",),
        )

    def test_plc_rack_stores_rack(self):
        """plc_rack() stores the rack on the project."""
        di_module = self._make_di_module()
        rack = [("DI1", di_module)]
        p = Project()
        p.plc_rack(rack)
        assert p._plc_rack == rack

    def test_plc_rack_returns_self(self):
        """plc_rack() returns self for method chaining."""
        p = Project()
        result = p.plc_rack([])
        assert result is p

    def test_plc_rack_default_is_none(self):
        """_plc_rack should default to None on a new Project."""
        p = Project()
        assert p._plc_rack is None

    def test_plc_rack_can_be_overwritten(self):
        """Calling plc_rack() twice should replace the previous rack."""
        di_module = self._make_di_module()
        rack1 = [("DI1", di_module)]
        rack2 = [("DI1", di_module), ("DI2", di_module)]
        p = Project()
        p.plc_rack(rack1)
        p.plc_rack(rack2)
        assert p._plc_rack == rack2

    def test_external_connections_stores(self):
        """external_connections() stores the connections."""
        p = Project()
        connections = [("SensorA", "Sig+", "X100", "1", "PLC:DI", "")]
        p.external_connections(connections)
        assert p._external_connections == connections

    def test_external_connections_returns_self(self):
        """external_connections() returns self for method chaining."""
        p = Project()
        result = p.external_connections([])
        assert result is p

    def test_external_connections_default_is_empty(self):
        """_external_connections should default to [] on a new Project."""
        p = Project()
        assert p._external_connections == []

    def test_external_connections_makes_copy(self):
        """external_connections() should copy the input list."""
        p = Project()
        original = [("SensorA", "Sig+", "X100", "1", "PLC:DI", "")]
        p.external_connections(original)
        original.append(("SensorB", "Sig+", "X100", "2", "PLC:DI", ""))
        # The project's list should NOT be affected by the mutation
        assert len(p._external_connections) == 1

    def test_plc_report_without_csv_path_accepted(self):
        """plc_report() with no csv_path is accepted when rack is configured."""
        p = Project()
        p.plc_rack([])
        p.plc_report()
        assert p._pages[-1].page_type == "plc_report"
        assert p._pages[-1].csv_path == ""

    def test_plc_report_returns_self(self):
        """plc_report() returns self for method chaining."""
        p = Project()
        result = p.plc_report()
        assert result is p

    def test_chaining(self):
        """plc_rack(), external_connections(), plc_report() can be chained."""
        di_module = self._make_di_module()
        p = (
            Project()
            .plc_rack([("DI1", di_module)])
            .external_connections([])
            .plc_report()
        )
        assert p._plc_rack is not None
        assert p._external_connections == []
        assert p._pages[-1].page_type == "plc_report"


class TestGeneratePlcCsv:
    """Tests for _generate_plc_csv and build() auto-generation integration."""

    def _make_rack(self):
        """Return a minimal DO rack for testing."""
        from schematika.electrical.plc_resolver import PlcModuleType

        do_module = PlcModuleType(
            mpn="750-1504",
            signal_type="DO",
            channels=4,
            pins_per_channel=("",),
        )
        return [("DO1", do_module)]

    def test_generate_plc_csv_creates_file(self):
        """_generate_plc_csv should create a CSV file at the given path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            rack = self._make_rack()
            p = Project()
            p.plc_rack(rack)

            csv_path = os.path.join(tmpdir, "plc_connections.csv")
            p._generate_plc_csv(csv_path)

            assert os.path.exists(csv_path)

    def test_generate_plc_csv_has_header(self):
        """Generated PLC CSV should have the expected header row."""
        import csv

        with tempfile.TemporaryDirectory() as tmpdir:
            rack = self._make_rack()
            p = Project()
            p.plc_rack(rack)

            csv_path = os.path.join(tmpdir, "plc_connections.csv")
            p._generate_plc_csv(csv_path)

            with open(csv_path, newline="") as f:
                reader = csv.reader(f)
                header = next(reader)

            assert header == [
                "Module",
                "MPN",
                "PLC Pin",
                "Component",
                "Pin",
                "Terminal",
            ]

    def test_build_auto_generates_plc_csv_when_rack_set(self):
        """build() should auto-generate plc_connections.csv when rack is set."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_pdf = os.path.join(tmpdir, "output.pdf")
            temp_dir = os.path.join(tmpdir, "temp")

            rack = self._make_rack()
            p = Project()
            p.plc_rack(rack)

            mock_typst_module = MagicMock()
            mock_compiler_inst = MagicMock()
            mock_typst_module.TypstCompiler.return_value = mock_compiler_inst
            mock_typst_module.TypstCompilerConfig = MagicMock()

            with patch.dict(
                "sys.modules",
                {"schematika.rendering.typst.compiler": mock_typst_module},
            ):
                p.build(output_pdf, temp_dir=temp_dir, keep_temp=True)

            plc_csv = os.path.join(temp_dir, "plc_connections.csv")
            assert os.path.exists(plc_csv)

    def test_build_passes_plc_csv_to_compiler_when_no_explicit_path(self):
        """build() should pass auto-generated CSV to add_plc_report when csv_path is empty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_pdf = os.path.join(tmpdir, "output.pdf")
            temp_dir = os.path.join(tmpdir, "temp")

            rack = self._make_rack()
            p = Project()
            p.plc_rack(rack)
            p.plc_report()  # no csv_path

            mock_typst_module = MagicMock()
            mock_compiler_inst = MagicMock()
            mock_typst_module.TypstCompiler.return_value = mock_compiler_inst
            mock_typst_module.TypstCompilerConfig = MagicMock()

            with patch.dict(
                "sys.modules",
                {"schematika.rendering.typst.compiler": mock_typst_module},
            ):
                p.build(output_pdf, temp_dir=temp_dir, keep_temp=True)

            mock_compiler_inst.add_plc_report.assert_called_once()
            call_arg = mock_compiler_inst.add_plc_report.call_args[0][0]
            assert "plc_connections.csv" in call_arg

    def test_build_explicit_csv_path_takes_priority(self):
        """When explicit csv_path is given it should override auto-generation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_pdf = os.path.join(tmpdir, "output.pdf")
            temp_dir = os.path.join(tmpdir, "temp")

            # Create a dummy explicit CSV
            os.makedirs(temp_dir, exist_ok=True)
            explicit_csv = os.path.join(tmpdir, "explicit_plc.csv")
            with open(explicit_csv, "w") as f:
                f.write("dummy")

            rack = self._make_rack()
            p = Project()
            p.plc_rack(rack)
            p.plc_report(csv_path=explicit_csv)

            mock_typst_module = MagicMock()
            mock_compiler_inst = MagicMock()
            mock_typst_module.TypstCompiler.return_value = mock_compiler_inst
            mock_typst_module.TypstCompilerConfig = MagicMock()

            with patch.dict(
                "sys.modules",
                {"schematika.rendering.typst.compiler": mock_typst_module},
            ):
                p.build(output_pdf, temp_dir=temp_dir, keep_temp=True)

            mock_compiler_inst.add_plc_report.assert_called_once_with(explicit_csv)

    def test_add_page_to_compiler_plc_report_uses_plc_csv_path(self):
        """_add_page_to_compiler should use plc_csv_path when page has no csv_path."""
        from schematika.project import _PageDef

        p = Project()
        compiler = MagicMock()

        page_def = _PageDef(page_type="plc_report", csv_path="")
        p._add_page_to_compiler(
            compiler, page_def, {}, {}, "/tmp/system.csv", "/tmp/plc_auto.csv"
        )

        compiler.add_plc_report.assert_called_once_with("/tmp/plc_auto.csv")

    def test_add_page_to_compiler_plc_report_page_csv_overrides_auto(self):
        """_add_page_to_compiler should prefer page's csv_path over plc_csv_path."""
        from schematika.project import _PageDef

        p = Project()
        compiler = MagicMock()

        page_def = _PageDef(page_type="plc_report", csv_path="/explicit/path.csv")
        p._add_page_to_compiler(
            compiler, page_def, {}, {}, "/tmp/system.csv", "/tmp/plc_auto.csv"
        )

        compiler.add_plc_report.assert_called_once_with("/explicit/path.csv")


class TestReservePins:
    def test_reserves_pins_and_creates_bridge_group(self):
        t = Terminal("X13", "Test IO")
        p = Project()
        p.terminals(t)
        p.reserve_pins("estop", t, count=2)
        p.build_circuits()

        result = p._results["estop"]
        assert result.circuit.elements == []
        assert result.circuit.symbols == []
        assert "X13" in result.bridge_groups
        bridges = result.bridge_groups["X13"]
        assert len(bridges) == 1
        start, end = bridges[0]
        assert end - start == 1  # 2 pins reserved

    def test_advances_terminal_counter(self):
        from schematika.electrical.utils.autonumbering import get_terminal_counter

        t = Terminal("X13", "Test IO")
        p = Project()
        p.terminals(t)

        # Build a dummy circuit that uses X13 pin 1
        def use_one_pin(state):
            from schematika.electrical.utils.autonumbering import set_terminal_counter

            state = set_terminal_counter(state, t, 1)
            return BuildResult(state=state, circuit=Circuit(), used_terminals=[])

        p.add_circuit("first", use_one_pin)
        p.reserve_pins("estop", t, count=2)
        p.build_circuits()

        # After reserve_pins, counter should be at 3 (pin 1 used + 2 reserved)
        assert get_terminal_counter(p._state, "X13") == 3


class TestMultiCircuitPage:
    def test_page_accepts_list_of_keys(self):
        p = Project()
        p.page("Combined", ["a", "b"])
        assert len(p._pages) == 1
        assert p._pages[0].circuit_keys == ["a", "b"]

    def test_multi_circuit_page_renders_merged_svg(self):
        def builder_a(state, **_kw):
            c = Circuit()
            return BuildResult(state=state, circuit=c, used_terminals=["X1"])

        def builder_b(state, **_kw):
            c = Circuit()
            return BuildResult(state=state, circuit=c, used_terminals=["X2"])

        p = Project()
        p.add_circuit("a", builder_a)
        p.add_circuit("b", builder_b)
        p.page("Combined", ["a", "b"])

        with tempfile.TemporaryDirectory() as tmpdir:
            p.build_svgs(tmpdir)
            # Individual SVGs should exist
            assert os.path.exists(os.path.join(tmpdir, "a.svg"))
            assert os.path.exists(os.path.join(tmpdir, "b.svg"))
            # Merged SVG should also exist
            assert os.path.exists(os.path.join(tmpdir, "a_b.svg"))

    def test_single_key_still_works(self):
        p = Project()
        p.page("Single", "my_circuit")
        assert p._pages[0].circuit_key == "my_circuit"
        assert p._pages[0].circuit_keys is None


class TestExportWireLabels:
    def test_writes_csv_during_build(self):
        def builder(state, **_kw):
            return BuildResult(
                state=state,
                circuit=Circuit(),
                used_terminals=[],
                wire_connections=[("Q1", "1", "X1", "1")],
            )

        p = Project()
        p.add_circuit("motors", builder)

        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = os.path.join(tmpdir, "wire_labels.csv")
            p.export_wire_labels(csv_path, titles={"motors": "Motor Circuits"})
            p.build_svgs(tmpdir)

            assert os.path.exists(csv_path)
            with open(csv_path) as f:
                content = f.read()
            assert "Motor Circuits" in content
            assert "Q1:1" in content

    def test_skips_circuits_without_wire_connections(self):
        def builder(state, **_kw):
            return BuildResult(state=state, circuit=Circuit(), used_terminals=[])

        p = Project()
        p.add_circuit("empty", builder)

        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = os.path.join(tmpdir, "wire_labels.csv")
            p.export_wire_labels(csv_path)
            p.build_svgs(tmpdir)

            with open(csv_path) as f:
                content = f.read()
            assert content.strip() == ""


class TestExportTaglist:
    def test_writes_sorted_tags(self):
        # _export_taglist only reads device_registry.keys(), so values can be
        # plain sentinels — no need to mock a device.
        def builder(state, **_kw):
            return BuildResult(
                state=state,
                circuit=Circuit(),
                used_terminals=[],
                device_registry={"Q1": object(), "F2": object()},
            )

        t = Terminal("X1", "Test")
        p = Project()
        p.terminals(t)
        p.add_circuit("circuit", builder)

        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = os.path.join(tmpdir, "taglist.csv")
            p.export_taglist(csv_path)
            p.build_svgs(tmpdir)

            with open(csv_path) as f:
                content = f.read()
            assert "Tag" in content  # header
            assert "F2" in content
            assert "Q1" in content
            assert "X1" in content


class TestFieldDevices:
    def test_deferred_resolution(self):
        """field_devices() stores config; build_circuits() resolves it."""
        from schematika.electrical.field_devices import (
            DeviceTemplate,
            FieldDevice,
            PinDef,
        )

        t = Terminal("X03", "Motor Power")
        template = DeviceTemplate(
            mpn="Motor",
            pins=(PinDef("U", terminal=t),),
        )
        device = FieldDevice(tag="M1", template=template)

        p = Project()
        p.terminals(t)
        p.field_devices([device])
        assert p._external_connections == []  # not resolved yet

        # Need at least one circuit so build_circuits works
        p.add_circuit(
            "dummy",
            lambda s, **_kw: BuildResult(state=s, circuit=Circuit(), used_terminals=[]),
        )
        p.build_circuits()

        assert len(p._external_connections) > 0  # now resolved

    def test_external_connections_appends(self):
        """external_connections() appends, not replaces."""
        p = Project()
        row1 = ("A", "1", "X1", "1", "B", "2")
        row2 = ("C", "3", "X2", "3", "D", "4")
        p.external_connections([row1])
        p.external_connections([row2])
        assert len(p._external_connections) == 2

    def test_resolved_connections_property(self):
        p = Project()
        row = ("A", "1", "X1", "1", "B", "2")
        p.external_connections([row])
        assert p.resolved_connections == [row]


class TestBomReport:
    def test_bom_report_registers_page(self):
        p = Project()
        p.bom_report()
        assert len(p._pages) == 1
        assert p._pages[0].page_type == "bom_report"

    def test_aggregate_bom_groups_devices(self):
        from schematika.electrical.internal_device import InternalDevice

        device = InternalDevice(prefix="Q", mpn="ABB-AF09", description="Contactor")

        def builder(state, **_kw):
            return BuildResult(
                state=state,
                circuit=Circuit(),
                used_terminals=[],
                device_registry={"Q1": device, "Q2": device},
            )

        p = Project()
        p.add_circuit("motors", builder)
        p.build_circuits()

        rows = p._aggregate_bom()
        # Should have one row with qty=2 for the contactor
        contactor_rows = [r for r in rows if r[1] == "ABB-AF09"]
        assert len(contactor_rows) == 1
        assert contactor_rows[0][3] == 2  # qty

    def test_aggregate_bom_includes_terminals(self):
        t = Terminal("X1", "Power", description="Terminal block", mpn="3209510")

        p = Project()
        p.terminals(t)
        p.add_circuit(
            "dummy",
            lambda s, **_kw: BuildResult(state=s, circuit=Circuit(), used_terminals=[]),
        )
        p.build_circuits()

        rows = p._aggregate_bom()
        terminal_rows = [r for r in rows if r[1] == "3209510"]
        assert len(terminal_rows) >= 1

    def test_generate_bom_typst_produces_markup(self):
        p = Project()
        rows = [("Q1/Q2", "ABB-AF09", "Contactor", 2)]
        typst = p._generate_bom_typst(rows)
        assert "Bill of Materials" in typst
        assert "ABB-AF09" in typst
        assert "Contactor" in typst
