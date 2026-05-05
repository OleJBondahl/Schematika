"""PCB005: CHAIN net not rendered as wire or label."""

from typing import Any

from schematika.pcb.classify import NetKind, classify_net
from schematika.pcb.findings import Finding, FindingLocation, Severity
from schematika.pcb.model import PCBBuildResult, SymbolMapping


def check(
    result: PCBBuildResult,
    circuit: Any,  # noqa: ANN401
    mapping: SymbolMapping,
) -> tuple[Finding, ...]:
    """Return ERROR for each CHAIN net where both endpoints are placed but not rendered.

    Args:
        result: PCBBuildResult from build().
        circuit: SKiDL circuit IR; returns () if None.
        mapping: SymbolMapping config.

    Returns:
        Tuple of ERROR Findings for unrendered CHAIN nets.
    """
    if circuit is None:
        return ()

    # Collect all terminator labels and placed (part_ref, pin_id) pairs.
    all_labels: set[str] = set()
    placed_pins: set[tuple[str, str]] = set()
    for block in result.connector_blocks:
        for pc in block.pin_columns:
            for col in pc.columns:
                for slc in col.slices:
                    for pin in slc.pins:
                        placed_pins.add((slc.part_ref, pin.pin_id))
                if col.terminator_label is not None:
                    all_labels.add(col.terminator_label)

    findings: list[Finding] = []
    for net in circuit.nets:
        if classify_net(net, power_nets=mapping.power_nets) is not NetKind.CHAIN:
            continue
        # All pins on the net must be in placed slices (not just the part_ref).
        net_pins = {(pin.part_ref, pin.pin_name) for pin in net.pins}
        if not net_pins.issubset(placed_pins):
            continue
        net_label = net.name.lstrip("/")
        if net_label not in all_labels:
            findings.append(
                Finding(
                    code="PCB005",
                    severity=Severity.ERROR,
                    message=(
                        f"CHAIN net {net.name!r} is not rendered as a wire or label."
                    ),
                    location=FindingLocation(net_name=net.name),
                )
            )
    return tuple(findings)


CHECKS = (check,)
