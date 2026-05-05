"""PCB006: power net rendered without power symbol."""

from typing import Any

from schematika.pcb.findings import Finding, FindingLocation, Severity
from schematika.pcb.model import PCBBuildResult, SymbolMapping, Terminator


def check(
    result: PCBBuildResult,
    circuit: Any,  # noqa: ANN401, ARG001
    mapping: SymbolMapping,
) -> tuple[Finding, ...]:
    """Return ERROR for each column using a power net label without a POWER terminator.

    Args:
        result: PCBBuildResult from build().
        circuit: SKiDL circuit IR (unused).
        mapping: SymbolMapping config.

    Returns:
        Tuple of ERROR Findings for power nets rendered without a power symbol.
    """
    power_canonical = {pm.canonical_name for pm in mapping.power_nets}

    findings: list[Finding] = []
    for block in result.connector_blocks:
        for pc in block.pin_columns:
            for col in pc.columns:
                label = col.terminator_label
                if label in power_canonical and col.terminator is not Terminator.POWER:
                    findings.append(
                        Finding(
                            code="PCB006",
                            severity=Severity.ERROR,
                            message=(
                                f"Power net {label!r} in block {block.connector_ref!r} "
                                "is not rendered with a POWER terminator."
                            ),
                            location=FindingLocation(
                                connector_block_ref=block.connector_ref
                            ),
                        )
                    )
    return tuple(findings)


CHECKS = (check,)
