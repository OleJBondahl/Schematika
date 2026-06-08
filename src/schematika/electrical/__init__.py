"""Schematika Electrical — IEC 60617 electrical schematic diagram API."""

# system.system must be imported first — pre-loads layout.layout, breaking the
# circular import chain that would otherwise form via builder.py → layout.layout.
from .system.system import Circuit, merge_circuits, render_system
from .layout.layout import draw_wire
from .layout.wire_labels import add_wire_labels_to_circuit
from .builder import (
    BuildResult,
    CircuitBuilder,
    merge_build_results,
)
from .builder_models import BridgeMode
from .exceptions import (
    CircuitValidationError,
    ComponentNotFoundError,
    PortNotFoundError,
    TagReuseError,
    TerminalReuseError,
    WireLabelMismatchError,
)

# Internal device metadata
from .internal_device import InternalDevice
from .field_devices import (
    CableData,
    ConnectionRow,
    ConnectorData,
    DeviceCable,
    DeviceTemplate,
    FieldDevice,
    PinDef,
    generate_field_connections,
)
from .model.constants import (
    CIRCUIT_SPACING,
    CIRCUIT_SPACING_NARROW,
    CIRCUIT_SPACING_WIDE,
    DEFAULT_POLE_SPACING,
    GRID_SIZE,
    PinPrefix,
    SPACING_COMPACT,
    SPACING_DEFAULT,
    SPACING_NARROW,
    SPACING_STANDARD,
    StandardTags,
    THERMAL_OVERLOAD_PINS,
    WireLabels,
)
from .model.state import GenerationState, create_initial_state
from .plc_resolver import (
    PlcModuleType,
    PlcRack,
    extract_plc_connections_from_registry,
    generate_plc_report_rows,
    resolve_plc_references,
)
from .harness import (
    Harness,
    HarnessBuildResult,
    Plc,
    PlcAssignment,
)
from .terminal_emit import panel_terminal_emit, terminal_csv_rows
from .terminal_sidecar import TerminalSidecar, TerminalWireFact
from .plc_report import plc_csv_rows
from .system.connection_registry import log_connection
from .terminal import Terminal
from .utils.autonumbering import create_autonumberer
from .utils.utils import apply_start_indices, set_terminal_counter

# Symbol factories
from . import symbols
from .symbols import (
    block,
    breaker,
    coil,
    connector_pin,
    contactor,
    ct,
    ct_assembly,
    estop,
    estop_button,
    fuse,
    motor,
    nc_contact,
    no_contact,
    psu,
    ref as ref_symbol,
    spdt_contact,
    terminal,
    terminal_box,
    thermal_overload,
    turn_actuator,
    turn_switch,
)

__all__ = [  # noqa: RUF022
    # Core builder + render
    "Circuit",
    "CircuitBuilder",
    "BuildResult",
    "BridgeMode",
    "merge_circuits",
    "merge_build_results",
    "render_system",
    "draw_wire",
    "add_wire_labels_to_circuit",
    "log_connection",
    # Symbol factories
    "symbols",
    "block",
    "breaker",
    "coil",
    "connector_pin",
    "contactor",
    "ct",
    "ct_assembly",
    "estop",
    "estop_button",
    "fuse",
    "motor",
    "nc_contact",
    "no_contact",
    "psu",
    "ref_symbol",
    "spdt_contact",
    "terminal",
    "terminal_box",
    "thermal_overload",
    "turn_actuator",
    "turn_switch",
    # Layout constants
    "CIRCUIT_SPACING",
    "CIRCUIT_SPACING_NARROW",
    "CIRCUIT_SPACING_WIDE",
    "DEFAULT_POLE_SPACING",
    "GRID_SIZE",
    "SPACING_COMPACT",
    "SPACING_DEFAULT",
    "SPACING_NARROW",
    "SPACING_STANDARD",
    "THERMAL_OVERLOAD_PINS",
    # Tag/wire conventions
    "PinPrefix",
    "StandardTags",
    "WireLabels",
    # State
    "GenerationState",
    "create_initial_state",
    # Autonumbering + counters
    "create_autonumberer",
    "apply_start_indices",
    "set_terminal_counter",
    # Field-device data model
    "InternalDevice",
    "Terminal",
    "CableData",
    "ConnectionRow",
    "ConnectorData",
    "DeviceCable",
    "DeviceTemplate",
    "FieldDevice",
    "PinDef",
    # Field-device generators
    "generate_field_connections",
    # Terminal CSV emit (native Wire+sidecar path)
    "TerminalSidecar",
    "TerminalWireFact",
    "panel_terminal_emit",
    "terminal_csv_rows",
    # PLC resolver
    "PlcModuleType",
    "PlcRack",
    "extract_plc_connections_from_registry",
    "generate_plc_report_rows",
    "plc_csv_rows",
    "resolve_plc_references",
    # Harness builder
    "Harness",
    "HarnessBuildResult",
    "Plc",
    "PlcAssignment",
    # Exception contract
    "CircuitValidationError",
    "ComponentNotFoundError",
    "PortNotFoundError",
    "TagReuseError",
    "TerminalReuseError",
    "WireLabelMismatchError",
]
