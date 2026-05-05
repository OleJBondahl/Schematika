"""Connector-anchored walk algorithm.

This module is the heart of schematika.pcb v2 — it consumes an adapter IR
plus a SymbolMapping and produces tuple[ConnectorBlock, ...] + floating
parts. Subsequent tasks add the actual chain walk; this task only adds the
enumeration helper.
"""

from collections.abc import Iterator
from typing import Any

from schematika.pcb.adapter import template_name
from schematika.pcb.model import SymbolMapping


def enumerate_connectors(
    ir: Any,  # noqa: ANN401
    mapping: SymbolMapping,
) -> Iterator[Any]:
    """Yield part-IRs whose template is a connector, in declaration order.

    Args:
        ir: Internal representation with a `parts` iterable of part objects,
            each with a `template_name` attribute.
        mapping: SymbolMapping containing registered connector templates.

    Yields:
        Part objects from ir.parts whose template_name matches a registered
        connector template.
    """
    connector_template_names = {template_name(cm.template) for cm in mapping.connectors}
    for part in ir.parts:
        if part.template_name in connector_template_names:
            yield part
