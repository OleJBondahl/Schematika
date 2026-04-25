"""schematika.electrical.advanced — tier-2 electrical names.

Public but lighter docstring bar; free to break on minor versions.
Includes: descriptors mini-API, type aliases, pin-tuple constants,
internal utilities, and inter-device helpers.
"""

from schematika.electrical.builder import ComponentRef, PortRef
from schematika.electrical.builder_models import merge_reuse_tags
from schematika.electrical.descriptors import build_from_descriptors, comp, ref, term
from schematika.electrical.field_devices import (
    DeviceEntry,
    FixedPin,
    PrefixedPin,
    SequentialPin,
)
from schematika.electrical.inter_device import EMPTY_TEMPLATE, InterDeviceConnection
from schematika.electrical.model.constants import (
    CB_2P_PINS,
    CB_3P_PINS,
    COIL_PINS,
    CONTACTOR_3P_PINS,
    NC_CONTACT_PINS,
    NO_CONTACT_PINS,
    LabelPosition,
    Position,
    Side,
    StandardCircuitKeys,
)
from schematika.electrical.model.core import SymbolFactory
from schematika.electrical.plc_resolver import PlcDesignation
from schematika.electrical.system.connection_registry import (
    export_registry_to_csv,
    get_registry,
)
from schematika.electrical.system.system import add_symbol
from schematika.electrical.utils.autonumbering import (
    get_tag_number,
    next_tag,
    next_terminal_pins,
)
from schematika.electrical.utils.export_utils import (
    export_terminal_list,
    finalize_terminal_csv,
    merge_terminal_csv,
)
from schematika.electrical.utils.terminal_bridges import (
    BridgeRange,
    ConnectionDef,
    expand_range_to_pins,
    generate_internal_connections_data,
    get_connection_groups_for_terminal,
    parse_terminal_pins_from_csv,
    update_csv_with_internal_connections,
)
from schematika.electrical.utils.utils import (
    fixed_tag,
    get_terminal_counter,
    merge_terminals,
    natural_sort_key,
    set_tag_counter,
)
from schematika.electrical.wire import wire

__all__ = [  # noqa: RUF022
    "add_symbol",
    "ComponentRef",
    "PortRef",
    "merge_reuse_tags",
    "build_from_descriptors",
    "comp",
    "ref",
    "term",
    "wire",
    "SymbolFactory",
    "LabelPosition",
    "Position",
    "Side",
    "StandardCircuitKeys",
    "CB_2P_PINS",
    "CB_3P_PINS",
    "COIL_PINS",
    "CONTACTOR_3P_PINS",
    "NC_CONTACT_PINS",
    "NO_CONTACT_PINS",
    "get_tag_number",
    "next_tag",
    "next_terminal_pins",
    "export_terminal_list",
    "finalize_terminal_csv",
    "merge_terminal_csv",
    "fixed_tag",
    "get_terminal_counter",
    "merge_terminals",
    "natural_sort_key",
    "set_tag_counter",
    "export_registry_to_csv",
    "get_registry",
    "DeviceEntry",
    "FixedPin",
    "PrefixedPin",
    "SequentialPin",
    "EMPTY_TEMPLATE",
    "InterDeviceConnection",
    "BridgeRange",
    "ConnectionDef",
    "expand_range_to_pins",
    "generate_internal_connections_data",
    "get_connection_groups_for_terminal",
    "parse_terminal_pins_from_csv",
    "update_csv_with_internal_connections",
    "PlcDesignation",
]
