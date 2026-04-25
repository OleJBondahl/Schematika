"""SVG schematic parser for the cad_parser tool.

Parses SVG files (typically exported from AutoCAD or KiCad) into the unified
SchematicData model using heuristic geometry analysis.  No external runtime
dependencies are required beyond the Python stdlib; ``svgpathtools`` is used
opportunistically when available for complex path geometry.

Because SVG exports lose all semantic data, this parser is inherently
best-effort: it extracts what can be inferred from geometry and text patterns.
"""

from __future__ import annotations

import logging
import math
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Any

from ..models import (
    ComponentInfo,
    Metadata,
    NetInfo,
    NetMember,
    Position,
    SchematicData,
    TerminalInfo,
    WireEndpoint,
    WireInfo,
    WireSegment,
)
from ..utils import normalize_component_type, positions_close

log = logging.getLogger(__name__)

# SVG namespace
_SVG_NS = "http://www.w3.org/2000/svg"
_NS = f"{{{_SVG_NS}}}"

# Heuristic thresholds (all in SVG user units / px)
_WIRE_TOLERANCE = 2.0  # endpoints this close are considered coincident
_LABEL_SNAP_DISTANCE = 30.0  # max perpendicular distance from label to nearest wire
_COMPONENT_SNAP = 10.0  # max distance to associate a wire endpoint with a component
_MIN_WIRE_LENGTH = 5.0  # shorter segments are ignored (noise)

# Component reference and wire label patterns
_REF_PATTERN = re.compile(r"^[A-Z]{1,3}\d+$")  # K1, Q3, M5, BT1
_WIRE_LABEL_PATTERN = re.compile(r"^(L\d+|N|PE|\d+)$")  # L1, N, PE, 400

# SVG transform parsing
_TRANSLATE_RE = re.compile(
    r"translate\(\s*([+-]?\d*\.?\d+)\s*,?\s*([+-]?\d*\.?\d+)?\s*\)"
)
_SCALE_RE = re.compile(r"scale\(\s*([+-]?\d*\.?\d+)\s*,?\s*([+-]?\d*\.?\d+)?\s*\)")


def _distance(a: Position, b: Position) -> float:
    return math.sqrt((b.x - a.x) ** 2 + (b.y - a.y) ** 2)


def _point_to_segment_distance(
    p: Position, seg_start: Position, seg_end: Position
) -> float:
    """Minimum Euclidean distance from point p to line segment."""
    dx = seg_end.x - seg_start.x
    dy = seg_end.y - seg_start.y
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq == 0.0:
        return _distance(p, seg_start)
    dot = (p.x - seg_start.x) * dx + (p.y - seg_start.y) * dy
    t = max(0.0, min(1.0, dot / seg_len_sq))
    proj = Position(x=seg_start.x + t * dx, y=seg_start.y + t * dy)
    return _distance(p, proj)


