"""PCB014 -- verify in-column autoconnect wires.

The renderer emits wires only when ``_autoconnect_wire`` is called with
y_end > y_start. In practice the only case that fires is the POWER terminator:
a wire from the bottom of the last slice to the power symbol above it.
No pin-to-first-slice wires or inter-slice wires are ever emitted because the
renderer places each slice at cursor_y == prev_y (no gap between them).

This check builds the allow-list of those expected wires, then asserts:
  - Every vertical Line in circuit.elements matches an allow-list entry.
  - Every allow-list entry has a matching Line.
"""

from typing import Any

from schematika.core.geometry import Point
from schematika.core.primitives import Line
from schematika.electrical.system.system import Circuit
from schematika.pcb.findings import Finding, Severity
from schematika.pcb.layout_spec import LayoutSpec
from schematika.pcb.model import (
    ConnectorBlock,
    PCBBuildResult,
    SymbolMapping,
    Terminator,
)
from schematika.pcb.render import render_connector_block

CODE = "PCB014"
_TOLERANCE = 1e-6


def _build_allow_list(
    block: ConnectorBlock,
    layout: LayoutSpec,
    mapping: SymbolMapping,
    origin_x_mm: float,
    origin_y_mm: float,
) -> list[tuple[Point, Point]]:
    """Return (start, end) pairs the renderer is expected to emit as vertical Lines."""
    pairs: list[tuple[Point, Point]] = []
    for pin_idx, pin_col in enumerate(block.pin_columns):
        pin_x = (
            origin_x_mm
            + layout.side_padding_mm
            + (pin_idx + 0.5) * layout.pin_spacing_mm
        )
        cursor_y = origin_y_mm + layout.block_height_mm

        for col_idx, column in enumerate(pin_col.columns):
            if col_idx != 0:
                cursor_y += layout.section_gap_mm
                cursor_y += layout.section_gap_mm

            # Advance cursor_y through slices (no wires emitted between them)
            for _placed in column.slices:
                cursor_y += layout.slice_height_mm

            # POWER terminator wire (the only vertical Line the renderer emits)
            if (
                column.terminator is Terminator.POWER
                and column.terminator_label is not None
            ):
                for pnet in mapping.power_nets:
                    if pnet.matches(column.terminator_label):
                        power_y = cursor_y + layout.power_terminator_offset_mm
                        if power_y > cursor_y + _TOLERANCE:
                            pairs.append(
                                (Point(pin_x, cursor_y), Point(pin_x, power_y))
                            )
                        break

            cursor_y += layout.slice_height_mm

    return pairs


def _vertical_lines(rendered: Circuit) -> list[Line]:
    """Return only top-level vertical Lines (autoconnect wires, not NC x marks)."""
    return [
        el
        for el in rendered.elements
        if isinstance(el, Line) and abs(el.start.x - el.end.x) < _TOLERANCE
    ]


def _matches(line: Line, pair: tuple[Point, Point]) -> bool:
    a_s, a_e = pair
    return (
        abs(line.start.x - a_s.x) < _TOLERANCE
        and abs(line.start.y - a_s.y) < _TOLERANCE
        and abs(line.end.x - a_e.x) < _TOLERANCE
        and abs(line.end.y - a_e.y) < _TOLERANCE
    ) or (
        abs(line.start.x - a_e.x) < _TOLERANCE
        and abs(line.start.y - a_e.y) < _TOLERANCE
        and abs(line.end.x - a_s.x) < _TOLERANCE
        and abs(line.end.y - a_s.y) < _TOLERANCE
    )


def check(
    result: PCBBuildResult,
    circuit: Any = None,  # noqa: ANN401, ARG001
    mapping: Any = None,  # noqa: ANN401, ARG001
) -> tuple[Finding, ...]:
    """Return ERROR for each missing or extraneous autoconnect wire."""
    findings: list[Finding] = []
    resolved_mapping = result.mapping
    if resolved_mapping is None:
        resolved_mapping = SymbolMapping(symbols=(), connectors=(), power_nets=())

    layout = result.layout
    expected_y = layout.page_top_margin_mm
    by_ref = {b.connector_ref: b for b in result.connector_blocks}

    for page_idx, page in enumerate(result.pages):
        for ref, origin_x in page.placements:
            block = by_ref.get(ref)
            if block is None:
                continue

            rendered = render_connector_block(
                block,
                resolved_mapping,
                origin_x_mm=origin_x,
                origin_y_mm=expected_y,
                layout=layout,
            )
            allow_list = _build_allow_list(
                block, layout, resolved_mapping, origin_x, expected_y
            )
            v_lines = _vertical_lines(rendered)

            findings.extend(
                Finding(
                    code=CODE,
                    severity=Severity.ERROR,
                    message=(
                        f"Page {page_idx + 1}, {ref}: extraneous wire"
                        f" from ({line.start.x},{line.start.y})"
                        f" to ({line.end.x},{line.end.y})"
                    ),
                )
                for line in v_lines
                if not any(_matches(line, p) for p in allow_list)
            )

            findings.extend(
                Finding(
                    code=CODE,
                    severity=Severity.ERROR,
                    message=(
                        f"Page {page_idx + 1}, {ref}:"
                        f" missing autoconnect wire"
                        f" from ({pair[0].x},{pair[0].y})"
                        f" to ({pair[1].x},{pair[1].y})"
                    ),
                )
                for pair in allow_list
                if not any(_matches(line, pair) for line in v_lines)
            )

    return tuple(findings)


CHECKS = (check,)
