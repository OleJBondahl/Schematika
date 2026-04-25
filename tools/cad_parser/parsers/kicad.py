"""KiCad schematic parser for the cad_parser tool.

Parses ``.kicad_sch`` files produced by KiCad into the unified SchematicData
model.  Requires the ``kiutils`` package at runtime; an ImportError is raised
on first use if it is not installed.
"""

from __future__ import annotations

import logging
import math
import re
import xml.etree.ElementTree as ET
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
from ..utils import positions_close

if TYPE_CHECKING:
    pass  # kiutils types only used at runtime

log = logging.getLogger(__name__)

# Tolerance in schematic coordinate units for coincident endpoint detection.
_WIRE_TOLERANCE = 0.5
# Max distance to snap a net label onto a wire network.
_LABEL_SNAP_DISTANCE = 5.0

# Mapping from KiCad reference prefix to generic component type.
KICAD_REF_TYPE_MAP: dict[str, str] = {
    "R": "resistor",
    "C": "capacitor",
    "L": "inductor",
    "D": "diode",
    "Q": "transistor",
    "U": "ic",
    "J": "connector",
    "X": "connector",
    "P": "connector",
    "K": "relay",
    "M": "motor",
    "F": "fuse",
    "S": "switch",
    "T": "transformer",
    "BT": "battery",
}

# Library identifier substrings → component type (checked case-insensitively).
_LIBID_TYPE_MAP: list[tuple[str, str]] = [
    ("connector", "connector"),
    ("terminal", "connector"),
    ("relay", "relay"),
    ("motor", "motor"),
    ("fuse", "fuse"),
    ("switch", "switch"),
    ("transistor", "transistor"),
    ("diode", "diode"),
    ("capacitor", "capacitor"),
    ("resistor", "resistor"),
    ("inductor", "inductor"),
    ("transformer", "transformer"),
    ("battery", "battery"),
]

# Reference prefixes that indicate a terminal block / connector.
_TERMINAL_REF_PREFIXES = ("J", "X", "P")


def _ref_prefix(ref: str) -> str:
    """Return the alphabetic prefix of a reference designator (e.g. 'K' from 'K1')."""
    m = re.match(r"^([A-Za-z]+)", ref)
    return m.group(1).upper() if m else ""


def _type_from_ref_and_libid(ref: str, lib_id: str) -> str:
    """Derive a generic component type from the reference and library identifier."""
    prefix = _ref_prefix(ref)
    if prefix in KICAD_REF_TYPE_MAP:
        return KICAD_REF_TYPE_MAP[prefix]
    # Fall back to library identifier substring match.
    lib_lower = lib_id.lower()
    for substring, ctype in _LIBID_TYPE_MAP:
        if substring in lib_lower:
            return ctype
    return "unknown"


def _safe_property(symbol, name: str) -> str | None:
    """Return a symbol property value, or None if absent."""
    try:
        prop = symbol.property(name)
        return prop.value if prop is not None else None
    except Exception:
        return None