def _parse_float(value: str | None, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _parse_transform(transform: str | None) -> tuple[float, float, float, float]:
    """Parse an SVG transform attribute into (tx, ty, sx, sy).

    Only translate and uniform scale are handled.  Rotate is not supported
    (rare in CAD exports and hard to apply correctly without matrix math).
    Returns (0.0, 0.0, 1.0, 1.0) when the attribute is absent or unparseable.
    """
    if not transform:
        return 0.0, 0.0, 1.0, 1.0

    tx, ty, sx, sy = 0.0, 0.0, 1.0, 1.0

    m = _TRANSLATE_RE.search(transform)
    if m:
        tx = _parse_float(m.group(1))
        ty = _parse_float(m.group(2), 0.0)

    m = _SCALE_RE.search(transform)
    if m:
        sx = _parse_float(m.group(1), 1.0)
        sy = _parse_float(m.group(2), sx)

    return tx, ty, sx, sy


def _apply_transform(
    x: float, y: float, tx: float, ty: float, sx: float, sy: float
) -> Position:
    return Position(x=x * sx + tx, y=y * sy + ty)


def _compose_transforms(
    outer: tuple[float, float, float, float],
    inner: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    """Compose (tx_outer, ty_outer, sx_outer, sy_outer) with inner."""
    otx, oty, osx, osy = outer
    itx, ity, isx, isy = inner
    return (
        itx * osx + otx,
        ity * osy + oty,
        isx * osx,
        isy * osy,
    )


class SvgParser:
    """Parse an SVG schematic file into :class:`SchematicData`.

    The parser operates in four sequential phases:

    1. XML traversal — walk the element tree, collecting raw geometry
       and text with their absolute positions.
    2. Wire detection — classify line segments and polylines as potential
       wires; filter noise; group connected segments via union-find.
    3. Component assembly — detect component references from text patterns;
       optionally associate them with compact ``<g>`` groups.
    4. Connectivity — snap wire endpoints to component positions to fill
       ``from_endpoint`` / ``to_endpoint``; associate wire-label text with
       wire networks.
    """

    def parse(self, path: Path) -> SchematicData:
        log.debug("Opening SVG file: %s", path)
        try:
            tree = ET.parse(str(path))
        except ET.ParseError as exc:
            log.error("Failed to parse SVG file %s: %s", path, exc)
            raise

        root = tree.getroot()

        # Strip namespace from tag for easier matching in _tag()
        self._root = root

        raw_segments: list[tuple[Position, Position]] = []
        raw_texts: list[dict[str, Any]] = []
        raw_groups: list[dict[str, Any]] = []

        identity = (0.0, 0.0, 1.0, 1.0)
        self._walk(root, identity, raw_segments, raw_texts, raw_groups)

        # Filter degenerate segments
        segments = [
            (s, e) for s, e in raw_segments if _distance(s, e) >= _MIN_WIRE_LENGTH
        ]

        log.debug(
            "SVG raw: %d segments, %d texts, %d groups",
            len(segments),
            len(raw_texts),
            len(raw_groups),
        )

        components = self._build_components(raw_texts, raw_groups)
        wires = self._build_wires(segments, raw_texts, components)
        terminals = self._extract_terminals(components)
        nets = self._build_nets(wires)

        metadata = Metadata(
            source_format="svg",
            filename=path.name,
            pages=1,
        )

        log.info(
            "Parsed %s: %d components, %d wires, %d terminals, %d nets",
            path.name,
            len(components),
            len(wires),
            len(terminals),
            len(nets),
        )

        return SchematicData(
            metadata=metadata,
            components=components,
            wires=wires,
            terminals=terminals,
            nets=nets,
        )

    # ------------------------------------------------------------------
    # Phase 1 — XML traversal
    # ------------------------------------------------------------------

    def _local(self, tag: str) -> str:
        """Strip the SVG namespace prefix from a tag string."""
        if tag.startswith(_NS):
            return tag[len(_NS) :]
        return tag

    def _walk(
        self,
        element: ET.Element,
        parent_transform: tuple[float, float, float, float],
        segments: list[tuple[Position, Position]],
        texts: list[dict[str, Any]],
        groups: list[dict[str, Any]],
    ) -> None:
        """Recursively walk element tree, accumulating geometry."""
        local = self._local(element.tag)
        own_transform = _parse_transform(element.get("transform"))
        transform = _compose_transforms(parent_transform, own_transform)

        if local == "line":
            seg = self._parse_line(element, transform)
            if seg:
                segments.append(seg)

        elif local == "polyline":
            segs = self._parse_polyline(element, transform)
            segments.extend(segs)

        elif local == "path":
            segs = self._parse_path(element, transform)
            segments.extend(segs)

        elif local == "rect":
            # Rectangles may be symbol outlines — record as very short
            # degenerate geometry; they rarely represent wires, so skip.
            pass

        elif local == "text":
            text_item = self._parse_text(element, transform)
            if text_item:
                texts.append(text_item)

        elif local == "g":
            self._walk_group(element, transform, segments, texts, groups)

        else:
            # Unknown element — recurse into children
            for child in element:
                self._walk(child, transform, segments, texts, groups)

    def _walk_group(
        self,
        element: ET.Element,
        transform: tuple[float, float, float, float],
        segments: list[tuple[Position, Position]],
        texts: list[dict[str, Any]],
        groups: list[dict[str, Any]],
    ) -> None:
        """Handle a <g> element: collect child geometry and register as a group."""
        child_segs: list[tuple[Position, Position]] = []
        child_texts: list[dict[str, Any]] = []
        child_groups: list[dict[str, Any]] = []

        for child in element:
            self._walk(child, transform, child_segs, child_texts, child_groups)

        segments.extend(child_segs)
        texts.extend(child_texts)
        groups.extend(child_groups)

        if child_segs and child_texts:
            centroid = self._group_centroid(child_segs)
            groups.append(
                {
                    "centroid": centroid,
                    "texts": child_texts,
                    "segment_count": len(child_segs),
                }
            )

    def _parse_line(
        self, el: ET.Element, transform: tuple[float, float, float, float]
    ) -> tuple[Position, Position] | None:
        tx, ty, sx, sy = transform
        x1 = _parse_float(el.get("x1"))
        y1 = _parse_float(el.get("y1"))
        x2 = _parse_float(el.get("x2"))
        y2 = _parse_float(el.get("y2"))
        start = _apply_transform(x1, y1, tx, ty, sx, sy)
        end = _apply_transform(x2, y2, tx, ty, sx, sy)
        return start, end

    def _parse_polyline(
        self, el: ET.Element, transform: tuple[float, float, float, float]
    ) -> list[tuple[Position, Position]]:
        points_str = el.get("points", "")
        coords = [_parse_float(v) for v in re.split(r"[\s,]+", points_str.strip()) if v]
        if len(coords) < 4:
            return []
        tx, ty, sx, sy = transform
        positions = [
            _apply_transform(coords[i], coords[i + 1], tx, ty, sx, sy)
            for i in range(0, len(coords) - 1, 2)
        ]
        return list(zip(positions[:-1], positions[1:], strict=False))

    def _parse_path(
        self, el: ET.Element, transform: tuple[float, float, float, float]
    ) -> list[tuple[Position, Position]]:
        """Best-effort path parsing: extract M/L/H/V commands only.

        Complex curves (C, S, Q, A) are ignored — they are typically decorative
        in CAD exports, not wire runs.  Optionally delegates to svgpathtools
        when available for more accurate results.
        """
        d = el.get("d", "")
        if not d:
            return []

        import importlib.util

        if importlib.util.find_spec("svgpathtools") is not None:
            return self._parse_path_svgpathtools(d, transform)

        return self._parse_path_simple(d, transform)

    def _parse_path_svgpathtools(
        self, d: str, transform: tuple[float, float, float, float]
    ) -> list[tuple[Position, Position]]:
        """Parse path using svgpathtools for accurate geometry."""
        import svgpathtools  # noqa: PLC0415

        try:
            path = svgpathtools.parse_path(d)
        except Exception as exc:
            log.debug("svgpathtools failed to parse path: %s", exc)
            return []

        tx, ty, sx, sy = transform
        segments: list[tuple[Position, Position]] = []

        for segment in path:
            # Use start/end of each sub-segment as an approximation
            try:
                start_c = segment.start
                end_c = segment.end
                s = _apply_transform(start_c.real, start_c.imag, tx, ty, sx, sy)
                e = _apply_transform(end_c.real, end_c.imag, tx, ty, sx, sy)
                segments.append((s, e))
            except AttributeError:
                continue

        return segments

    def _parse_path_simple(
        self, d: str, transform: tuple[float, float, float, float]
    ) -> list[tuple[Position, Position]]:
        """Minimal M/L/H/V path command parser (no curves)."""
        tx, ty, sx, sy = transform
        segments: list[tuple[Position, Position]] = []
        tokens = re.findall(r"([MLHVZmlhvz]|[+-]?\d*\.?\d+(?:[eE][+-]?\d+)?)", d)

        cx, cy = 0.0, 0.0
        subpath_start_x, subpath_start_y = 0.0, 0.0
        cmd = "M"
        i = 0

        while i < len(tokens):
            tok = tokens[i]
            if tok.upper() in "MLHVZ":
                cmd = tok
                i += 1
                continue
            try:
                if cmd in ("Z", "z"):
                    prev = _apply_transform(cx, cy, tx, ty, sx, sy)
                    new = _apply_transform(
                        subpath_start_x, subpath_start_y, tx, ty, sx, sy
                    )
                    segments.append((prev, new))
                    cx, cy = subpath_start_x, subpath_start_y
                    i += 1
                elif cmd.isupper():
                    cx, cy, subpath_start_x, subpath_start_y, step = (
                        self._apply_abs_path_cmd(
                            cmd,
                            tokens,
                            i,
                            cx,
                            cy,
                            subpath_start_x,
                            subpath_start_y,
                            transform,
                            segments,
                        )
                    )
                    i += step
                else:
                    cx, cy, subpath_start_x, subpath_start_y, step = (
                        self._apply_rel_path_cmd(
                            cmd,
                            tokens,
                            i,
                            cx,
                            cy,
                            subpath_start_x,
                            subpath_start_y,
                            transform,
                            segments,
                        )
                    )
                    i += step
            except (IndexError, ValueError):
                i += 1

        return segments

    def _apply_abs_path_cmd(
        self,
        cmd: str,
        tokens: list[str],
        i: int,
        cx: float,
        cy: float,
        sx0: float,
        sy0: float,
        transform: tuple[float, float, float, float],
        segments: list[tuple[Position, Position]],
    ) -> tuple[float, float, float, float, int]:
        """Process one absolute path command.  Returns (cx, cy, sx0, sy0, consumed)."""
        tx, ty, sx, sy = transform
        if cmd in ("M", "L"):
            nx, ny = _parse_float(tokens[i]), _parse_float(tokens[i + 1])
            prev = _apply_transform(cx, cy, tx, ty, sx, sy)
            new = _apply_transform(nx, ny, tx, ty, sx, sy)
            if cmd == "L":
                segments.append((prev, new))
            else:
                sx0, sy0 = nx, ny
            return nx, ny, sx0, sy0, 2
        if cmd == "H":
            nx = _parse_float(tokens[i])
            prev = _apply_transform(cx, cy, tx, ty, sx, sy)
            segments.append((prev, _apply_transform(nx, cy, tx, ty, sx, sy)))
            return nx, cy, sx0, sy0, 1
        if cmd == "V":
            ny = _parse_float(tokens[i])
            prev = _apply_transform(cx, cy, tx, ty, sx, sy)
            segments.append((prev, _apply_transform(cx, ny, tx, ty, sx, sy)))
            return cx, ny, sx0, sy0, 1
        return cx, cy, sx0, sy0, 1  # unknown — skip one token

    def _apply_rel_path_cmd(
        self,
        cmd: str,
        tokens: list[str],
        i: int,
        cx: float,
        cy: float,
        sx0: float,
        sy0: float,
        transform: tuple[float, float, float, float],
        segments: list[tuple[Position, Position]],
    ) -> tuple[float, float, float, float, int]:
        """Process one relative path command.  Returns (cx, cy, sx0, sy0, consumed)."""
        tx, ty, sx, sy = transform
        if cmd in ("m", "l"):
            dx, dy = _parse_float(tokens[i]), _parse_float(tokens[i + 1])
            prev = _apply_transform(cx, cy, tx, ty, sx, sy)
            cx, cy = cx + dx, cy + dy
            new = _apply_transform(cx, cy, tx, ty, sx, sy)
            if cmd == "l":
                segments.append((prev, new))
            else:
                sx0, sy0 = cx, cy
            return cx, cy, sx0, sy0, 2
        if cmd == "h":
            nx = cx + _parse_float(tokens[i])
            prev = _apply_transform(cx, cy, tx, ty, sx, sy)
            segments.append((prev, _apply_transform(nx, cy, tx, ty, sx, sy)))
            return nx, cy, sx0, sy0, 1
        if cmd == "v":
            ny = cy + _parse_float(tokens[i])
            prev = _apply_transform(cx, cy, tx, ty, sx, sy)
            segments.append((prev, _apply_transform(cx, ny, tx, ty, sx, sy)))
            return cx, ny, sx0, sy0, 1
        return cx, cy, sx0, sy0, 1  # unknown — skip one token

    def _parse_text(
        self, el: ET.Element, transform: tuple[float, float, float, float]
    ) -> dict[str, Any] | None:
        """Extract text content and position from a <text> element."""
        tx, ty, sx, sy = transform

        # Position: prefer x/y attributes; may also come from transform
        x = _parse_float(el.get("x"))
        y = _parse_float(el.get("y"))
        pos = _apply_transform(x, y, tx, ty, sx, sy)

        # Text content: may be directly in el.text or nested in <tspan>
        parts: list[str] = []
        if el.text and el.text.strip():
            parts.append(el.text.strip())
        for child in el:
            local = self._local(child.tag)
            if local == "tspan":
                t = (child.text or "").strip()
                if t:
                    parts.append(t)
            if child.tail and child.tail.strip():
                parts.append(child.tail.strip())

        content = " ".join(parts).strip()
        if not content:
            return None

        return {"content": content, "position": pos}

    # ------------------------------------------------------------------
    # Phase 2 — Wire network building
    # ------------------------------------------------------------------

    def _build_wires(
        self,
        segments: list[tuple[Position, Position]],
        texts: list[dict[str, Any]],
        components: list[ComponentInfo],
    ) -> list[WireInfo]:
        if not segments:
            log.warning("No wire segments found in SVG")
            return []

        networks = self._union_find_networks(segments)
        wire_labels = [t for t in texts if _WIRE_LABEL_PATTERN.match(t["content"])]
        network_wireno = self._map_labels_to_networks(wire_labels, networks, segments)

        comp_positions: list[tuple[str, Position]] = [
            (comp.tag, comp.position) for comp in components
        ]

        wires: list[WireInfo] = []
        for wire_idx, (root, seg_indices) in enumerate(networks.items()):
            wire_number = network_wireno.get(root, "")
            wire_segments = [
                WireSegment(start=segments[i][0], end=segments[i][1])
                for i in seg_indices
            ]

            endpoints = self._find_connected_endpoints(
                seg_indices, segments, comp_positions
            )
            from_ep = endpoints[0] if len(endpoints) > 0 else None
            to_ep = endpoints[1] if len(endpoints) > 1 else None

            if len(endpoints) > 2:
                log.debug(
                    "Wire %d has %d connection points; using first two",
                    wire_idx,
                    len(endpoints),
                )

            wires.append(
                WireInfo(
                    id=f"W{wire_idx + 1}",
                    wire_number=wire_number,
                    from_endpoint=from_ep,
                    to_endpoint=to_ep,
                    segments=wire_segments,
                )
            )

        log.debug("Built %d wire networks", len(wires))
        return wires

    def _union_find_networks(
        self, segments: list[tuple[Position, Position]]
    ) -> dict[int, list[int]]:
        """Group segments into connected networks via union-find."""
        parent = list(range(len(segments)))

        def find(i: int) -> int:
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        def union(i: int, j: int) -> None:
            ri, rj = find(i), find(j)
            if ri != rj:
                parent[ri] = rj

        for i in range(len(segments)):
            si, ei = segments[i]
            for j in range(i + 1, len(segments)):
                sj, ej = segments[j]
                if (
                    positions_close(si, sj, _WIRE_TOLERANCE)
                    or positions_close(si, ej, _WIRE_TOLERANCE)
                    or positions_close(ei, sj, _WIRE_TOLERANCE)
                    or positions_close(ei, ej, _WIRE_TOLERANCE)
                ):
                    union(i, j)

        networks: dict[int, list[int]] = defaultdict(list)
        for i in range(len(segments)):
            networks[find(i)].append(i)
        return networks

    def _map_labels_to_networks(
        self,
        wire_labels: list[dict[str, Any]],
        networks: dict[int, list[int]],
        segments: list[tuple[Position, Position]],
    ) -> dict[int, str]:
        """Associate wire-label text positions with the nearest network.

        Uses point-to-segment distance so labels placed above or beside the
        middle of a wire are correctly associated even when far from either
        endpoint.
        """
        network_wireno: dict[int, str] = {}
        for label in wire_labels:
            label_pos: Position = label["position"]
            best_root: int | None = None
            best_dist = float("inf")

            for root, seg_indices in networks.items():
                for idx in seg_indices:
                    seg = segments[idx]
                    d = _point_to_segment_distance(label_pos, seg[0], seg[1])
                    if d < best_dist:
                        best_dist = d
                        best_root = root

            if best_root is None or best_dist > _LABEL_SNAP_DISTANCE:
                log.debug(
                    "Wire label %r at (%.1f, %.1f) could not be snapped "
                    "(nearest dist=%.1f)",
                    label["content"],
                    label_pos.x,
                    label_pos.y,
                    best_dist,
                )
                continue

            existing = network_wireno.get(best_root)
            if existing and existing != label["content"]:
                log.warning(
                    "Network %d already has wire number %r; ignoring %r",
                    best_root,
                    existing,
                    label["content"],
                )
            else:
                network_wireno[best_root] = label["content"]

        return network_wireno

    def _find_connected_endpoints(
        self,
        seg_indices: list[int],
        segments: list[tuple[Position, Position]],
        comp_positions: list[tuple[str, Position]],
    ) -> list[WireEndpoint]:
        all_pts: list[Position] = []
        for idx in seg_indices:
            all_pts.extend(segments[idx])

        endpoints: list[WireEndpoint] = []
        seen: set[str] = set()

        for pt in all_pts:
            for tag, comp_pos in comp_positions:
                if positions_close(pt, comp_pos, _COMPONENT_SNAP):
                    if tag not in seen:
                        seen.add(tag)
                        # Pin is unknown from SVG geometry alone
                        endpoints.append(WireEndpoint(component=tag, pin="?"))

        return endpoints

    # ------------------------------------------------------------------
    # Phase 3 — Component assembly
    # ------------------------------------------------------------------

    def _build_components(
        self,
        texts: list[dict[str, Any]],
        groups: list[dict[str, Any]],
    ) -> list[ComponentInfo]:
        """Detect component references from text and group geometry."""
        ref_texts = [
            t
            for t in texts
            if _REF_PATTERN.match(t["content"])
            and not _WIRE_LABEL_PATTERN.match(t["content"])
        ]

        if not ref_texts:
            log.warning("No component references found in SVG text elements")
            return []

        # Build a lookup: for each ref text, check whether it falls inside a group
        group_lookup = self._build_group_lookup(groups)

        components: list[ComponentInfo] = []
        seen_tags: set[str] = set()

        for ref in ref_texts:
            tag: str = ref["content"]
            if tag in seen_tags:
                log.debug("Duplicate component reference %r — skipping", tag)
                continue
            seen_tags.add(tag)

            pos: Position = ref["position"]

            # If the reference sits inside a known group, use the group centroid
            group = group_lookup.get(tag)
            if group:
                pos = group["centroid"]

            # Extract the alphabetic prefix to infer component type
            prefix_m = re.match(r"^([A-Z]{1,3})", tag)
            prefix = prefix_m.group(1) if prefix_m else ""
            comp_type = normalize_component_type(prefix)

            log.debug(
                "Component %r at (%.1f, %.1f) type=%r",
                tag,
                pos.x,
                pos.y,
                comp_type,
            )

            components.append(
                ComponentInfo(
                    tag=tag,
                    type=comp_type,
                    family="",
                    description="",
                    position=pos,
                    terminals={},
                    attributes={"_source": "svg_text"},
                )
            )

        log.debug("Assembled %d components from SVG", len(components))
        return components

    def _build_group_lookup(
        self, groups: list[dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        """Return a mapping of component tag → group info for groups whose
        text contains exactly one reference pattern."""
        lookup: dict[str, dict[str, Any]] = {}
        for group in groups:
            ref_texts_in_group = [
                t for t in group["texts"] if _REF_PATTERN.match(t["content"])
            ]
            if len(ref_texts_in_group) == 1:
                tag = ref_texts_in_group[0]["content"]
                lookup[tag] = group
        return lookup

    def _group_centroid(self, segments: list[tuple[Position, Position]]) -> Position:
        if not segments:
            return Position(0.0, 0.0)
        xs = [p.x for seg in segments for p in seg]
        ys = [p.y for seg in segments for p in seg]
        return Position(x=sum(xs) / len(xs), y=sum(ys) / len(ys))

    # ------------------------------------------------------------------
    # Phase 4 — Terminals and nets
    # ------------------------------------------------------------------

    def _extract_terminals(self, components: list[ComponentInfo]) -> list[TerminalInfo]:
        """Components whose prefix is X or XT are treated as terminal strips."""
        terminals: list[TerminalInfo] = []
        for comp in components:
            prefix_m = re.match(r"^([A-Z]{1,3})", comp.tag)
            prefix = prefix_m.group(1) if prefix_m else ""
            if prefix not in ("X", "XT"):
                continue
            terminals.append(
                TerminalInfo(
                    strip=comp.tag,
                    pin=comp.tag,
                    description=comp.description,
                    wire="",
                )
            )
        log.debug("Extracted %d terminal entries from SVG", len(terminals))
        return terminals

    def _build_nets(self, wires: list[WireInfo]) -> list[NetInfo]:
        """Group wires by wire number to build NetInfo records."""
        net_members: dict[str, set[tuple[str, str]]] = defaultdict(set)

        for wire in wires:
            wn = wire.wire_number
            if not wn:
                continue
            if wire.from_endpoint:
                net_members[wn].add(
                    (wire.from_endpoint.component, wire.from_endpoint.pin)
                )
            if wire.to_endpoint:
                net_members[wn].add((wire.to_endpoint.component, wire.to_endpoint.pin))

        nets: list[NetInfo] = []
        for name, members_set in sorted(net_members.items()):
            members = [
                NetMember(component=comp, pin=pin) for comp, pin in sorted(members_set)
            ]
            nets.append(NetInfo(name=name, members=members))

        log.debug("Built %d nets from SVG", len(nets))
        return nets
