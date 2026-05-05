"""PCB010: cross-block CHAIN label missing on one end."""

from collections import Counter
from typing import Any

from schematika.pcb.classify import NetKind, classify_net
from schematika.pcb.findings import Finding, FindingLocation, Severity
from schematika.pcb.model import PCBBuildResult, SymbolMapping, Terminator


def check(
    result: PCBBuildResult,
    circuit: Any,  # noqa: ANN401
    mapping: SymbolMapping,
) -> tuple[Finding, ...]:
    """Return WARNING for each CHAIN net that has a label on exactly one end.

    Args:
        result: PCBBuildResult from build().
        circuit: SKiDL circuit IR; returns () if None.
        mapping: SymbolMapping config.

    Returns:
        Tuple of WARNING Findings for CHAIN nets with a label on only one side.
    """
    if circuit is None:
        return ()

    # Count label occurrences per label string
    label_counts: Counter[str] = Counter()
    for block in result.connector_blocks:
        for pc in block.pin_columns:
            for col in pc.columns:
                if (
                    col.terminator is Terminator.LABEL
                    and col.terminator_label is not None
                ):
                    label_counts[col.terminator_label] += 1

    findings: list[Finding] = []
    for net in circuit.nets:
        if classify_net(net, power_nets=mapping.power_nets) is not NetKind.CHAIN:
            continue
        net_label = net.name.lstrip("/")
        if label_counts.get(net_label, 0) == 1:
            findings.append(
                Finding(
                    code="PCB010",
                    severity=Severity.WARNING,
                    message=(
                        f"CHAIN net {net.name!r} has a label on only one end "
                        "(cross-block label missing on the other side)."
                    ),
                    location=FindingLocation(net_name=net.name),
                )
            )
    return tuple(findings)


CHECKS = (check,)
