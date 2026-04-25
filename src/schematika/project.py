"""Project class -- Layer 0 declarative API for Schematika.

The Project is the top-level object that owns state, terminal registry,
circuit definitions, page layout, and output configuration. Users interact
with it declaratively to define an entire schematic drawing set and compile
it to a multi-page PDF.
"""

import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any

from schematika.core.exceptions import CircuitValidationError
from schematika.electrical.builder import BuildResult, CircuitBuilder
from schematika.electrical.builder_models import BridgeMode

if TYPE_CHECKING:
    from schematika.catalog.cables import CableRegistry
    from schematika.catalog.registry import DeviceCatalog
    from schematika.electrical.field_devices import ConnectionRow
    from schematika.electrical.plc_resolver import PlcRack
    from schematika.pcb.model import PCBBuildResult
    from schematika.pid.builder import PIDBuildResult

from schematika.electrical.descriptors import Descriptor, build_from_descriptors
from schematika.electrical.system.connection_registry import (
    export_registry_to_csv,
    get_registry,
)
from schematika.electrical.system.system import render_system
from schematika.electrical.terminal import Terminal
from schematika.electrical.utils.autonumbering import create_autonumberer
from schematika.electrical.utils.export_utils import (
    export_terminal_list,
    finalize_terminal_csv,
)

# ---------------------------------------------------------------------------
# Internal data structures
# ---------------------------------------------------------------------------


@dataclass
class _CircuitDef:
    """Internal deferred circuit definition."""

    key: str
    factory: str  # "descriptors" or "custom"
    params: dict[str, Any] = field(default_factory=dict)
    count: int = 1
    wire_labels: list[str] | None = None
    reuse_tags: dict[str, str] | None = None  # maps prefix -> circuit key
    components: list[Descriptor] | None = None
    builder_fn: Callable | None = None
    start_indices: dict[str, int] | None = None
    terminal_start_indices: dict[str, int] | None = None


@dataclass
class _PageDef:
    """Internal page definition."""

    # page_type values: "schematic", "front", "terminal_report", "plc_report",
    # "custom", "bom_report", "pid", "block", "cable", "cable_toc"
    page_type: str
    title: str = ""
    circuit_key: str = ""
    circuit_keys: list[str] | None = None
    md_path: str = ""
    notice: str | None = None
    csv_path: str = ""
    typst_content: str = ""
    cable_entries: list[tuple[str, str, str, str]] | None = None
    cable_toc_entries: list[tuple[str, str]] | None = None


@dataclass
class _PIDDef:
    """Internal deferred P&ID diagram definition."""

    key: str
    builder_or_factory: Any  # PIDBuilder instance or callable(state) -> PIDBuildResult


@dataclass
class _BlockDiagramDef:
    """Internal deferred block diagram definition."""

    key: str
    builder_or_factory: Any  # BlockDiagram instance (V2) or legacy callable


def _resolve_svg_for_page(
    page_type: str,
    key: str,
    svg_paths: dict[str, str],
    csv_paths: dict[str, str],
    pid_svg_paths: dict[str, str] | None,
    block_svg_paths: dict[str, str] | None,
) -> tuple[str, str | None]:
    """Resolve SVG and CSV paths for a schematic/pid/block page."""
    if page_type == "pid":
        return (pid_svg_paths or {}).get(key, ""), None
    if page_type == "block":
        return (block_svg_paths or {}).get(key, ""), None
    return svg_paths.get(key, ""), csv_paths.get(key)


# ---------------------------------------------------------------------------
# Project class
# ---------------------------------------------------------------------------


