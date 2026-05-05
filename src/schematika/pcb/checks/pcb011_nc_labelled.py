"""PCB011: NC pin rendered as label instead of dropped."""

from typing import Any

from schematika.pcb.findings import Finding, FindingLocation, Severity
from schematika.pcb.model import PCBBuildResult, SymbolMapping


def check(
    result: PCBBuildResult,
    circuit: Any,  # noqa: ANN401
    mapping: SymbolMapping,  # noqa: ARG001
) -> tuple[Finding, ...]:
    """Return ERROR for each net where all pins are NC but the net appears as a label.

    Args:
        result: PCBBuildResult from build().
        circuit: SKiDL circuit IR.
        mapping: SymbolMapping config (unused).

    Returns:
        Tuple of ERROR Findings for NC nets rendered as labels.
    """
    if circuit is None:
        return ()

    nc_set: set[tuple[str, str]] = set(getattr(circuit, "nc_pins", ()) or ())
    if not nc_set:
        return ()

    # Collect all terminator labels
    all_labels: set[str] = set()
    for block in result.connector_blocks:
        for pc in block.pin_columns:
            for col in pc.columns:
                if col.terminator_label is not None:
                    all_labels.add(col.terminator_label)

    findings: list[Finding] = []
    for net in circuit.nets:
        if not net.pins:
            continue
        if all((pin.part_ref, pin.pin_name) in nc_set for pin in net.pins):
            net_label = net.name.lstrip("/")
            if net_label in all_labels:
                findings.append(
                    Finding(
                        code="PCB011",
                        severity=Severity.ERROR,
                        message=(
                            f"Net {net.name!r} has only NC pins but is rendered "
                            "as a label (it should be dropped)."
                        ),
                        location=FindingLocation(net_name=net.name),
                    )
                )
    return tuple(findings)


CHECKS = (check,)
