"""PCB004: dropped 1-pin net not marked NC."""

from typing import Any

from schematika.pcb.findings import Finding, FindingLocation, Severity
from schematika.pcb.model import PCBBuildResult, SymbolMapping


def check(
    result: PCBBuildResult,  # noqa: ARG001
    circuit: Any,  # noqa: ANN401
    mapping: SymbolMapping,  # noqa: ARG001
) -> tuple[Finding, ...]:
    """Return WARNING for each 1-pin net not marked NC.

    Args:
        result: PCBBuildResult from build() (unused).
        circuit: SKiDL circuit IR; returns () if None.
        mapping: SymbolMapping config (unused).

    Returns:
        Tuple of WARNING Findings for dropped nets with exactly 1 pin.
    """
    if circuit is None:
        return ()

    nc_set: set[tuple[str, str]] = set(getattr(circuit, "nc_pins", ()) or ())

    findings: list[Finding] = []
    for net in circuit.nets:
        if len(net.pins) != 1:
            continue
        pin = net.pins[0]
        if (pin.part_ref, pin.pin_name) not in nc_set:
            findings.append(
                Finding(
                    code="PCB004",
                    severity=Severity.WARNING,
                    message=f"Net {net.name!r} has only 1 pin and is not marked NC.",
                    location=FindingLocation(net_name=net.name),
                )
            )
    return tuple(findings)


CHECKS = (check,)