class Project:
    """Declarative project builder for electrical schematic drawing sets.

    Project is one of the intentional mutable builder classes in the library.
    It accumulates terminal definitions, circuit registrations, and page
    layouts, then compiles everything to a multi-page PDF via ``.build()``.

    State is threaded automatically between circuits in registration order,
    so terminal pin numbers auto-increment correctly across the drawing set.

    Example::

        project = Project(
            title="My Schematics",
            drawing_number="DWG-001",
            author="Engineer",
            project="Project Name",
        )
        project.terminals(
            Terminal("X1", "Main Power"),
            Terminal("X3", "Fused 24V", bridge=BridgeMode.ALL),
            Terminal("X4", "Ground", bridge=BridgeMode.ALL),
        )
        project.add_circuit("motors", my_builder_fn, count=3)
        project.page("Motor Circuits", "motors")
        project.terminal_report()
        project.build("output.pdf")

    Warning:
        Do not share Project instances across multiple build contexts.
        Each Project should be used for a single ``.build()`` call.

    Args:
        title: Drawing title (appears in title block).
        drawing_number: Drawing number (appears in title block).
        author: Author name.
        project: Project name.
        revision: Revision string (e.g. "00", "A1").
        logo: Path to logo image file (optional).
        font: Font family for all text output.
    """

    def __init__(
        self,
        title: str = "",
        drawing_number: str = "",
        author: str = "",
        project: str = "",
        revision: str = "00",
        logo: str | None = None,
        font: str = "Times New Roman",
    ):
        """Build a ``Project`` with the given title-block metadata."""
        self.title = title
        self.drawing_number = drawing_number
        self.author = author
        self.project = project
        self.revision = revision
        self.logo = logo
        self.font = font

        self._state = create_autonumberer()
        self._terminals: dict[str, Terminal] = {}
        self._circuit_defs: list[_CircuitDef] = []
        self._pages: list[_PageDef] = []
        self._results: dict[str, BuildResult] = {}
        self._plc_rack: PlcRack | None = None
        self._external_connections: list[ConnectionRow] = []
        self._terminal_only_connections: list[ConnectionRow] = []
        self._field_device_defs: list[tuple[list, dict | None, dict | None]] = []
        self._inter_device_defs: list = []
        self._wire_label_export: tuple[str, dict[str, str] | None] | None = None
        self._taglist_export: str | None = None
        self._bom_excel_export: str | None = None
        self._bom_csv_export: str | None = None
        self._catalog: DeviceCatalog | None = None
        self._cable_registry: CableRegistry | None = None
        self._pid_defs: list[_PIDDef] = []
        self._pid_results: dict[str, PIDBuildResult] = {}
        self._block_defs: list[_BlockDiagramDef] = []
        self._block_results: dict[str, Any] = {}  # BlockDiagram instances

    # ------------------------------------------------------------------
    # Terminal registration
    # ------------------------------------------------------------------

    def terminals(self, *terminals: Terminal):
        """Register terminal block definitions for this project.

        Terminals carry metadata (description, bridge info, reference flag)
        used for reports and auto-generation. Must be called before
        registering circuits that reference these terminals.

        Args:
            *terminals: One or more ``Terminal`` instances.
        """
        for t in terminals:
            self._terminals[str(t)] = t

    @property
    def _terminal_descriptions(self) -> dict[str, str]:
        return {tag: t.title for tag, t in self._terminals.items() if t.title}

    def set_pin_start(self, terminal_id: str, pin: int) -> None:
        """Seed the pin counter for a terminal so auto-allocation starts at *pin*.

        Also updates per-prefix counters for this terminal so that
        prefixed allocations respect the new floor.

        Args:
            terminal_id: Terminal tag (e.g. "X1").
            pin: Starting pin number (subsequent auto-allocations will
                begin at ``pin + 1``).
        """
        tag_key = str(terminal_id)

        new_counters = {**self._state.terminal_counters, tag_key: pin}

        prefix_counters = self._state.terminal_prefix_counters
        if tag_key in prefix_counters:
            new_tag_prefixes = prefix_counters[tag_key].copy()
            for p in new_tag_prefixes:
                new_tag_prefixes[p] = pin
            new_prefix_counters = {**prefix_counters, tag_key: new_tag_prefixes}
        else:
            new_prefix_counters = prefix_counters

        self._state = replace(
            self._state,
            terminal_counters=new_counters,
            terminal_prefix_counters=new_prefix_counters,
        )

    # ------------------------------------------------------------------
    # Circuit registration
    # ------------------------------------------------------------------

    def circuit(
        self,
        key: str,
        components: list[Descriptor],
        count: int = 1,
        wire_labels: list[str] | None = None,
        reuse_tags: dict[str, str] | None = None,
        start_indices: dict[str, int] | None = None,
        terminal_start_indices: dict[str, int] | None = None,
        **kwargs,
    ):
        """Register a custom inline circuit from descriptors.

        Args:
            key: Unique circuit identifier.
            components: List of ref(), comp(), term() descriptors.
            count: Number of instances.
            wire_labels: Wire label strings.
            reuse_tags: Maps tag prefix to source circuit key.
            start_indices: Override tag counters.
            terminal_start_indices: Override terminal pin counters.
            **kwargs: Additional keyword arguments forwarded to the descriptor builder.
        """
        self._circuit_defs.append(
            _CircuitDef(
                key=key,
                factory="descriptors",
                count=count,
                wire_labels=wire_labels,
                reuse_tags=reuse_tags,
                components=components,
                params=kwargs,
                start_indices=start_indices,
                terminal_start_indices=terminal_start_indices,
            )
        )

    def add_circuit(self, key: str, builder_fn: Callable, count: int = 1, **kwargs):
        """Register a custom circuit built via a builder function.

        The function receives ``(state, **kwargs)`` and must return
        a ``BuildResult`` (or a tuple ``(state, circuit, used_terminals)``).

        Example::

            from schematika import Project

            def my_circuit(state):
                builder = CircuitBuilder(state)
                tm = builder.add_terminal("X1", poles=1)
                return builder.build()

            project = Project(name="example")
            project.add_circuit("my_circuit", my_circuit, count=3)
            project.add_page("my_circuit", title="My Circuit")
        """
        self._circuit_defs.append(
            _CircuitDef(
                key=key,
                factory="custom",
                count=count,
                builder_fn=builder_fn,
                params=kwargs,
            )
        )

    def reserve_pins(self, key: str, terminal: "Terminal", count: int) -> "Project":
        """Reserve terminal pins with a bridge group (e.g., emergency stop).

        Registers a deferred circuit that advances the pin counter by *count*
        and creates a bridge group spanning those pins.  The circuit itself
        is empty (no visual elements).

        Args:
            key: Unique circuit identifier for this reservation.
            terminal: Terminal to reserve pins on.
            count: Number of sequential pins to reserve.

        Returns:
            self (for method chaining).
        """

        def _reserve_fn(state, **_kwargs):
            from schematika.electrical.system.system import Circuit
            from schematika.electrical.utils.autonumbering import (
                get_terminal_counter,
                set_terminal_counter,
            )

            tag = str(terminal)
            start = get_terminal_counter(state, tag) + 1
            end = start + count - 1
            state = set_terminal_counter(state, terminal, end)
            return BuildResult(
                state=state,
                circuit=Circuit(),
                used_terminals=[],
                bridge_groups={tag: [(start, end)]},
            )

        self._circuit_defs.append(
            _CircuitDef(key=key, factory="custom", builder_fn=_reserve_fn)
        )
        return self

    # ------------------------------------------------------------------
    # Catalog and P&ID registration
    # ------------------------------------------------------------------

    def set_catalog(self, catalog: "DeviceCatalog") -> "Project":
        """Store a device catalog for cross-referencing between P&ID and electrical.

        Args:
            catalog: A :class:`~schematika.catalog.registry.DeviceCatalog` instance.

        Returns:
            self (for method chaining).
        """
        self._catalog = catalog
        return self

    @property
    def catalog(self) -> "DeviceCatalog | None":
        """The registered device catalog, or None if not set."""
        return self._catalog

    def add_pid(self, key: str, builder_or_factory: Any) -> "Project":
        """Register a P&ID diagram definition (deferred, like ``add_circuit()``).

        The diagram is built lazily when ``build()`` is called.  State is
        shared with electrical circuits so tag counters are consistent
        across the whole drawing set.

        Args:
            key: Unique diagram identifier (used as key in results and for
                SVG filenames).
            builder_or_factory: Either:

                - A :class:`~schematika.pid.builder.PIDBuilder` instance
                  (already configured but not yet built), **or**
                - A callable ``(state: GenerationState) -> PIDBuildResult``.

        Returns:
            self (for method chaining).
        """
        self._pid_defs.append(_PIDDef(key=key, builder_or_factory=builder_or_factory))
        return self

    def pid_page(self, title: str, diagram_key: str) -> "Project":
        """Add a P&ID diagram page to the drawing set.

        Works alongside :meth:`page` for electrical schematic pages.
        The diagram must have been registered via :meth:`add_pid` using
        the same *diagram_key*.

        Args:
            title: Page title displayed in the title block.
            diagram_key: Key of the registered P&ID diagram to render.

        Returns:
            self (for method chaining).
        """
        self._pages.append(
            _PageDef(page_type="pid", title=title, circuit_key=diagram_key)
        )
        return self

    # ------------------------------------------------------------------
    # Cable registry
    # ------------------------------------------------------------------

    def set_cable_registry(self, registry: "CableRegistry") -> "Project":
        """Store a cable registry for cross-referencing across all modules.

        Args:
            registry: A :class:`~schematika.catalog.cables.CableRegistry` instance.

        Returns:
            self (for method chaining).
        """
        self._cable_registry = registry
        return self

    @property
    def cable_registry(self) -> "CableRegistry | None":
        """The registered cable registry, or None if not set."""
        return self._cable_registry

    # ------------------------------------------------------------------
    # Block diagram registration
    # ------------------------------------------------------------------

    def add_pcb(self, result: "PCBBuildResult") -> "Project":
        """Register every column and page from a :class:`PCBBuildResult`.

        Each column in ``result.columns`` is registered as a circuit under its
        key; each ``(title, [key, ...])`` entry in ``result.pages`` becomes a
        multi-circuit page.

        Args:
            result: The ``PCBBuildResult`` returned by ``schematika.pcb.build``.

        Returns:
            self (for method chaining).
        """
        from schematika.electrical.builder_models import BuildResult
        from schematika.electrical.system.system import Circuit

        def _wrap(circuit: Circuit) -> Callable[..., BuildResult]:
            return lambda state, c=circuit: BuildResult(
                state=state, circuit=c, used_terminals=[]
            )

        for key, circuit in result.columns:
            self.add_circuit(key, builder_fn=_wrap(circuit))
        for title, col_keys in result.pages:
            self.page(title, list(col_keys))
        return self

    def add_block_diagram(self, key: str, builder_or_factory: Any) -> "Project":
        """Register a block diagram.

        Accepts a :class:`~schematika.block.diagram.BlockDiagram` instance
        directly (V2 API). The diagram renders itself when SVGs are produced.

        Args:
            key: Unique diagram identifier.
            builder_or_factory: A ``BlockDiagram`` instance.

        Returns:
            self (for method chaining).
        """
        self._block_defs.append(
            _BlockDiagramDef(key=key, builder_or_factory=builder_or_factory)
        )
        return self

    def block_page(self, title: str, diagram_key: str) -> "Project":
        """Add a block diagram page to the drawing set.

        The diagram must have been registered via :meth:`add_block_diagram`
        using the same *diagram_key*.

        Args:
            title: Page title displayed in the title block.
            diagram_key: Key of the registered block diagram to render.

        Returns:
            self (for method chaining).
        """
        self._pages.append(
            _PageDef(page_type="block", title=title, circuit_key=diagram_key)
        )
        return self

    # ------------------------------------------------------------------
    # PLC rack and external connections
    # ------------------------------------------------------------------

    def plc_rack(self, rack: "PlcRack") -> "Project":
        """Register a PLC rack for automatic PLC connection report generation.

        When a rack is registered, ``.build()`` will automatically generate
        the PLC connections CSV from the circuit registry and any registered
        external connections.

        Args:
            rack: List of (designation, PlcModuleType) tuples describing
                the physical PLC rack.

        Returns:
            self (for method chaining).
        """
        self._plc_rack = rack
        return self

    def external_connections(self, connections: "list[ConnectionRow]") -> "Project":
        """Register external field wiring connections for the PLC report.

        These are connections from field devices (sensors, valves, motors)
        entering the cabinet. They are resolved against the PLC rack to
        generate the PLC connection report.

        Args:
            connections: List of ConnectionRow tuples
                (component_from, pin_from, terminal_tag, terminal_pin,
                 component_to, pin_to).

        Returns:
            self (for method chaining).
        """
        self._external_connections.extend(connections)
        return self

    def internal_wiring(self, connections: "list[ConnectionRow]") -> "Project":
        """Register internal terminal-to-terminal connections.

        These connections appear in the terminal report but are excluded
        from cable exports.
        """
        self._terminal_only_connections.extend(connections)
        return self

    def add_field_devices(
        self,
        connections: "list[ConnectionRow]",
        reuse_terminals: dict[str, str] | None = None,
    ) -> "Project":
        """Register external field device connections.

        Alias for ``external_connections()`` with an optional
        ``reuse_terminals`` parameter for future expansion.

        Args:
            connections: List of ``ConnectionRow`` tuples.
            reuse_terminals: Reserved for future use. Currently ignored.

        Returns:
            self (for method chaining).
        """
        self._external_connections.extend(connections)
        return self

    def field_devices(
        self,
        devices: list,
        reuse_terminals: dict | None = None,
        template_reuse: dict | None = None,
    ) -> "Project":
        """Register field devices for deferred connection resolution.

        After build_circuits(), resolves reuse_terminals from built circuit
        results, generates connections via generate_field_connections(),
        and resolves PLC references if a rack is registered.

        Args:
            devices: List of FieldDevice instances.
            reuse_terminals: Maps Terminal -> circuit key string.
                Pins from that circuit's terminal_pin_map are reused.
            template_reuse: Maps DeviceTemplate -> {Terminal: circuit key}.
                Only devices whose template matches will reuse those
                terminal pins; other devices auto-number normally but
                skip the reserved pin values.

        Returns:
            self (for method chaining).
        """
        self._field_device_defs.append((devices, reuse_terminals, template_reuse))
        return self

    def inter_device_cables(self, connections: list) -> "Project":
        """Register direct device-to-device cables (FieldDevice <-> FieldDevice).

        Each ``InterDeviceConnection`` produces one cable page in the PDF,
        appended after any device-to-terminal cables generated by
        ``cable_pages()``.  Devices referenced by ``from_device`` /
        ``to_device`` tags must also be registered via ``field_devices()``
        (the ``EMPTY_TEMPLATE`` sentinel is provided for devices that have
        no terminal wiring).

        Args:
            connections: List of ``InterDeviceConnection`` instances.

        Returns:
            self (for method chaining).
        """
        self._inter_device_defs.extend(connections)
        return self

    # ------------------------------------------------------------------
    # Query properties
    # ------------------------------------------------------------------

    @property
    def device_registry(self) -> dict:
        """Merged device registry from all built circuits."""
        merged: dict = {}
        for result in self._results.values():
            merged.update(result.device_registry)
        return merged

    @property
    def bridge_groups(self) -> dict:
        """Merged bridge groups from all built circuits."""
        merged: dict = {}
        for result in self._results.values():
            for key, groups in result.bridge_groups.items():
                merged.setdefault(key, []).extend(groups)
        return merged

    @property
    def wire_connections(self) -> dict[str, list]:
        """Wire connections grouped by circuit name."""
        return {
            key: result.wire_connections
            for key, result in self._results.items()
            if result.wire_connections
        }

    @property
    def resolved_connections(self) -> list:
        """All resolved external connections (available after build_circuits())."""
        return list(self._external_connections)

    # ------------------------------------------------------------------
    # Page management
    # ------------------------------------------------------------------

    def page(self, title: str, circuit_key: str | list[str]):
        """Add a schematic page to the PDF output.

        Args:
            title: Page title displayed in the title block.
            circuit_key: Key of a registered circuit to render, or a list of
                keys to merge onto a single page.
        """
        if isinstance(circuit_key, list):
            self._pages.append(
                _PageDef(page_type="schematic", title=title, circuit_keys=circuit_key)
            )
        else:
            self._pages.append(
                _PageDef(page_type="schematic", title=title, circuit_key=circuit_key)
            )

    def front_page(self, md_path: str, notice: str | None = None):
        """Add a front page rendered from a Markdown file.

        Args:
            md_path: Path to the Markdown source file.
            notice: Optional notice text displayed on the front page.
        """
        self._pages.append(_PageDef(page_type="front", md_path=md_path, notice=notice))

    def terminal_report(self):
        """Add an auto-generated system terminal report page.

        Includes all registered terminals with bridge/connection info
        and descriptions from ``terminals()``.
        """
        self._pages.append(_PageDef(page_type="terminal_report"))

    def plc_report(self, csv_path: str = "") -> "Project":
        """Add a PLC connections report page.

        When a rack has been registered via ``plc_rack()`` and *csv_path*
        is empty, ``.build()`` will auto-generate the PLC connections CSV
        from the circuit registry and any registered external connections.

        Args:
            csv_path: Path to the PLC connections CSV file.  Leave empty
                when using the auto-generation path via ``plc_rack()``.

        Returns:
            self (for method chaining).
        """
        self._pages.append(_PageDef(page_type="plc_report", csv_path=csv_path))
        return self

    def custom_page(self, title: str, typst_content: str):
        """Add a page with raw Typst markup content.

        Args:
            title: Page title displayed in the title block.
            typst_content: Raw Typst source code for the page body.
        """
        self._pages.append(
            _PageDef(page_type="custom", title=title, typst_content=typst_content)
        )

    def bom_report(self) -> "Project":
        """Add an auto-generated Bill of Materials page."""
        self._pages.append(_PageDef(page_type="bom_report"))
        return self

    def cable_pages(
        self,
        cable_prefix: str = "A-W",
        cable_start: int = 1,
        pins_last: tuple[str, ...] = ("PE",),
        temp_dir: str = "temp",
        toc: bool = True,
    ) -> "Project":
        """Generate cable drawings and add TOC + cable pages to the PDF.

        Auto-extracts cable data from registered field devices and external
        connections, renders each cable to SVG via WireViz, and adds a table
        of contents page followed by flowing two-column cable drawing pages.

        Requires ``build_circuits()`` to have been called first.

        Args:
            cable_prefix: Auto-numbering prefix, e.g. "A-W".
            cable_start: First cable number.
            pins_last: Pin names to reorder to end of each cable.
            temp_dir: Directory for intermediate SVG files.
            toc: When True, prepend a table-of-contents page before the cable pages.

        Returns:
            self (for method chaining).
        """
        from schematika.cable import (
            build_cable_drawings,
            build_inter_device_drawings,
            render_cable_svg,
        )

        # Collect all field devices
        all_devices: list = []
        for devices, _reuse, _template_reuse in self._field_device_defs:
            all_devices.extend(devices)

        # Build cable drawings from field device data
        drawings = build_cable_drawings(
            self._external_connections,
            all_devices,
            cable_prefix=cable_prefix,
            cable_start=cable_start,
            pins_last=pins_last,
        )

        # Append device-to-device cable drawings (separate pages in the PDF),
        # continuing the numbering from where device-to-terminal cables stopped.
        drawings.extend(
            build_inter_device_drawings(
                self._inter_device_defs,
                cable_prefix=cable_prefix,
                cable_start=cable_start + len(drawings),
            )
        )

        # Render each cable to SVG file
        cable_dir = os.path.join(temp_dir, "cables")
        os.makedirs(cable_dir, exist_ok=True)
        cable_entries: list[tuple[str, str, str, str]] = []
        for drawing in drawings:
            svg_content = render_cable_svg(drawing)
            svg_path = os.path.join(cable_dir, f"{drawing.cable.designator}.svg")
            with open(svg_path, "w", encoding="utf-8") as f:
                f.write(svg_content)
            length_str = ""
            if drawing.cable.length:
                length_str = f"{drawing.cable.length:g} m"
            cable_entries.append(
                (svg_path, drawing.cable.designator, drawing.title, length_str)
            )

        # Add TOC page + cable pages (TOC skipped when toc=False)
        if toc:
            toc_entries = [(d.cable.designator, d.title) for d in drawings]
            self._pages.append(
                _PageDef(
                    page_type="cable_toc",
                    title="Table of Contents",
                    cable_toc_entries=toc_entries,
                )
            )
        self._pages.append(
            _PageDef(
                page_type="cable",
                title="Cable Drawings",
                cable_entries=cable_entries,
            )
        )
        return self

    def export_wire_labels(
        self, path: str, titles: dict[str, str] | None = None
    ) -> "Project":
        """Register a wire label CSV export. Written during build()."""
        self._wire_label_export = (path, titles)
        return self

    def export_taglist(self, path: str) -> "Project":
        """Register a taglist CSV export. Written during build()."""
        self._taglist_export = path
        return self

    def export_bom_excel(self, path: str) -> "Project":
        """Register a BOM Excel export. Written during build()."""
        self._bom_excel_export = path
        return self

    def export_bom_csv(self, path: str) -> "Project":
        """Register a BOM CSV export. Written during build()."""
        self._bom_csv_export = path
        return self

    # ------------------------------------------------------------------
    # Build pipeline
    # ------------------------------------------------------------------

    def build_circuits(self) -> None:
        """Build all deferred circuits and resolve field devices."""
        self._build_all_circuits()
        self._resolve_field_devices()

    def build(
        self,
        output: str,
        temp_dir: str = "temp",
        keep_temp: bool = False,
        datetime_stamp: bool = True,
    ):
        """Build all circuits and compile the PDF.

        Steps:
        1. Build all registered circuits (respecting dependencies).
        2. Generate SVG for each circuit.
        3. Generate per-circuit terminal CSV.
        4. Generate system terminal CSV with bridge info.
        5. Assemble and compile Typst -> PDF.

        Args:
            output: Path for the output PDF file.
            temp_dir: Directory for intermediate files.
            keep_temp: If True, keep intermediate files after compilation.
            datetime_stamp: When True, embed a build timestamp in the title block.
        """
        from schematika.rendering.typst.compiler import (
            TypstCompiler,
            TypstCompilerConfig,
        )

        os.makedirs(temp_dir, exist_ok=True)

        # 1. Build all circuits
        self._build_all_circuits()
        self._resolve_field_devices()

        # 2. Generate SVGs and terminal CSVs
        svg_paths = {}
        csv_paths = {}

        for key, result in self._results.items():
            svg_path = os.path.join(temp_dir, f"{key}.svg")
            render_system(result.circuit, svg_path)
            svg_paths[key] = svg_path

            if result.used_terminals:
                csv_path = os.path.join(temp_dir, f"{key}_terminals.csv")
                export_terminal_list(
                    csv_path, result.used_terminals, self._terminal_descriptions
                )
                csv_paths[key] = csv_path

        # 2b. Render P&ID SVGs
        pid_svg_paths = self._render_pid_svgs(temp_dir)

        # 2c. Render block diagram SVGs
        block_svg_paths = self._render_block_svgs(temp_dir)

        self._render_multi_circuit_pages(svg_paths, csv_paths, temp_dir)
        self._export_wire_labels()
        self._export_taglist()
        self._export_bom_excel()
        self._export_bom_csv()

        # 3. Generate system terminal CSV with bridge info
        system_csv_path = self._generate_system_csv(temp_dir)

        # 3.5. Auto-generate PLC connections CSV if rack is configured
        plc_csv_path = ""
        if self._plc_rack is not None:
            plc_csv_path = os.path.join(temp_dir, "plc_connections.csv")
            self._generate_plc_csv(plc_csv_path)

        # 4. Assemble Typst document
        # Use CWD as root so all relative paths (SVGs, CSVs) resolve correctly
        root_dir = os.getcwd()
        config = TypstCompilerConfig(
            drawing_name=self.title,
            drawing_number=self.drawing_number,
            author=self.author,
            project=self.project,
            revision=self.revision,
            logo_path=os.path.abspath(self.logo) if self.logo else None,
            font_family=self.font,
            root_dir=root_dir,
            temp_dir=os.path.relpath(os.path.abspath(temp_dir), root_dir),
            datetime_stamp=datetime_stamp,
        )
        compiler = TypstCompiler(config)

        # Add pages
        for page_def in self._pages:
            self._add_page_to_compiler(
                compiler,
                page_def,
                svg_paths,
                csv_paths,
                system_csv_path,
                plc_csv_path,
                pid_svg_paths=pid_svg_paths,
                block_svg_paths=block_svg_paths,
            )

        # 5. Compile
        compiler.compile(output)

        # Cleanup
        if not keep_temp:
            shutil.rmtree(temp_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # Build SVGs only (no PDF, no typst dependency)
    # ------------------------------------------------------------------

    def build_svgs(self, output_dir: str = "output"):
        """Build all circuits and export SVGs (no PDF compilation).

        Useful when the ``typst`` package is not installed.

        Args:
            output_dir: Directory for output SVG and CSV files.
        """
        os.makedirs(output_dir, exist_ok=True)
        self._build_all_circuits()

        svg_paths: dict[str, str] = {}
        csv_paths: dict[str, str] = {}

        for key, result in self._results.items():
            svg_path = os.path.join(output_dir, f"{key}.svg")
            render_system(result.circuit, svg_path)
            svg_paths[key] = svg_path

            if result.used_terminals:
                csv_path = os.path.join(output_dir, f"{key}_terminals.csv")
                export_terminal_list(
                    csv_path, result.used_terminals, self._terminal_descriptions
                )
                csv_paths[key] = csv_path

        # Render P&ID SVGs
        self._render_pid_svgs(output_dir)

        self._render_multi_circuit_pages(svg_paths, csv_paths, output_dir)
        self._export_wire_labels()
        self._export_taglist()

        # System terminal CSV
        self._generate_system_csv(output_dir)

    # ------------------------------------------------------------------
    # Separate output methods
    # ------------------------------------------------------------------

    def render_svgs(self, output_dir: str) -> None:
        """Render all circuit SVGs and per-circuit terminal CSVs to *output_dir*.

        Unlike ``build_svgs()``, this method does **not** build deferred
        circuits. It only renders results already present in ``_results``
        (populated by ``add_circuit()`` or a prior ``_build_all_circuits()``
        call).

        Args:
            output_dir: Directory for output SVG and CSV files.
        """
        os.makedirs(output_dir, exist_ok=True)

        for key, result in self._results.items():
            svg_path = os.path.join(output_dir, f"{key}.svg")
            render_system(result.circuit, svg_path)

            if result.used_terminals:
                csv_path = os.path.join(output_dir, f"{key}_terminals.csv")
                export_terminal_list(
                    csv_path, result.used_terminals, self._terminal_descriptions
                )

        if self._pid_defs:
            self._render_pid_svgs(output_dir)

    def export_csvs(self, output_dir: str) -> None:
        """Export system terminal CSV with bridge info to *output_dir*.

        Also generates the PLC connections CSV when a rack has been
        registered via ``plc_rack()``.

        Args:
            output_dir: Directory for output CSV files.
        """
        os.makedirs(output_dir, exist_ok=True)

        # System terminal CSV
        self._generate_system_csv(output_dir)

        # PLC connections CSV
        if self._plc_rack is not None:
            plc_csv_path = os.path.join(output_dir, "plc_connections.csv")
            self._generate_plc_csv(plc_csv_path)

    def compile_pdf(
        self,
        output: str,
        temp_dir: str = "temp",
        keep_temp: bool = False,
        datetime_stamp: bool = True,
    ) -> None:
        """Compile the full PDF using TypstCompiler with the defined page flow.

        This method renders SVGs, exports CSVs, and compiles the Typst
        document into a single PDF. It operates on results already present
        in ``_results`` (populated by ``add_circuit()`` or a prior
        ``_build_all_circuits()`` call).

        Args:
            output: Path for the output PDF file.
            temp_dir: Directory for intermediate files.
            keep_temp: If True, keep intermediate files after compilation.
            datetime_stamp: When True, embed a build timestamp in the title block.
        """
        from schematika.rendering.typst.compiler import (
            TypstCompiler as _TypstCompiler,
        )
        from schematika.rendering.typst.compiler import (
            TypstCompilerConfig,
        )

        os.makedirs(temp_dir, exist_ok=True)

        # Render SVGs and per-circuit terminal CSVs
        svg_paths: dict[str, str] = {}
        csv_paths: dict[str, str] = {}

        for key, result in self._results.items():
            svg_path = os.path.join(temp_dir, f"{key}.svg")
            render_system(result.circuit, svg_path)
            svg_paths[key] = svg_path

            if result.used_terminals:
                csv_path = os.path.join(temp_dir, f"{key}_terminals.csv")
                export_terminal_list(
                    csv_path, result.used_terminals, self._terminal_descriptions
                )
                csv_paths[key] = csv_path

        # Build any P&ID diagrams not yet built (e.g. added after build_circuits())
        for pdef in self._pid_defs:
            if pdef.key not in self._pid_results:
                self._build_all_pids()
                break

        # Build any block diagrams not yet built
        for bdef in self._block_defs:
            if bdef.key not in self._block_results:
                self._build_all_block_diagrams()
                break

        # Render P&ID SVGs
        pid_svg_paths = self._render_pid_svgs(temp_dir)

        # Render block diagram SVGs
        block_svg_paths = self._render_block_svgs(temp_dir)

        self._render_multi_circuit_pages(svg_paths, csv_paths, temp_dir)
        self._export_wire_labels()
        self._export_taglist()

        # System terminal CSV with bridge info
        system_csv_path = self._generate_system_csv(temp_dir)

        # PLC connections CSV
        plc_csv_path = ""
        if self._plc_rack is not None:
            plc_csv_path = os.path.join(temp_dir, "plc_connections.csv")
            self._generate_plc_csv(plc_csv_path)

        # Assemble Typst document
        root_dir = os.getcwd()
        config = TypstCompilerConfig(
            drawing_name=self.title,
            drawing_number=self.drawing_number,
            author=self.author,
            project=self.project,
            revision=self.revision,
            logo_path=os.path.abspath(self.logo) if self.logo else None,
            font_family=self.font,
            root_dir=root_dir,
            temp_dir=os.path.relpath(os.path.abspath(temp_dir), root_dir),
            datetime_stamp=datetime_stamp,
        )
        compiler = _TypstCompiler(config)

        for page_def in self._pages:
            self._add_page_to_compiler(
                compiler,
                page_def,
                svg_paths,
                csv_paths,
                system_csv_path,
                plc_csv_path,
                pid_svg_paths=pid_svg_paths,
                block_svg_paths=block_svg_paths,
            )

        compiler.compile(output)

        if not keep_temp:
            shutil.rmtree(temp_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # Internal: field device resolution
    # ------------------------------------------------------------------

    def _resolve_field_devices(self) -> None:
        """Resolve deferred field device registrations."""
        if not self._field_device_defs:
            return

        from schematika.electrical.field_devices import generate_field_connections

        for devices, reuse_terminals, template_reuse in self._field_device_defs:
            resolved_reuse = self._resolve_terminal_reuse(reuse_terminals)
            resolved_template_reuse = self._resolve_template_reuse(template_reuse)

            connections = generate_field_connections(
                devices,
                reuse_terminals=resolved_reuse,
                template_reuse=resolved_template_reuse,
            )

            if self._plc_rack:
                from schematika.electrical.plc_resolver import resolve_plc_references

                connections = resolve_plc_references(connections, self._plc_rack)

            self._external_connections.extend(connections)

    def _resolve_terminal_reuse(self, reuse_terminals: dict | None) -> dict | None:
        """Resolve terminal reuse dict to built circuit results."""
        if not reuse_terminals:
            return None
        resolved: dict = {}
        for terminal, circuit_key in reuse_terminals.items():
            if circuit_key not in self._results:
                raise CircuitValidationError(
                    f"field_devices() references circuit '{circuit_key}' "
                    f"for terminal reuse, but it hasn't been built yet."
                )
            resolved[str(terminal)] = self._results[circuit_key]
        return resolved

    def _resolve_template_reuse(self, template_reuse: dict | None) -> dict | None:
        """Resolve template reuse dict to built circuit results."""
        if not template_reuse:
            return None
        resolved: dict = {}
        for tmpl, terminal_map in template_reuse.items():
            resolved[tmpl] = {}
            for terminal, circuit_key in terminal_map.items():
                if circuit_key not in self._results:
                    raise CircuitValidationError(
                        f"field_devices() template_reuse references "
                        f"circuit '{circuit_key}', but it hasn't "
                        f"been built yet."
                    )
                resolved[tmpl][str(terminal)] = self._results[circuit_key]
        return resolved

    # ------------------------------------------------------------------
    # Internal: circuit building
    # ------------------------------------------------------------------

    def _build_all_circuits(self):
        """Build all registered circuits and P&ID diagrams in order."""
        self._results = {}
        for cdef in self._circuit_defs:
            result = self._build_one_circuit(cdef)
            self._results[cdef.key] = result
            self._state = result.state
        self._build_all_pids()
        self._build_all_block_diagrams()

    def _build_all_pids(self) -> None:
        """Build all registered P&ID diagram definitions in order."""
        from schematika.pid.builder import PIDBuilder

        self._pid_results = {}
        for pdef in self._pid_defs:
            builder_or_factory = pdef.builder_or_factory
            if isinstance(builder_or_factory, PIDBuilder):
                result = builder_or_factory.build(state=self._state)
            elif callable(builder_or_factory):
                result = builder_or_factory(self._state)
            else:
                raise TypeError(
                    f"add_pid('{pdef.key}'): builder_or_factory must be a "
                    f"PIDBuilder instance or a callable, got "
                    f"{type(builder_or_factory).__name__}"
                )
            self._pid_results[pdef.key] = result
            self._state = result.state

    def _render_pid_svgs(self, output_dir: str) -> dict[str, str]:
        """Render all built P&ID diagrams to SVG files.

        Returns a mapping of diagram key -> SVG file path.
        """
        from schematika.pid.diagram import render_pid

        pid_svg_paths: dict[str, str] = {}
        for key, result in self._pid_results.items():
            svg_path = os.path.join(output_dir, f"pid_{key}.svg")
            render_pid(result.diagram, svg_path)
            pid_svg_paths[key] = svg_path
        return pid_svg_paths

    def _build_all_block_diagrams(self) -> None:
        """Store all registered block diagrams (V2 diagrams need no build step)."""
        from schematika.block.diagram import BlockDiagram

        self._block_results = {}
        for bdef in self._block_defs:
            diagram = bdef.builder_or_factory
            if isinstance(diagram, BlockDiagram):
                self._block_results[bdef.key] = diagram
            else:
                raise TypeError(
                    f"add_block_diagram('{bdef.key}'): expected BlockDiagram, "
                    f"got {type(diagram).__name__}"
                )

    def _render_block_svgs(self, output_dir: str) -> dict[str, str]:
        """Render all block diagrams to SVG files.

        Returns a mapping of diagram key -> SVG file path.
        """
        block_svg_paths: dict[str, str] = {}
        for key, diagram in self._block_results.items():
            svg_path = os.path.join(output_dir, f"block_{key}.svg")
            diagram.render(svg_path)
            block_svg_paths[key] = svg_path
        return block_svg_paths

    def _build_one_circuit(self, cdef: _CircuitDef) -> BuildResult:
        """Build a single circuit definition."""
        # Resolve reuse_tags: map circuit key -> BuildResult
        resolved_reuse = None
        if cdef.reuse_tags:
            resolved_reuse = {}
            for prefix, source_key in cdef.reuse_tags.items():
                if source_key not in self._results:
                    raise CircuitValidationError(
                        f"Circuit '{cdef.key}' references '{source_key}' via "
                        f"reuse_tags, but it hasn't been built yet. "
                        f"Register '{source_key}' before '{cdef.key}'."
                    )
                resolved_reuse[prefix] = self._results[source_key]

        if cdef.factory == "descriptors":
            return self._build_descriptor_circuit(cdef, resolved_reuse)
        if cdef.factory == "custom":
            return self._build_custom_circuit(cdef)
        raise CircuitValidationError(
            f"Unknown circuit factory '{cdef.factory}'. Use 'descriptors' or 'custom'."
        )

    def _build_descriptor_circuit(
        self, cdef: _CircuitDef, resolved_reuse: dict | None
    ) -> BuildResult:
        """Build a circuit from inline descriptors."""
        if cdef.components is None:
            raise CircuitValidationError(
                f"Circuit '{cdef.key}' uses descriptor mode but has no "
                f"components defined"
            )
        return build_from_descriptors(
            self._state,
            cdef.components,
            x=cdef.params.get("x", 0.0),
            y=cdef.params.get("y", 0.0),
            spacing=cdef.params.get("spacing", 80.0),
            count=cdef.count,
            wire_labels=cdef.wire_labels,
            reuse_tags=resolved_reuse,
            start_indices=cdef.start_indices,
            terminal_start_indices=cdef.terminal_start_indices,
        )

    def _build_custom_circuit(self, cdef: _CircuitDef) -> BuildResult:
        """Build a circuit via user-provided builder function."""
        if cdef.builder_fn is None:
            raise CircuitValidationError(
                f"Circuit '{cdef.key}' uses custom mode but has no builder_fn defined"
            )
        result = cdef.builder_fn(self._state, **cdef.params)
        if isinstance(result, BuildResult):
            return result
        # Support frozen CircuitBuilder return
        if isinstance(result, CircuitBuilder) and result._frozen:
            return result._result
        # Support tuple return: (state, circuit, used_terminals)
        state, circuit, used_terminals = result
        return BuildResult(
            state=state,
            circuit=circuit,
            used_terminals=used_terminals,
        )

    def _render_multi_circuit_pages(self, svg_paths, csv_paths, output_dir):
        """Render merged SVGs for multi-circuit pages."""
        from schematika.electrical.builder import merge_build_results

        for page_def in self._pages:
            if page_def.circuit_keys:
                results_to_merge = [
                    self._results[k]
                    for k in page_def.circuit_keys
                    if k in self._results
                ]
                if results_to_merge:
                    merged = merge_build_results(results_to_merge)
                    merged_key = "_".join(page_def.circuit_keys)
                    svg_path = os.path.join(output_dir, f"{merged_key}.svg")
                    render_system(merged.circuit, svg_path)
                    svg_paths[merged_key] = svg_path
                    if merged.used_terminals:
                        csv_path_m = os.path.join(
                            output_dir, f"{merged_key}_terminals.csv"
                        )
                        export_terminal_list(
                            csv_path_m,
                            merged.used_terminals,
                            self._terminal_descriptions,
                        )
                        csv_paths[merged_key] = csv_path_m
                    # Point page_def to merged key for compiler
                    page_def.circuit_key = merged_key

    # ------------------------------------------------------------------
    # Internal: wire label and taglist exports
    # ------------------------------------------------------------------

    def _export_wire_labels(self) -> None:
        if self._wire_label_export is None:
            return
        import csv as _csv

        path, titles = self._wire_label_export
        titles = titles or {}
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", newline="") as f:
            writer = _csv.writer(f)
            for circuit_key, result in self._results.items():
                if not result.wire_connections:
                    continue
                title = titles.get(circuit_key, circuit_key)
                writer.writerow([title])
                for tag_a, pin_a, tag_b, pin_b in result.wire_connections:
                    writer.writerow([f"{tag_a}:{pin_a}"])
                    writer.writerow([f"{tag_b}:{pin_b}"])
                writer.writerow([])

    def _export_taglist(self) -> None:
        if self._taglist_export is None:
            return
        import csv as _csv

        from schematika.core.utils import natural_sort_key

        tags: set[str] = set()
        for result in self._results.values():
            tags.update(result.device_registry.keys())
        for tid in self._terminals:
            tags.add(tid)
        if self._plc_rack:
            for slot_name, _module in self._plc_rack:
                tags.add(slot_name)

        os.makedirs(
            os.path.dirname(os.path.abspath(self._taglist_export)), exist_ok=True
        )
        with open(self._taglist_export, "w", newline="") as f:
            writer = _csv.writer(f)
            writer.writerow(["Tag"])
            for tag in sorted(tags, key=natural_sort_key):
                writer.writerow([tag])

    def _export_bom_excel(self) -> None:
        if self._bom_excel_export is None:
            return
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill

        rows = self._aggregate_bom()
        wb = Workbook()
        ws = wb.active
        ws.title = "BOM"

        headers = ["Tags", "MPN", "Description", "Qty"]
        header_font = Font(bold=True)
        header_fill = PatternFill(
            start_color="D9D9D9", end_color="D9D9D9", fill_type="solid"
        )
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="left")

        for row_idx, (tags, mpn, desc, qty) in enumerate(rows, 2):
            ws.cell(row=row_idx, column=1, value=tags)
            ws.cell(row=row_idx, column=2, value=mpn)
            ws.cell(row=row_idx, column=3, value=desc)
            ws.cell(row=row_idx, column=4, value=qty).alignment = Alignment(
                horizontal="right"
            )

        ws.column_dimensions["A"].width = 30
        ws.column_dimensions["B"].width = 20
        ws.column_dimensions["C"].width = 40
        ws.column_dimensions["D"].width = 8

        path = self._bom_excel_export
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        wb.save(path)

    def _export_bom_csv(self) -> None:
        if self._bom_csv_export is None:
            return
        import csv

        rows = self._aggregate_bom()
        path = self._bom_csv_export
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Tags", "MPN", "Description", "Qty"])
            for tags, mpn, desc, qty in rows:
                writer.writerow([tags, mpn, desc, qty])

    # ------------------------------------------------------------------
    # Internal: system CSV generation
    # ------------------------------------------------------------------

    def _generate_system_csv(self, output_dir: str) -> str:
        """Generate system terminal CSV with bridge info and external connections.

        PLC-prefixed connections are filtered out (they appear in the
        PLC report instead).
        """
        from schematika.electrical.system.connection_registry import TerminalRegistry

        csv_path = os.path.join(output_dir, "system_terminals.csv")
        registry = get_registry(self._state)
        filtered = tuple(
            c for c in registry.connections if not c.terminal_tag.startswith("PLC:")
        )
        registry = TerminalRegistry(connections=filtered)
        export_registry_to_csv(registry, csv_path, state=self._state)

        # Bridge defs from Terminal objects
        bridge_defs: dict = {}
        prefix_bridge_tags: set[str] = set()
        for tid, t in self._terminals.items():
            if t.bridge and not t.reference:
                if t.bridge == BridgeMode.PER_PREFIX:
                    prefix_bridge_tags.add(tid)
                else:
                    bridge_defs[tid] = t.bridge

        # Bridge groups from circuit results
        for result in self._results.values():
            for key, groups in result.bridge_groups.items():
                bridge_defs.setdefault(key, []).extend(groups)

        finalize_terminal_csv(
            csv_path,
            bridge_defs=bridge_defs or None,
            prefix_bridge_tags=prefix_bridge_tags or None,
            external_connections=(
                self._external_connections + self._terminal_only_connections
            )
            or None,
        )
        return csv_path

    # ------------------------------------------------------------------
    # Internal: BOM aggregation
    # ------------------------------------------------------------------

    def _count_terminal_pins(self) -> dict[str, int]:
        """Count unique pins per terminal from all connection sources."""
        pin_sets: dict[str, set] = {}
        for conn in get_registry(self._state).connections:
            pin_sets.setdefault(conn.terminal_tag, set()).add(conn.terminal_pin)
        for row in self._external_connections:
            tag, pin = str(row[2]), row[3]
            if tag and pin:
                pin_sets.setdefault(tag, set()).add(pin)
        for row in self._terminal_only_connections:
            tag, pin = str(row[2]), row[3]
            if tag and pin:
                pin_sets.setdefault(tag, set()).add(pin)
        return {k: len(v) for k, v in pin_sets.items()}

    def _aggregate_bom(self) -> list[tuple[str, str, str, int]]:
        """Aggregate BOM from device registries, terminals, and PLC modules."""
        from schematika.core.utils import natural_sort_key

        terminal_pin_counts = self._count_terminal_pins()

        # Devices
        device_groups: dict[tuple[str, str], list[str]] = {}
        for result in self._results.values():
            for tag, device in result.device_registry.items():
                key = (device.mpn, device.description)
                device_groups.setdefault(key, []).append(tag)

        rows: list[tuple[str, str, str, int]] = []
        for (mpn, desc), tags in sorted(device_groups.items()):
            unique_tags = sorted(set(tags), key=natural_sort_key)
            rows.append(("/".join(unique_tags), mpn, desc, len(unique_tags)))

        # Terminals
        terminal_groups: dict[tuple[str, str], list[tuple[str, int]]] = {}
        for tid, t in self._terminals.items():
            if not t.reference and t.mpn:
                key = (t.mpn, t.description)
                pin_count = terminal_pin_counts.get(tid, 0)
                terminal_groups.setdefault(key, []).append((tid, pin_count))

        for (mpn, desc), entries in sorted(terminal_groups.items()):
            tags = sorted([e[0] for e in entries], key=natural_sort_key)
            total_pins = sum(e[1] for e in entries)
            rows.append(("/".join(tags), mpn, desc, total_pins))

        # PLC modules
        if self._plc_rack:
            plc_groups: dict[str, list[str]] = {}
            plc_desc: dict[str, str] = {}
            for slot_name, module in self._plc_rack:
                plc_groups.setdefault(module.mpn, []).append(slot_name)
                plc_desc[module.mpn] = (
                    f"PLC {module.signal_type} module ({module.channels}ch)"
                )
            for mpn, slots in sorted(plc_groups.items()):
                sorted_slots = sorted(slots, key=natural_sort_key)
                rows.append(
                    ("/".join(sorted_slots), mpn, plc_desc[mpn], len(sorted_slots))
                )

        return rows

    def _generate_bom_typst(self, bom_rows: list[tuple[str, str, str, int]]) -> str:
        """Generate Typst markup for BOM table."""
        lines = [
            "#place(bottom + center, dy: -title_offset)[",
            '  #text(size: 18pt, weight: "bold")[Bill of Materials]',
            "]",
            "#pad(left: 25mm, right: 25mm, top: 40mm, bottom: 40mm)[",
            "  #columns(2, gutter: 30em)[",
            "    #block(breakable: true)[",
            "      #table(",
            "        columns: (4.5cm, 3.5cm, 1fr, 1cm),",
            "        align: (left, left, left, right),",
            "        fill: (x, y) => if y == 0 { gray.lighten(85%) } else { none },",
            "        inset: 4pt,",
            "        stroke: 0.25pt + gray,",
            "        table.header(",
            '          text(size: 9pt, weight: "bold")[Tags],',
            '          text(size: 9pt, weight: "bold")[MPN],',
            '          text(size: 9pt, weight: "bold")[Description],',
            '          text(size: 9pt, weight: "bold")[Qty],',
            "        ),",
        ]
        for tags, mpn, desc, qty in bom_rows:
            tags_esc = tags.replace("#", "\\#")
            mpn_esc = mpn.replace("#", "\\#")
            desc_esc = desc.replace("#", "\\#")
            lines.append(
                f"        text(size: 9pt)[{tags_esc}], "
                f"text(size: 9pt)[{mpn_esc}], "
                f"text(size: 9pt)[{desc_esc}], "
                f"text(size: 9pt)[{qty}],"
            )
        lines.append("      )")
        lines.append("    ]")
        lines.append("  ]")
        lines.append("]")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal: page compilation
    # ------------------------------------------------------------------

    def _add_page_to_compiler(
        self,
        compiler: Any,
        page_def: _PageDef,
        svg_paths: dict[str, str],
        csv_paths: dict[str, str],
        system_csv_path: str,
        plc_csv_path: str = "",
        pid_svg_paths: dict[str, str] | None = None,
        block_svg_paths: dict[str, str] | None = None,
    ):
        """Add a page definition to the TypstCompiler."""
        if page_def.page_type in ("schematic", "pid", "block"):
            key = page_def.circuit_key
            svg_path, csv_path = _resolve_svg_for_page(
                page_def.page_type,
                key,
                svg_paths,
                csv_paths,
                pid_svg_paths,
                block_svg_paths,
            )
            if svg_path:
                compiler.add_schematic_page(page_def.title, svg_path, csv_path)
        elif page_def.page_type == "front":
            compiler.add_front_page(page_def.md_path, notice=page_def.notice)
        elif page_def.page_type == "terminal_report":
            titles = {
                str(t): t.title for t in self._terminals.values() if not t.reference
            }
            compiler.add_terminal_report(system_csv_path, titles)
        elif page_def.page_type == "plc_report":
            csv_path = page_def.csv_path or plc_csv_path
            if csv_path:
                compiler.add_plc_report(csv_path)
        elif page_def.page_type == "custom":
            compiler.add_custom_page(page_def.title, page_def.typst_content)
        elif page_def.page_type == "bom_report":
            bom_rows = self._aggregate_bom()
            typst_content = self._generate_bom_typst(bom_rows)
            compiler.add_custom_page("Bill of Materials", typst_content)
        elif page_def.page_type == "cable":
            if page_def.cable_entries:
                compiler.add_cable_pages(page_def.cable_entries)
        elif page_def.page_type == "cable_toc":
            if page_def.cable_toc_entries:
                compiler.add_cable_toc(page_def.cable_toc_entries)

    # ------------------------------------------------------------------
    # Internal: PLC CSV generation
    # ------------------------------------------------------------------

    def _generate_plc_csv(self, csv_path: str) -> None:
        """Generate PLC connections CSV from registry and external connections."""
        import csv as _csv

        from schematika.electrical.plc_resolver import (
            extract_plc_connections_from_registry,
            generate_plc_report_rows,
            resolve_plc_references,
        )

        # _generate_plc_csv is only called when _plc_rack is not None
        rack = self._plc_rack
        assert rack is not None  # noqa: S101 — _generate_plc_csv is only called when _plc_rack is not None

        # Resolve external connections if any
        external = list(self._external_connections)
        if external:
            external = resolve_plc_references(external, rack)

        # Extract registry connections
        registry_connections: list[ConnectionRow] = (
            extract_plc_connections_from_registry(self._state, rack, external)
        )

        # Merge and generate rows
        all_connections = external + registry_connections
        rows = generate_plc_report_rows(all_connections, rack)

        with open(csv_path, "w", newline="") as f:
            writer = _csv.writer(f)
            writer.writerow(
                ["Module", "MPN", "PLC Pin", "Component", "Pin", "Terminal"]
            )
            writer.writerows(rows)
