"""AutoCAD Electrical DXF parser for the cad_parser tool.

Parses DXF files produced by AutoCAD Electrical into the unified SchematicData
model.  Requires the ``ezdxf`` package at runtime; an ImportError is raised on
first use if it is not installed.
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING

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

if TYPE_CHECKING:
    import ezdxf  # noqa: F401 — only for type hints

log = logging.getLogger(__name__)

# Tolerance (drawing units) for treating two endpoints as coincident.
_WIRE_TOLERANCE = 0.5
# Heuristic max distance (drawing units) to associate a wire-number label
# with a network.
_LABEL_SNAP_DISTANCE = 5.0


def _distance(a: Position, b: Position) -> float:
    return math.sqrt((b.x - a.x) ** 2 + (b.y - a.y) ** 2)


class AutocadParser:
    """Parse an AutoCAD Electrical DXF file into :class:`SchematicData`."""

    def parse(self, path: Path) -> SchematicData:
        import ezdxf  # noqa: PLC0415 — lazy import; raises ImportError if missing

        log.debug("Opening DXF file: %s", path)
        try:
            doc = ezdxf.readfile(str(path))
        except Exception as exc:
            log.error("Failed to open DXF file %s: %s", path, exc)
            raise

        msp = doc.modelspace()

        components = self._extract_components(msp)
        wire_labels = self._extract_wire_labels(msp)
        lines = self._extract_lines(msp)

        wires = self._build_wires(lines, wire_labels, components)
        terminals = self._extract_terminals(components)
        nets = self._build_nets(wires, components)

        metadata = Metadata(
            source_format="autocad_dxf",
            filename=path.name,
            pages=1,  # DXF modelspace = one logical page
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
    # Component extraction
    # ------------------------------------------------------------------

    def _extract_components(self, msp) -> list[ComponentInfo]:
        components: list[ComponentInfo] = []

        for insert in msp.query("INSERT"):
            attribs = {a.dxf.tag: a.dxf.text for a in insert.attribs}

            if "TAG1" not in attribs:
                continue

            tag = attribs.get("TAG1", "").strip()
            if not tag:
                log.debug("Skipping INSERT with empty TAG1 at %s", insert.dxf.insert)
                continue

            block_name: str = insert.dxf.name or ""
            family: str = attribs.get("FAMILY", "").strip()
            comp_type = normalize_component_type(family, block_name)

            desc_parts = [
                attribs.get("DESC1", ""),
                attribs.get("DESC2", ""),
                attribs.get("DESC3", ""),
            ]
            description = " ".join(p.strip() for p in desc_parts if p.strip())

            pos = insert.dxf.insert
            position = Position(x=float(pos.x), y=float(pos.y))

            terminals: dict[str, str] = {}
            extra_attribs: dict[str, str] = {}
            reserved = {"TAG1", "FAMILY", "DESC1", "DESC2", "DESC3"}

            for key, value in attribs.items():
                if key.startswith("TERM"):
                    terminals[key] = value
                elif key not in reserved:
                    extra_attribs[key] = value

            extra_attribs["_block_name"] = block_name

            components.append(
                ComponentInfo(
                    tag=tag,
                    type=comp_type,
                    family=family,
                    description=description,
                    position=position,
                    terminals=terminals,
                    attributes=extra_attribs,
                )
            )

        log.debug("Extracted %d components", len(components))
        return components

    # ------------------------------------------------------------------
    # Wire number label extraction
    # ------------------------------------------------------------------

    def _extract_wire_labels(self, msp) -> list[dict]:
        """Return a list of dicts with keys ``wireno`` and ``position``."""
        labels: list[dict] = []

        for insert in msp.query("INSERT"):
            block_name: str = insert.dxf.name or ""
            attribs = {a.dxf.tag: a.dxf.text for a in insert.attribs}

            wireno = attribs.get("WIRENO", "").strip()
            if not wireno and "WD_WN" not in block_name.upper():
                continue
            if not wireno:
                log.debug("Wire-number block %r has empty WIRENO", block_name)
                continue

            pos = insert.dxf.insert
            labels.append(
                {
                    "wireno": wireno,
                    "position": Position(x=float(pos.x), y=float(pos.y)),
                }
            )

        log.debug("Extracted %d wire number labels", len(labels))
        return labels

    # ------------------------------------------------------------------
    # LINE entity extraction
    # ------------------------------------------------------------------

    def _extract_lines(self, msp) -> list[tuple[Position, Position]]:
        segments: list[tuple[Position, Position]] = []

        for line in msp.query("LINE"):
            start = line.dxf.start
            end = line.dxf.end
            segments.append(
                (
                    Position(x=float(start.x), y=float(start.y)),
                    Position(x=float(end.x), y=float(end.y)),
                )
            )

        log.debug("Extracted %d LINE entities", len(segments))
        return segments

    # ------------------------------------------------------------------
    # Wire network building (union-find on shared endpoints)
    # ------------------------------------------------------------------

    def _union_find_networks(
        self, lines: list[tuple[Position, Position]]
    ) -> dict[int, list[int]]:
        """Return a mapping of root → [segment indices] via union-find."""
        parent = list(range(len(lines)))

        def find(i: int) -> int:
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        def union(i: int, j: int) -> None:
            ri, rj = find(i), find(j)
            if ri != rj:
                parent[ri] = rj

        for i in range(len(lines)):
            si, ei = lines[i]
            for j in range(i + 1, len(lines)):
                sj, ej = lines[j]
                if (
                    positions_close(si, sj, _WIRE_TOLERANCE)
                    or positions_close(si, ej, _WIRE_TOLERANCE)
                    or positions_close(ei, sj, _WIRE_TOLERANCE)
                    or positions_close(ei, ej, _WIRE_TOLERANCE)
                ):
                    union(i, j)

        networks: dict[int, list[int]] = defaultdict(list)
        for i in range(len(lines)):
            networks[find(i)].append(i)
        return networks

    def _map_labels_to_networks(
        self,
        wire_labels: list[dict],
        networks: dict[int, list[int]],
        lines: list[tuple[Position, Position]],
    ) -> dict[int, str]:
        """Return a mapping of network root → wire number string."""

        def all_endpoints(seg_indices: list[int]) -> list[Position]:
            pts: list[Position] = []
            for idx in seg_indices:
                pts.extend(lines[idx])
            return pts

        network_wireno: dict[int, str] = {}
        for label in wire_labels:
            label_pos: Position = label["position"]
            best_root: int | None = None
            best_dist = float("inf")

            for root, seg_indices in networks.items():
                for pt in all_endpoints(seg_indices):
                    d = _distance(label_pos, pt)
                    if d < best_dist:
                        best_dist = d
                        best_root = root

            if best_root is None or best_dist > _LABEL_SNAP_DISTANCE:
                continue

            existing = network_wireno.get(best_root)
            if existing and existing != label["wireno"]:
                log.warning(
                    "Network %d already has wire number %r; ignoring %r",
                    best_root,
                    existing,
                    label["wireno"],
                )
            else:
                network_wireno[best_root] = label["wireno"]

        return network_wireno

    def _find_connected_endpoints(
        self,
        seg_indices: list[int],
        lines: list[tuple[Position, Position]],
        comp_pins: list[tuple[str, str, Position]],
    ) -> list[WireEndpoint]:
        endpoints: list[WireEndpoint] = []
        seen: set[tuple[str, str]] = set()

        all_pts: list[Position] = []
        for idx in seg_indices:
            all_pts.extend(lines[idx])

        for pt in all_pts:
            for tag, pin, comp_pos in comp_pins:
                if positions_close(pt, comp_pos, _WIRE_TOLERANCE * 4):
                    key = (tag, pin)
                    if key not in seen:
                        seen.add(key)
                        endpoints.append(WireEndpoint(component=tag, pin=pin))
        return endpoints

    def _build_wires(
        self,
        lines: list[tuple[Position, Position]],
        wire_labels: list[dict],
        components: list[ComponentInfo],
    ) -> list[WireInfo]:
        """Group LINE segments into wire networks and create WireInfo objects."""
        if not lines:
            return []

        networks = self._union_find_networks(lines)
        network_wireno = self._map_labels_to_networks(wire_labels, networks, lines)

        comp_pins: list[tuple[str, str, Position]] = []
        for comp in components:
            for _, pin_value in comp.terminals.items():
                comp_pins.append((comp.tag, pin_value, comp.position))

        wires: list[WireInfo] = []
        for wire_idx, (root, seg_indices) in enumerate(networks.items()):
            wire_number = network_wireno.get(root, "")
            segments = [
                WireSegment(start=lines[i][0], end=lines[i][1]) for i in seg_indices
            ]

            endpoints = self._find_connected_endpoints(seg_indices, lines, comp_pins)
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
                    segments=segments,
                )
            )

        log.debug("Built %d wire networks", len(wires))
        return wires

    # ------------------------------------------------------------------
    # Terminal strip extraction
    # ------------------------------------------------------------------

    def _extract_terminals(self, components: list[ComponentInfo]) -> list[TerminalInfo]:
        terminals: list[TerminalInfo] = []

        for comp in components:
            family_upper = comp.family.upper()
            block_upper = comp.attributes.get("_block_name", "").upper()
            is_terminal = (
                family_upper == "TS"
                or "TERMINAL" in family_upper
                or "TERMINAL" in block_upper
            )
            if not is_terminal:
                continue

            strip = comp.attributes.get("WD_1_TAGSTRIP", comp.tag)
            wireno = comp.attributes.get("WIRENO", "")

            if comp.terminals:
                for _, pin_value in comp.terminals.items():
                    terminals.append(
                        TerminalInfo(
                            strip=strip,
                            pin=pin_value,
                            description=comp.description,
                            wire=wireno,
                        )
                    )
            else:
                terminals.append(
                    TerminalInfo(
                        strip=strip,
                        pin=comp.tag,
                        description=comp.description,
                        wire=wireno,
                    )
                )

        log.debug("Extracted %d terminal entries", len(terminals))
        return terminals

    # ------------------------------------------------------------------
    # Net building
    # ------------------------------------------------------------------

    def _build_nets(
        self, wires: list[WireInfo], components: list[ComponentInfo]
    ) -> list[NetInfo]:
        """Group WireInfo objects by wire number to create NetInfo records."""
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

        log.debug("Built %d nets", len(nets))
        return nets