class KicadParser:
    """Parse a KiCad ``.kicad_sch`` file into :class:`SchematicData`."""

    def parse(self, path: Path) -> SchematicData:
        from kiutils.schematic import Schematic  # noqa: PLC0415 — lazy import

        log.debug("Opening KiCad schematic: %s", path)
        try:
            sch = Schematic.from_file(str(path))
        except Exception as exc:
            log.error("Failed to open KiCad schematic %s: %s", path, exc)
            raise

        components = self._extract_components(sch)
        raw_segments = self._extract_wire_segments(sch)
        net_labels = self._extract_net_labels(sch)

        wires = self._build_wires(raw_segments, net_labels, components)
        terminals = self._extract_terminals(components)

        # Optionally enrich nets from a sibling XML netlist export.
        nets = self._load_netlist_xml(path, components)
        if not nets:
            nets = self._build_nets_from_wires(wires)

        metadata = Metadata(
            source_format="kicad_sch",
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
    # Component extraction
    # ------------------------------------------------------------------

    def _extract_components(self, sch) -> list[ComponentInfo]:
        components: list[ComponentInfo] = []

        for symbol in sch.schematicSymbols:
            ref = _safe_property(symbol, "Reference")
            if ref is None:
                log.debug("Symbol with no Reference property; skipping")
                continue
            ref = ref.strip()
            # Skip power symbols (reference starts with '#') and unplaced
            # symbols whose reference ends with '?' (unfilled template).
            if ref.startswith("#") or ref.endswith("?"):
                log.debug("Skipping non-component reference %r", ref)
                continue

            value = _safe_property(symbol, "Value") or ""
            lib_id: str = getattr(symbol, "libraryIdentifier", "") or ""
            description = _safe_property(symbol, "Description") or ""

            comp_type = _type_from_ref_and_libid(ref, lib_id)

            pos_obj = getattr(symbol, "position", None)
            if pos_obj is not None:
                position = Position(x=float(pos_obj.X), y=float(pos_obj.Y))
            else:
                position = Position(x=0.0, y=0.0)

            # Collect all non-reserved properties into attributes.
            reserved = {"Reference", "Value", "Description"}
            attributes: dict[str, str] = {}
            try:
                all_props = symbol.properties
            except AttributeError:
                all_props = []
            for prop in all_props:
                name = getattr(prop, "key", None) or getattr(prop, "name", None)
                val = getattr(prop, "value", "")
                if name and name not in reserved:
                    attributes[str(name)] = str(val) if val is not None else ""

            attributes["_lib_id"] = lib_id
            attributes["_value"] = value

            components.append(
                ComponentInfo(
                    tag=ref,
                    type=comp_type,
                    family=lib_id,
                    description=description,
                    position=position,
                    terminals={},
                    attributes=attributes,
                )
            )

        log.debug("Extracted %d components", len(components))
        return components

    # ------------------------------------------------------------------
    # Wire segment extraction
    # ------------------------------------------------------------------

    def _extract_wire_segments(self, sch) -> list[tuple[Position, Position]]:
        segments: list[tuple[Position, Position]] = []

        wires = getattr(sch, "wires", []) or []
        for wire in wires:
            try:
                sp = wire.startPoint
                ep = wire.endPoint
                segments.append(
                    (
                        Position(x=float(sp.X), y=float(sp.Y)),
                        Position(x=float(ep.X), y=float(ep.Y)),
                    )
                )
            except AttributeError as exc:
                log.debug("Skipping malformed wire: %s", exc)

        log.debug("Extracted %d wire segments", len(segments))
        return segments

    # ------------------------------------------------------------------
    # Net label extraction
    # ------------------------------------------------------------------

    def _extract_net_labels(self, sch) -> list[dict]:
        """Return list of dicts with keys ``name`` and ``position``."""
        labels: list[dict] = []

        for attr in ("labels", "globalLabels", "netLabels"):
            for lbl in getattr(sch, attr, []) or []:
                text = getattr(lbl, "text", None) or getattr(lbl, "name", None)
                if not text:
                    continue
                pos_obj = getattr(lbl, "position", None)
                if pos_obj is None:
                    continue
                try:
                    labels.append(
                        {
                            "name": str(text).strip(),
                            "position": Position(
                                x=float(pos_obj.X), y=float(pos_obj.Y)
                            ),
                        }
                    )
                except AttributeError as exc:
                    log.debug("Skipping malformed label: %s", exc)

        log.debug("Extracted %d net labels", len(labels))
        return labels

    # ------------------------------------------------------------------
    # Wire network building (union-find on shared endpoints)
    # ------------------------------------------------------------------

    def _union_find_networks(
        self, segments: list[tuple[Position, Position]]
    ) -> dict[int, list[int]]:
        """Group wire segment indices into connected networks via union-find."""
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
        net_labels: list[dict],
        networks: dict[int, list[int]],
        segments: list[tuple[Position, Position]],
    ) -> dict[int, str]:
        """Return a mapping of network root → net name string."""

        def all_endpoints(seg_indices: list[int]) -> list[Position]:
            pts: list[Position] = []
            for idx in seg_indices:
                pts.extend(segments[idx])
            return pts

        network_name: dict[int, str] = {}
        for label in net_labels:
            label_pos: Position = label["position"]
            best_root: int | None = None
            best_dist = float("inf")

            for root, seg_indices in networks.items():
                for pt in all_endpoints(seg_indices):
                    d = math.sqrt((pt.x - label_pos.x) ** 2 + (pt.y - label_pos.y) ** 2)
                    if d < best_dist:
                        best_dist = d
                        best_root = root

            if best_root is None or best_dist > _LABEL_SNAP_DISTANCE:
                continue

            existing = network_name.get(best_root)
            if existing and existing != label["name"]:
                log.warning(
                    "Network %d already has name %r; ignoring %r",
                    best_root,
                    existing,
                    label["name"],
                )
            else:
                network_name[best_root] = label["name"]

        return network_name

    def _find_connected_endpoints(
        self,
        seg_indices: list[int],
        segments: list[tuple[Position, Position]],
        comp_pins: list[tuple[str, str, Position]],
    ) -> list[WireEndpoint]:
        endpoints: list[WireEndpoint] = []
        seen: set[tuple[str, str]] = set()

        all_pts: list[Position] = []
        for idx in seg_indices:
            all_pts.extend(segments[idx])

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
        segments: list[tuple[Position, Position]],
        net_labels: list[dict],
        components: list[ComponentInfo],
    ) -> list[WireInfo]:
        """Group wire segments into networks and create WireInfo objects."""
        if not segments:
            return []

        networks = self._union_find_networks(segments)
        network_name = self._map_labels_to_networks(net_labels, networks, segments)

        # Use component position as a proxy for pin positions (coarse).
        comp_pins: list[tuple[str, str, Position]] = []
        for comp in components:
            if comp.terminals:
                for _pin_key, pin_value in comp.terminals.items():
                    comp_pins.append((comp.tag, pin_value, comp.position))
            else:
                comp_pins.append((comp.tag, "1", comp.position))

        wires: list[WireInfo] = []
        for wire_idx, (root, seg_indices) in enumerate(networks.items()):
            wire_number = network_name.get(root, "")
            wire_segments = [
                WireSegment(start=segments[i][0], end=segments[i][1])
                for i in seg_indices
            ]

            endpoints = self._find_connected_endpoints(seg_indices, segments, comp_pins)
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

    # ------------------------------------------------------------------
    # Terminal extraction
    # ------------------------------------------------------------------

    def _extract_terminals(self, components: list[ComponentInfo]) -> list[TerminalInfo]:
        terminals: list[TerminalInfo] = []

        for comp in components:
            prefix = _ref_prefix(comp.tag)
            lib_lower = comp.family.lower()
            is_terminal = prefix in _TERMINAL_REF_PREFIXES or any(
                kw in lib_lower for kw in ("connector", "terminal")
            )
            if not is_terminal:
                continue

            # Strip: use ref prefix + numeric part (e.g. "J1" → strip "J", pin "1")
            m = re.match(r"^([A-Za-z]+)(\d+)$", comp.tag)
            if m:
                strip = m.group(1)
                pin = m.group(2)
            else:
                strip = comp.tag
                pin = "1"

            terminals.append(
                TerminalInfo(
                    strip=strip,
                    pin=pin,
                    description=comp.description,
                    wire="",
                )
            )

        log.debug("Extracted %d terminal entries", len(terminals))
        return terminals

    # ------------------------------------------------------------------
    # Net building from wires (fallback when no XML netlist)
    # ------------------------------------------------------------------

    def _build_nets_from_wires(self, wires: list[WireInfo]) -> list[NetInfo]:
        """Group WireInfo objects by wire number / net name into NetInfo records."""
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

        log.debug("Built %d nets from wires", len(nets))
        return nets

    # ------------------------------------------------------------------
    # Optional XML netlist parsing
    # ------------------------------------------------------------------

    def _load_netlist_xml(
        self, path: Path, components: list[ComponentInfo]
    ) -> list[NetInfo]:
        """Parse a KiCad-exported XML netlist alongside the schematic, if present.

        Returns a list of :class:`NetInfo` objects, or an empty list if no
        netlist file is found or parsing fails.
        """
        xml_path = path.with_suffix(".xml")
        if not xml_path.exists():
            log.debug("No sibling XML netlist found at %s", xml_path)
            return []

        log.debug("Loading XML netlist: %s", xml_path)
        try:
            tree = ET.parse(str(xml_path))
        except ET.ParseError as exc:
            log.warning("Failed to parse XML netlist %s: %s", xml_path, exc)
            return []

        root = tree.getroot()
        nets_elem = root.find("nets")
        if nets_elem is None:
            log.warning("XML netlist %s has no <nets> element", xml_path)
            return []

        # Build a quick lookup for known component tags.
        known_tags = {comp.tag for comp in components}

        nets: list[NetInfo] = []
        for net_elem in nets_elem.findall("net"):
            name = net_elem.get("name", "").strip()
            if not name:
                continue

            members: list[NetMember] = []
            for node in net_elem.findall("node"):
                ref = node.get("ref", "").strip()
                pin = node.get("pin", "").strip()
                if ref and pin:
                    if ref not in known_tags:
                        log.debug(
                            "Netlist references unknown component %r in net %r",
                            ref,
                            name,
                        )
                    members.append(NetMember(component=ref, pin=pin))

            nets.append(NetInfo(name=name, members=members))

        log.debug("Loaded %d nets from XML netlist", len(nets))
        return nets
