"""PCB017: every declared slice and pin must be rendered."""

from collections import defaultdict
from typing import Any

from schematika.pcb.adapter import template_name
from schematika.pcb.findings import Finding, FindingLocation, Severity
from schematika.pcb.model import PCBBuildResult, SymbolMap, SymbolMapping

CODE = "PCB017"


def _symbol_map_for_template_name(
    mapping: SymbolMapping, tname: str
) -> SymbolMap | None:
    for smap in mapping.symbols:
        if template_name(smap.template) == tname:
            return smap
    return None


def _placed_slice_keys(result: PCBBuildResult) -> set[tuple[str, int]]:
    keys: set[tuple[str, int]] = set()
    for block in result.connector_blocks:
        for pc in block.pin_columns:
            for col in pc.columns:
                for slc in col.slices:
                    keys.add((slc.part_ref, slc.slice_index))
    return keys


def _floating_slice_keys(result: PCBBuildResult) -> set[tuple[str, int]]:
    keys: set[tuple[str, int]] = set()
    for fp in result.floating_parts:
        for idx in fp.slice_indices:
            keys.add((fp.part_ref, idx))
    return keys


def _placed_pin_counts(
    result: PCBBuildResult,
) -> dict[tuple[str, str], int]:
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for block in result.connector_blocks:
        for pc in block.pin_columns:
            for col in pc.columns:
                for slc in col.slices:
                    for pin in slc.pins:
                        counts[(slc.part_ref, pin.pin_id)] += 1
    return counts


def _floating_pin_counts(
    result: PCBBuildResult,
    mapping: SymbolMapping,
    part_template_names: dict[str, str],
) -> dict[tuple[str, str], int]:
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for fp in result.floating_parts:
        tname = part_template_names.get(fp.part_ref)
        if tname is None:
            continue
        smap = _symbol_map_for_template_name(mapping, tname)
        if smap is None:
            continue
        for idx in fp.slice_indices:
            if idx >= len(smap.slices):
                continue
            for pin_id in smap.slices[idx].pin_map:
                counts[(fp.part_ref, pin_id)] += 1
    return counts


def check(
    result: PCBBuildResult,
    circuit: Any,  # noqa: ANN401
    mapping: SymbolMapping,
) -> tuple[Finding, ...]:
    """Return ERROR for each declared slice or pin not rendered.

    Slice rule: every (part_ref, slice_index) declared in mapping.symbols for
    every instantiated part must appear in either a ConnectorBlock column or
    a FloatingPart.slice_indices.

    Pin rule: every pin in every declared slice must be rendered exactly once
    (either as a PlacedSlice pin or as a slice within a FloatingPart).

    Args:
        result: PCBBuildResult from build().
        circuit: SKiDL circuit IR; returns () if None.
        mapping: SymbolMapping config.

    Returns:
        Tuple of ERROR Findings.
    """
    if circuit is None:
        return ()

    part_template_names: dict[str, str] = {
        p.ref: getattr(p, "template_name", "") for p in circuit.parts
    }

    placed = _placed_slice_keys(result)
    floating = _floating_slice_keys(result)
    placed_pins = _placed_pin_counts(result)
    floating_pins = _floating_pin_counts(result, mapping, part_template_names)

    findings: list[Finding] = []
    for part in circuit.parts:
        ref = part.ref
        tname = getattr(part, "template_name", "")
        smap = _symbol_map_for_template_name(mapping, tname)
        if smap is None:
            continue

        for idx, slc in enumerate(smap.slices):
            key = (ref, idx)
            in_placed = key in placed
            in_floating = key in floating
            if not (in_placed or in_floating):
                pin_keys = ",".join(slc.pin_map.keys())
                findings.append(
                    Finding(
                        code=CODE,
                        severity=Severity.ERROR,
                        message=(
                            f"Part {ref!r} slice {idx} (pins {pin_keys}) is declared"
                            f" in the SymbolMap but not rendered anywhere"
                            f" (neither placed in a ConnectorBlock nor floating)."
                        ),
                        location=FindingLocation(part_ref=ref),
                    )
                )
                continue
            for pin_id in slc.pin_map:
                expected = 1
                actual = placed_pins.get((ref, pin_id), 0) + floating_pins.get(
                    (ref, pin_id), 0
                )
                if actual != expected:
                    findings.append(
                        Finding(
                            code=CODE,
                            severity=Severity.ERROR,
                            message=(
                                f"Pin {pin_id!r} of part {ref!r} (slice {idx}):"
                                f" expected {expected} render, got {actual}."
                            ),
                            location=FindingLocation(part_ref=ref),
                        )
                    )
    return tuple(findings)


CHECKS = (check,)
