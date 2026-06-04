"""Render a PLC connection report from a HarnessBuildResult.

Adapts the new ``PlcAssignment``/``Wire`` data into the row shape the legacy
``generate_plc_report_rows`` already produces, so the PLC CSV can be generated
from the Harness path. The legacy ``ConnectionRow`` pipeline is untouched.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from schematika.electrical.plc_resolver import generate_plc_report_rows

if TYPE_CHECKING:
    from schematika.electrical.harness import HarnessBuildResult
    from schematika.electrical.plc_resolver import PlcRack

_PLC_PREFIX = "PLC:"


def plc_csv_rows(
    result: HarnessBuildResult, rack: PlcRack
) -> list[tuple[str, str, str, str, str, str]]:
    """PLC report rows ``(Module, MPN, PLC Pin, Component, Pin, Terminal)``.

    One row per rack channel pin -- empty rows for unallocated channels -- matching
    ``generate_plc_report_rows``. The Terminal column is reconstructed from the
    wire feeding each PLC channel.

    Args:
        result: Frozen build result from ``Harness.build()``, carrying wires and
            PLC assignments.
        rack: Same ``PlcRack`` passed to ``Harness``; used by
            ``generate_plc_report_rows`` to emit empty rows for unused channels.

    Returns:
        One 6-tuple per rack channel pin in module order, with empty strings for
        unallocated channels.

    Examples:
        >>> from schematika.electrical.harness import HarnessBuildResult
        >>> from schematika.electrical.plc_report import plc_csv_rows
        >>> plc_csv_rows(HarnessBuildResult(wires=(), plc_assignments=()), [])
        []
    """
    terminal_by_channel: dict[tuple[str, str], tuple[str, str]] = {}
    for wire in result.wires:
        target_device = str(wire.target.device)
        if target_device.startswith(_PLC_PREFIX):
            module = target_device[len(_PLC_PREFIX) :]
            terminal_by_channel[(module, wire.target.port_id)] = (
                str(wire.source.device),
                wire.source.port_id,
            )

    connections: list[tuple[str, str, str, str, str, str]] = []
    for assignment in result.plc_assignments:
        terminal_tag, terminal_pin = terminal_by_channel.get(
            (assignment.module, assignment.pin_label), ("", "")
        )
        connections.append(
            (
                str(assignment.source.device),
                assignment.source.port_id,
                terminal_tag,
                terminal_pin,
                f"{_PLC_PREFIX}{assignment.module}",
                assignment.pin_label,
            )
        )
    return generate_plc_report_rows(connections, rack)
