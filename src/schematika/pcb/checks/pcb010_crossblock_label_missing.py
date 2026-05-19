"""PCB010: cross-block CHAIN label missing on one end."""

from collections import Counter
from typing import Any

from schematika.pcb.classify import NetKind, classify_net
from schematika.pcb.findings import Finding, FindingLocation, Severity
from schematika.pcb.model import PCBBuildResult, SymbolMapping, Terminator


def _label_owning_connector(result: PCBBuildResult, net_label: str) -> str | None:
    """Return the connector_ref that carries a LABEL column for net_label, or None."""
    for block in result.connector_blocks:
        for pc in block.pin_columns:
            for col in pc.columns:
                if (
                    col.terminator is Terminator.LABEL
                    and col.terminator_label == net_label
                ):
                    return block.connector_ref
    return None


def _parts_placed_under_connector(
    result: PCBBuildResult, connector_ref: str
) -> set[str]:
    """Return part refs with slices placed under connector_ref."""
    refs: set[str] = set()
    for block in result.connector_blocks:
        if block.connector_ref != connector_ref:
            continue
        for pc in block.pin_columns:
            for col in pc.columns:
                for sl in col.slices:
                    refs.add(sl.part_ref)
    return refs


def _chain_net_satisfied(result: PCBBuildResult, net_label: str) -> bool:
    """Return True if a chain net is satisfied by chain_net_name grouping.

    A chain net is satisfied when its group (all columns with the same
    chain_net_name) contains either:
    - Two or more LABEL columns, OR
    - At least one LABEL + at least one PIN_AT_BOTTOM column.
    """
    label_count = 0
    pin_at_bottom_count = 0
    for block in result.connector_blocks:
        for pc in block.pin_columns:
            for col in pc.columns:
                if col.chain_net_name != net_label:
                    continue
                if col.terminator is Terminator.LABEL:
                    label_count += 1
                elif col.terminator is Terminator.PIN_AT_BOTTOM:
                    pin_at_bottom_count += 1
    return label_count >= 2 or (label_count >= 1 and pin_at_bottom_count >= 1)  # noqa: PLR2004


def check(
    result: PCBBuildResult,
    circuit: Any,  # noqa: ANN401
    mapping: SymbolMapping,
) -> tuple[Finding, ...]:
    """Return WARNING for each CHAIN net that has a label on exactly one end.

    A CHAIN net with label_count == 1 is exempt when the label is a dedup
    back-reference: that is, both non-connector pin parts of the net are
    placed inline under the connector that carries the sole label.  In that
    case the relay contact is visually drawn — no second label is required.

    A CHAIN net is also exempt when chain_net_name grouping shows it is
    satisfied by at least one LABEL + one PIN_AT_BOTTOM column.

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

    connector_refs = {b.connector_ref for b in result.connector_blocks}

    findings: list[Finding] = []
    for net in circuit.nets:
        if classify_net(net, power_nets=mapping.power_nets) is not NetKind.CHAIN:
            continue
        net_label = net.name.lstrip("/")
        if label_counts.get(net_label, 0) != 1:
            continue
        # Check if satisfied via chain_net_name grouping (LABEL + PIN_AT_BOTTOM).
        if _chain_net_satisfied(result, net_label):
            continue
        # Determine whether the sole label is a dedup back-reference.
        # That happens when the owning connector has ALL non-connector pin parts
        # placed as slices under itself (the relay is drawn inline there).
        owner = _label_owning_connector(result, net_label)
        if owner is not None:
            placed_under_owner = _parts_placed_under_connector(result, owner)
            non_connector_parts = {p.part_ref for p in net.pins} - connector_refs
            if non_connector_parts.issubset(placed_under_owner):
                # All parts are drawn inline under the owning connector — exempt.
                continue
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
