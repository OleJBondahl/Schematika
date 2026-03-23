"""
Schematika Electrical — IEC 60617 electrical schematic diagram API.
"""

# system.system must be imported first — pre-loads layout.layout, breaking the
# circular import chain that would otherwise form via builder.py → layout.layout.
from .system.system import Circuit, add_symbol, merge_circuits, render_system  # noqa: E402
from .layout.layout import auto_connect
from .builder import BuildResult, CircuitBuilder, ComponentRef, PortRef
from .builder_models import merge_reuse_tags
from .descriptors import build_from_descriptors, comp, ref, term
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
    DeviceEntry,
    DeviceTemplate,
    FieldDevice,
    FixedPin,
    PinDef,
    PrefixedPin,
    SequentialPin,
    generate_field_connections,
)
from .model.constants import (
    CB_2P_PINS,
    CB_3P_PINS,
    CIRCUIT_SPACING,
    CIRCUIT_SPACING_NARROW,
    CIRCUIT_SPACING_WIDE,
    COIL_PINS,
    CONTACTOR_3P_PINS,
    NC_CONTACT_PINS,
    NO_CONTACT_PINS,
    PinPrefix,
    SPACING_COMPACT,
    SPACING_DEFAULT,
    SPACING_NARROW,
    SPACING_STANDARD,
    StandardCircuitKeys,
    StandardTags,
    THERMAL_OVERLOAD_PINS,
    WireLabels,
)
from .model.core import SymbolFactory
from .model.state import GenerationState, create_initial_state
from .plc_resolver import (
    PlcDesignation,
    PlcModuleType,
    PlcRack,
    extract_plc_connections_from_registry,
    generate_plc_report_rows,
    resolve_plc_references,
)
from schematika.project import Project
from .system.connection_registry import export_registry_to_csv, get_registry
from .terminal import Terminal
from .utils.autonumbering import (
    create_autonumberer,
    get_tag_number,
    next_tag,
    next_terminal_pins,
)
from .utils.export_utils import (
    export_terminal_list,
    finalize_terminal_csv,
    merge_terminal_csv,
)
from .utils.terminal_bridges import (
    BridgeRange,
    ConnectionDef,
    expand_range_to_pins,
    generate_internal_connections_data,
    get_connection_groups_for_terminal,
    parse_terminal_pins_from_csv,
    update_csv_with_internal_connections,
)
from .utils.utils import (
    apply_start_indices,
    fixed_tag,
    get_terminal_counter,
    merge_terminals,
    natural_sort_key,
    set_tag_counter,
    set_terminal_counter,
)
from .wire import wire

__all__ = [
    # Core
    "Circuit",
    "add_symbol",
    "merge_circuits",
    "render_system",
    "auto_connect",
    "BuildResult",
    "CircuitBuilder",
    "ComponentRef",
    "PortRef",
    "merge_reuse_tags",
    "build_from_descriptors",
    "comp",
    "ref",
    "term",
    "wire",
    "Project",
    # Symbols
    "SymbolFactory",
    # Constants
    "CB_2P_PINS",
    "CB_3P_PINS",
    "CIRCUIT_SPACING",
    "CIRCUIT_SPACING_NARROW",
    "CIRCUIT_SPACING_WIDE",
    "COIL_PINS",
    "CONTACTOR_3P_PINS",
    "NC_CONTACT_PINS",
    "NO_CONTACT_PINS",
    "PinPrefix",
    "SPACING_COMPACT",
    "SPACING_DEFAULT",
    "SPACING_NARROW",
    "SPACING_STANDARD",
    "StandardCircuitKeys",
    "StandardTags",
    "THERMAL_OVERLOAD_PINS",
    "WireLabels",
    # Utilities
    "GenerationState",
    "create_initial_state",
    "create_autonumberer",
    "get_tag_number",
    "next_tag",
    "next_terminal_pins",
    "export_terminal_list",
    "finalize_terminal_csv",
    "merge_terminal_csv",
    "apply_start_indices",
    "fixed_tag",
    "get_terminal_counter",
    "merge_terminals",
    "natural_sort_key",
    "set_tag_counter",
    "set_terminal_counter",
    "export_registry_to_csv",
    "get_registry",
    # Devices
    "InternalDevice",
    "CableData",
    "ConnectionRow",
    "ConnectorData",
    "DeviceCable",
    "DeviceEntry",
    "DeviceTemplate",
    "FieldDevice",
    "FixedPin",
    "PinDef",
    "PrefixedPin",
    "SequentialPin",
    "generate_field_connections",
    "Terminal",
    "BridgeRange",
    "ConnectionDef",
    "expand_range_to_pins",
    "generate_internal_connections_data",
    "get_connection_groups_for_terminal",
    "parse_terminal_pins_from_csv",
    "update_csv_with_internal_connections",
    # PLC
    "PlcDesignation",
    "PlcModuleType",
    "PlcRack",
    "extract_plc_connections_from_registry",
    "generate_plc_report_rows",
    "resolve_plc_references",
    # Exceptions
    "CircuitValidationError",
    "ComponentNotFoundError",
    "PortNotFoundError",
    "TagReuseError",
    "TerminalReuseError",
    "WireLabelMismatchError",
]
