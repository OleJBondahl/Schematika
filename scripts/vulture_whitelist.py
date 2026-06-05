"""Vulture whitelist — symbols used dynamically or via patterns vulture can't see.

Run as:

    uv run vulture src/ scripts/vulture_whitelist.py --min-confidence 60

Generated initially via `vulture --make-whitelist` and then curated to keep
only the legitimate false positives (singledispatch handlers, dataclass
fields read via attribute access, public-API methods called by downstream
consumers rather than the internal test suite).
"""

# Vulture interprets this file as code.  Use the `_.attr` form for attributes,
# bare names for module-level symbols, and assign anything to silence "unused".

_ = None  # sink for unused-name suppression


def _touch(*args: object) -> None:
    """Noop to make every argument look 'used' to vulture."""


# --- singledispatch handlers (core/transform.py) -----------------------------
# All named `_` — register themselves at import time via @translate.register
# etc.  Already visible through the `_` sink above when vulture sees them in
# their own module.

# --- dataclass / frozen-dataclass fields read via attribute access -----------
_.opacity  # Style.opacity
_.contact_channels  # GenerationState
_.pin_counter  # GenerationState
_.manufacturer  # CatalogDevice
_.model  # CatalogDevice
_.cable_type  # CableSpec
_.relative_to_idx  # ComponentSpec
_.spacing_override  # ComponentSpec
_.source_pole  # PlannedConnection
_.target_pole  # PlannedConnection

# --- public builder / model API --------------------------------------------
# BlockDiagram.spread / mirror / legend are documented builder methods.
_.spread
_.mirror
_.legend
# Block placement DSL
_.above
_.below
_.right_of
_.left_of
_.place
_.under
_._set_placement
# CatalogDevice.first_letter computed on access, read by external code
_.first_letter
# Catalog query methods
_.by_device
_.instruments
_.electrical_devices
_.generate_cross_reference_table
# ConnectionRegistry
_.add_connections
# BuildResult accessor used by end-users (not tests)
_.get_symbols
_.component_tags
# CircuitBuilder higher-level methods
_.connect_matching
_.merge

# --- __all__-exported helpers used by consumer projects ----------------------
DEFAULT_CABLE_PREFIX = None  # cable/constants.py
DEFAULT_CABLE_START = None  # cable/constants.py
generate_cable_csv = None  # electrical/cable_export.py

# --- Layout helpers called via descriptor builders ---------------------------
draw_wire_labeled = None  # electrical/layout/layout.py
layout_vertical_chain = None  # electrical/layout/layout.py

# --- Core utility exposed for future use / external wiring ------------------
compute_bounding_box = None  # core/bbox.py
resolve_terminal_pins = None  # core/autonumbering.py
create_pin_label_text = None  # core/parts.py
_edge_point = None  # block/rendering.py — future cable-routing helper

# Validation status flag read by external rendering reports
_.passed

# --- block/model.py internals accessed by renderer/layout -------------------
# (Placement fields used by layout engine.)

# --- Project public API methods (consumed by ../auxillary_cabinet_v3) -------
_.set_pin_start
_.reserve_pins
_.set_catalog
_.add_pid
_.pid_page
_.set_cable_registry
_.cable_registry
_.add_pcb
_.add_block_diagram
_.block_page
_.plc_rack
_.internal_wiring
_.add_field_devices
_.inter_device_cables
_.resolved_connections
_.front_page
_.terminal_report
_.plc_report
_.custom_page
_.bom_report
_.cable_pages
_.export_wire_labels
_.export_taglist
_.export_bom_excel
_.export_bom_csv
_.build_circuits
_.build_svgs
_.render_svgs
_.export_csvs
_.compile_pdf
_.alignment

# --- PID public API (symbol factories, builder methods) --------------------
_.signal_line
_.get_equipment_by_tag
add_equipment = None  # pid/diagram.py free function
add_instrument = None  # pid/builder.py method
add_instrument_from_catalog = None  # pid/builder.py method
merge_diagrams = None  # pid/diagram.py
validate_pid = None  # pid/validation.py
# PID symbol factories (public library — used by consumers, not by internal tests):
pipe_segment = None
pipe_tee = None
pipe_reducer = None
pipe_cap = None
centrifugal_pump = None
positive_displacement_pump = None
gate_valve = None
globe_valve = None
control_valve = None
check_valve = None
ball_valve = None
three_way_valve = None
tank = None
heat_exchanger = None
PNEUMATIC_LINE = None  # pid/connections.py
TEXT_STYLE = None  # pid/styles.py

# --- electrical public API ---------------------------------------------------
add_spdt = None  # electrical/builder.py — public method exposed for SPDT
layout_horizontal = None  # electrical/layout
create_labeled_connections = None  # electrical/layout/wire_labels
register_3phase_input = None  # electrical/system/connection_registry
register_3phase_output = None
export_terminals_to_csv = None  # electrical/system/system_analysis
export_components_to_csv = None
# Electrical constants re-exported via __init__
LINE_WIDTH_THICK = None
BREAKER = CONTACTOR = RELAY = SWITCH = POWER_SUPPLY = None
TRANSFORMER = MOTOR = INDICATOR = BUTTON = SENSOR = TERMINAL = None
SPDT_3P_PINS = TERMINAL_3P_PINS = None
TN = IT = SINGLEPHASE = None
MAIN = SUPPLY = OUTPUT = None
V24 = GND = None
INPUT = INPUT_1 = INPUT_2 = OUTPUT_24V = OUTPUT_GND = None
# wire color constants
RD_2_5 = BK_2_5 = RD_0_5 = BK_0_5 = WH_0_5 = None
BR_2_5 = GY_2_5 = BL_2_5 = GR_YE_2_5 = None
BR_1_5 = BK_1_5 = GY_1_5 = BL_1_5 = None

# --- mcp public tool handlers (entry points, not called from within library) -
list_symbols = describe_symbol = validate_circuit = None
render_circuit = get_reference = None
# signal.signal handler parameters
frame = signum = None

# --- pcb internals used via attribute access --------------------------------
_pack_pages = None
