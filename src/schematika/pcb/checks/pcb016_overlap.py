"""PCB016 - flags geometric overlaps between elements on a rendered page.

Checks six element-pair categories: symbol-symbol, wire-wire, wire-symbol,
text-symbol, text-wire, text-text.  Reports all overlaps found as ERRORs.

Exemptions:
- Intra-symbol elements (pin labels, internal wires inside a placed Symbol).
- Two wires sharing exactly one endpoint at a port position.
- A wire endpoint touching a symbol's perimeter at a port position.
- Terminator texts (text anchor positioned at a symbol port exit).
- NC-cross wire pairs (two short diagonal wires sharing a midpoint).
- Text overlapping only NC-cross wires (the NC label above an X mark).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from schematika.core.bbox import compute_bounding_box
from schematika.core.primitives import Line, Text
from schematika.core.validation import text_bbox
from schematika.core.validation_geometry import (
    segment_intersects_bbox_interior,
    segments_intersect_strict,
)
from schematika.electrical.system.system import Circuit, merge_circuits
from schematika.pcb.findings import Finding, FindingLocation, Severity
from schematika.pcb.model import Page, PCBBuildResult, SymbolMapping
from schematika.pcb.render import render_connector_block

if TYPE_CHECKING:
    from schematika.core.geometry import Point
    from schematika.core.symbol import Symbol

CODE = "PCB016"
_TOUCH_TOLERANCE = 0.1  # mm - anything within this is "just touching"
_NC_MAX_HALF = 3.0  # mm - NC cross arm half-length threshold


# ---------------------------------------------------------------------------
# Bbox helpers
# ---------------------------------------------------------------------------


def _symbol_bbox(sym: Symbol) -> tuple[float, float, float, float]:
    bb = compute_bounding_box(sym)
    return (bb.min_x, bb.min_y, bb.max_x, bb.max_y)


def _wire_bbox(line: Line) -> tuple[float, float, float, float]:
    sw = line.style.stroke_width / 2
    x1, y1 = line.start.x, line.start.y
    x2, y2 = line.end.x, line.end.y
    return (min(x1, x2) - sw, min(y1, y2) - sw, max(x1, x2) + sw, max(y1, y2) + sw)


def _bboxes_overlap_strict(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
    *,
    tol: float = _TOUCH_TOLERANCE,
) -> bool:
    """True only when boxes have actual interior overlap (not just touching)."""
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return ax0 + tol < bx1 and ax1 - tol > bx0 and ay0 + tol < by1 and ay1 - tol > by0


# ---------------------------------------------------------------------------
# Port-position helpers (exemptions)
# ---------------------------------------------------------------------------


def _all_port_positions(symbols: list[Symbol]) -> list[Point]:
    return [p.position for sym in symbols for p in sym.ports.values()]


def _point_near(p: Point, q: Point, tol: float = _TOUCH_TOLERANCE) -> bool:
    return abs(p.x - q.x) <= tol and abs(p.y - q.y) <= tol


def _wire_endpoint_at_symbol_port(line: Line, sym: Symbol) -> bool:
    for ep in (line.start, line.end):
        if any(_point_near(ep, p.position) for p in sym.ports.values()):
            return True
    return False


def _wires_share_single_endpoint(a: Line, b: Line) -> bool:
    shared = sum(
        1 for pa in (a.start, a.end) for pb in (b.start, b.end) if _point_near(pa, pb)
    )
    return shared == 1


def _wire_midpoint(line: Line) -> tuple[float, float]:
    return ((line.start.x + line.end.x) / 2, (line.start.y + line.end.y) / 2)


def _is_diagonal(line: Line, tol: float = _TOUCH_TOLERANCE) -> bool:
    dx = abs(line.end.x - line.start.x)
    dy = abs(line.end.y - line.start.y)
    return dx > tol and dy > tol


def _wire_length_sq(line: Line) -> float:
    dx = line.end.x - line.start.x
    dy = line.end.y - line.start.y
    return dx * dx + dy * dy


def _classify_nc_cross_wires(wires: list[Line]) -> set[int]:
    """Return indices of wires forming an NC-cross (X) pattern.

    An NC cross consists of two short diagonal wires sharing the same midpoint,
    like the terminator rendered for a no-connect pin.
    """
    nc_indices: set[int] = set()
    midpoints = [_wire_midpoint(w) for w in wires]
    tol = _TOUCH_TOLERANCE
    max_len_sq = (2 * _NC_MAX_HALF) ** 2

    for i in range(len(wires)):
        if not _is_diagonal(wires[i]) or _wire_length_sq(wires[i]) > max_len_sq:
            continue
        for j in range(i + 1, len(wires)):
            if not _is_diagonal(wires[j]) or _wire_length_sq(wires[j]) > max_len_sq:
                continue
            mx_i, my_i = midpoints[i]
            mx_j, my_j = midpoints[j]
            if abs(mx_i - mx_j) <= tol and abs(my_i - my_j) <= tol:
                nc_indices.add(i)
                nc_indices.add(j)
    return nc_indices


def _nc_cross_midpoints(wires: list[Line], nc_indices: set[int]) -> list[Point]:
    """Return the unique midpoints of all NC-cross pairs."""
    from schematika.core.geometry import Point as Pt

    seen: list[tuple[float, float]] = []
    result: list[Point] = []
    tol = _TOUCH_TOLERANCE
    for i in nc_indices:
        mx, my = _wire_midpoint(wires[i])
        if not any(abs(mx - ox) <= tol and abs(my - oy) <= tol for ox, oy in seen):
            seen.append((mx, my))
            result.append(Pt(mx, my))
    return result


def _text_at_port_position(text: Text, port_positions: list[Point]) -> bool:
    return any(_point_near(text.position, p) for p in port_positions)


def _text_is_nc_label(
    text: Text,
    wires: list[Line],
    nc_indices: set[int],
) -> bool:
    """True if text is an NC-terminator label placed near an NC-cross midpoint."""
    if not nc_indices:
        return False
    midpoints = _nc_cross_midpoints(wires, nc_indices)
    y_range = text.font_size * 3
    tol = _TOUCH_TOLERANCE
    return any(
        abs(text.position.x - mp.x) <= tol * 10
        and abs(text.position.y - mp.y) <= y_range
        for mp in midpoints
    )


# ---------------------------------------------------------------------------
# Page context
# ---------------------------------------------------------------------------


@dataclass
class _PageCtx:
    """Per-page data shared across all pair-check helpers."""

    page_title: str
    loc: FindingLocation
    outer_symbols: list[Symbol]
    sym_bboxes: list[tuple[float, float, float, float]]
    wires: list[Line]
    texts: list[Text]
    text_bboxes: list[tuple[float, float, float, float]]
    nc_wire_indices: set[int]
    port_positions: list[Point] = field(default_factory=list)

    def _finding(self, message: str) -> Finding:
        return Finding(
            code=CODE, severity=Severity.ERROR, message=message, location=self.loc
        )


# ---------------------------------------------------------------------------
# Page circuit builder
# ---------------------------------------------------------------------------


def _build_page_circuit(result: PCBBuildResult, page: Page) -> Circuit:
    """Render all blocks on a page and merge into a single Circuit."""
    circuit = Circuit()
    by_ref = {b.connector_ref: b for b in result.connector_blocks}
    mapping = result.mapping or SymbolMapping(symbols=(), connectors=(), power_nets=())

    for connector_ref, origin_x in page.placements:
        block = by_ref.get(connector_ref)
        if block is None:
            continue
        block_circuit = render_connector_block(
            block,
            mapping,
            origin_x_mm=origin_x,
            origin_y_mm=result.layout.page_top_margin_mm,
            layout=result.layout,
        )
        circuit = merge_circuits(circuit, block_circuit)

    return circuit


# ---------------------------------------------------------------------------
# Per-pair check helpers
# ---------------------------------------------------------------------------


def _check_symbol_pairs(ctx: _PageCtx) -> list[Finding]:
    findings: list[Finding] = []
    for i, s1 in enumerate(ctx.outer_symbols):
        for j, s2 in enumerate(ctx.outer_symbols[i + 1 :], start=i + 1):
            if _bboxes_overlap_strict(ctx.sym_bboxes[i], ctx.sym_bboxes[j]):
                findings.append(
                    ctx._finding(
                        f"Symbol '{s1.label}' overlaps symbol '{s2.label}'"
                        f" on page '{ctx.page_title}'"
                    )
                )
    return findings


def _check_text_pairs(ctx: _PageCtx) -> list[Finding]:
    findings: list[Finding] = []
    for i, t1 in enumerate(ctx.texts):
        for j, t2 in enumerate(ctx.texts[i + 1 :], start=i + 1):
            if _bboxes_overlap_strict(ctx.text_bboxes[i], ctx.text_bboxes[j]):
                findings.append(
                    ctx._finding(
                        f"Text '{t1.content[:30]}' overlaps"
                        f" text '{t2.content[:30]}'"
                        f" on page '{ctx.page_title}'"
                    )
                )
    return findings


def _check_wire_pairs(ctx: _PageCtx) -> list[Finding]:
    findings: list[Finding] = []
    for i, w1 in enumerate(ctx.wires):
        if i in ctx.nc_wire_indices:
            continue
        for j in range(i + 1, len(ctx.wires)):
            w2 = ctx.wires[j]
            if j in ctx.nc_wire_indices:
                continue
            if _wires_share_single_endpoint(w1, w2):
                continue
            if segments_intersect_strict(
                (w1.start, w1.end),
                (w2.start, w2.end),
                tolerance=_TOUCH_TOLERANCE,
            ):
                findings.append(
                    ctx._finding(f"Wire overlap on page '{ctx.page_title}'")
                )
    return findings


def _check_wire_symbol(ctx: _PageCtx) -> list[Finding]:
    findings: list[Finding] = []
    for i, wire in enumerate(ctx.wires):
        if i in ctx.nc_wire_indices:
            continue
        for sym, sbb in zip(ctx.outer_symbols, ctx.sym_bboxes, strict=True):
            if _wire_endpoint_at_symbol_port(wire, sym):
                continue
            if segment_intersects_bbox_interior(
                (wire.start, wire.end),
                sbb,
                tolerance=_TOUCH_TOLERANCE,
            ):
                findings.append(
                    ctx._finding(
                        f"Wire overlaps symbol '{sym.label}' on page '{ctx.page_title}'"
                    )
                )
    return findings


def _is_text_exempt(text: Text, ctx: _PageCtx) -> bool:
    return _text_at_port_position(text, ctx.port_positions) or _text_is_nc_label(
        text, ctx.wires, ctx.nc_wire_indices
    )


def _check_text_symbol(ctx: _PageCtx) -> list[Finding]:
    findings: list[Finding] = []
    for text, tbb in zip(ctx.texts, ctx.text_bboxes, strict=True):
        if _is_text_exempt(text, ctx):
            continue
        for sym, sbb in zip(ctx.outer_symbols, ctx.sym_bboxes, strict=True):
            if _bboxes_overlap_strict(tbb, sbb):
                findings.append(
                    ctx._finding(
                        f"Text '{text.content[:30]}' overlaps"
                        f" symbol '{sym.label}'"
                        f" on page '{ctx.page_title}'"
                    )
                )
    return findings


def _wire_terminates_at_text(wire: Line, text: Text) -> bool:
    """True if a wire endpoint is at (or very near) the text anchor position.

    A wire that terminates exactly at the text position is the standard
    'incoming wire → label' pattern and is not a real overlap.
    """
    tol = _TOUCH_TOLERANCE * 2  # slightly looser: stroke_width/2 causes ~0.125 mm drift
    tx, ty = text.position.x, text.position.y
    return any(
        abs(ep.x - tx) <= tol and abs(ep.y - ty) <= tol for ep in (wire.start, wire.end)
    )


def _check_text_wire(ctx: _PageCtx) -> list[Finding]:
    findings: list[Finding] = []
    for text, tbb in zip(ctx.texts, ctx.text_bboxes, strict=True):
        if _is_text_exempt(text, ctx):
            continue
        for i, wire in enumerate(ctx.wires):
            if i in ctx.nc_wire_indices:
                continue
            if _wire_terminates_at_text(wire, text):
                continue
            wbb = _wire_bbox(wire)
            if _bboxes_overlap_strict(tbb, wbb):
                findings.append(
                    ctx._finding(
                        f"Text '{text.content[:30]}' overlaps"
                        f" wire on page '{ctx.page_title}'"
                    )
                )
    return findings


# ---------------------------------------------------------------------------
# Main check
# ---------------------------------------------------------------------------


def check(
    result: PCBBuildResult,
    circuit: object = None,  # noqa: ARG001
    mapping: SymbolMapping | None = None,  # noqa: ARG001
) -> tuple[Finding, ...]:
    """Return ERROR for each geometric overlap on any rendered page.

    Args:
        result: PCBBuildResult from build().
        circuit: SKiDL circuit IR (unused).
        mapping: SymbolMapping config (unused).

    Returns:
        Tuple of ERROR Findings for overlapping element pairs.
    """
    findings: list[Finding] = []

    for page in result.pages:
        page_circuit = _build_page_circuit(result, page)
        outer_symbols: list[Symbol] = list(page_circuit.symbols)
        wires: list[Line] = [e for e in page_circuit.elements if isinstance(e, Line)]
        texts: list[Text] = [e for e in page_circuit.elements if isinstance(e, Text)]

        ctx = _PageCtx(
            page_title=page.title,
            loc=FindingLocation(page_title=page.title),
            outer_symbols=outer_symbols,
            sym_bboxes=[_symbol_bbox(s) for s in outer_symbols],
            wires=wires,
            texts=texts,
            text_bboxes=[text_bbox(t) for t in texts],
            nc_wire_indices=_classify_nc_cross_wires(wires),
            port_positions=_all_port_positions(outer_symbols),
        )

        findings += _check_symbol_pairs(ctx)
        findings += _check_text_pairs(ctx)
        findings += _check_wire_pairs(ctx)
        findings += _check_wire_symbol(ctx)
        findings += _check_text_symbol(ctx)
        findings += _check_text_wire(ctx)

    return tuple(findings)


CHECKS = (check,)
