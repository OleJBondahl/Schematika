"""PCB014 -- verify in-column autoconnect wires.

This check builds the allow-list of vertical Lines the renderer is expected to
emit, then asserts:
  - Every vertical Line in circuit.elements matches an allow-list entry.
  - Every allow-list entry has a matching Line.
"""

from typing import Any

from schematika.core.geometry import Point
from schematika.core.primitives import Line
from schematika.core.symbol import Symbol
from schematika.electrical.system.system import Circuit
from schematika.pcb.findings import Finding, Severity
from schematika.pcb.layout_spec import LayoutSpec
from schematika.pcb.model import (
    Column,
    ConnectorBlock,
    PCBBuildResult,
    SymbolMapping,
    Terminator,
)
from schematika.pcb.render import render_connector_block

CODE = "PCB014"
_TOLERANCE = 1e-6


def _top_port_y_local(symbol: Symbol) -> float:
    upward = [p for p in symbol.ports.values() if p.direction.dy < -_TOLERANCE]
    if upward:
        return min(p.position.y for p in upward)
    if not symbol.ports:
        return 0.0
    return min(p.position.y for p in symbol.ports.values())


def _bottom_port_y_local(symbol: Symbol) -> float:
    downward = [p for p in symbol.ports.values() if p.direction.dy > _TOLERANCE]
    if downward:
        return max(p.position.y for p in downward)
    if not symbol.ports:
        return 0.0
    return max(p.position.y for p in symbol.ports.values())


def _column_allow_pairs(
    column: Column,
    layout: LayoutSpec,
    mapping: SymbolMapping,
    pin_x: float,
    chain_y: float,
) -> tuple[list[tuple[Point, Point]], float]:
    """Return (pairs, terminator_y) for one column."""
    pairs: list[tuple[Point, Point]] = []
    slice_top_y = chain_y
    last_outgoing_y = chain_y

    for placed in column.slices:
        sym = placed.symbol
        top_local = _top_port_y_local(sym)
        bot_local = _bottom_port_y_local(sym)
        sym_y = slice_top_y - top_local
        if slice_top_y > last_outgoing_y + _TOLERANCE:
            pairs.append((Point(pin_x, last_outgoing_y), Point(pin_x, slice_top_y)))
        last_outgoing_y = sym_y + bot_local
        slice_top_y += layout.slice_height_mm

    terminator_y = slice_top_y if column.slices else chain_y

    if column.slices:
        if terminator_y > last_outgoing_y + _TOLERANCE:
            pairs.append((Point(pin_x, last_outgoing_y), Point(pin_x, terminator_y)))
    elif terminator_y > chain_y + _TOLERANCE:
        pairs.append((Point(pin_x, chain_y), Point(pin_x, terminator_y)))

    if column.terminator is Terminator.POWER and column.terminator_label is not None:
        for pnet in mapping.power_nets:
            if pnet.matches(column.terminator_label):
                power_y = terminator_y + layout.power_terminator_offset_mm
                if power_y > terminator_y + _TOLERANCE:
                    pairs.append((Point(pin_x, terminator_y), Point(pin_x, power_y)))
                break

    if column.terminator is Terminator.PIN_AT_BOTTOM:
        bottom_y = layout.bottom_terminator_y_mm
        if bottom_y > terminator_y + _TOLERANCE:
            pairs.append((Point(pin_x, terminator_y), Point(pin_x, bottom_y)))

    return pairs, terminator_y


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
        pin_anchor_y = origin_y_mm + layout.block_height_mm
        cursor_y = pin_anchor_y

        for col_idx, column in enumerate(pin_col.columns):
            if col_idx == 0:
                if column.slices:
                    gap = layout.connector_to_first_symbol_gap_mm
                elif column.terminator is Terminator.NC:
                    # NC with no slices: marker sits flush at the connector pin.
                    gap = 0.0
                else:
                    gap = layout.connector_to_first_label_gap_mm
                chain_y = pin_anchor_y + gap
                cursor_y = chain_y
                if gap > _TOLERANCE:
                    pairs.append((Point(pin_x, pin_anchor_y), Point(pin_x, chain_y)))
            else:
                cursor_y += layout.slice_height_mm
                chain_y = cursor_y

            col_pairs, terminator_y = _column_allow_pairs(
                column, layout, mapping, pin_x, chain_y
            )
            pairs.extend(col_pairs)
            cursor_y = terminator_y + layout.slice_height_mm

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
    by_ref = {b.connector_ref: b for b in result.connector_blocks}

    for page_idx, page in enumerate(result.pages):
        for ref, origin_x, origin_y in page.placements:
            block = by_ref.get(ref)
            if block is None:
                continue

            rendered = render_connector_block(
                block,
                resolved_mapping,
                origin_x_mm=origin_x,
                origin_y_mm=origin_y,
                layout=layout,
            )
            allow_list = _build_allow_list(
                block, layout, resolved_mapping, origin_x, origin_y
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
