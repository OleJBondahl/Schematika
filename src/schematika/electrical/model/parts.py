"""Re-export shim: actual code lives in schematika.core.parts."""

# Re-export constants that were previously importable from model.parts
# (they originated in model.constants but were imported at module level there)
from schematika.core.parts import (
    _add_remapped_ports,
    box,
    create_extended_blade,
    create_pin_label_text,
    create_pin_labels,
    multipole,
    pad_pins,
    standard_style,
    standard_text,
    terminal_circle,
    terminal_text,
)
from schematika.electrical.model.constants import (
    PIN_LABEL_OFFSET_X,
    PIN_LABEL_OFFSET_Y_ADJUST,
    TEXT_FONT_FAMILY_AUX,
    TEXT_SIZE_PIN,
)

__all__ = [
    "PIN_LABEL_OFFSET_X",
    "PIN_LABEL_OFFSET_Y_ADJUST",
    "TEXT_FONT_FAMILY_AUX",
    "TEXT_SIZE_PIN",
    "_add_remapped_ports",
    "box",
    "create_extended_blade",
    "create_pin_label_text",
    "create_pin_labels",
    "multipole",
    "pad_pins",
    "standard_style",
    "standard_text",
    "terminal_circle",
    "terminal_text",
]
