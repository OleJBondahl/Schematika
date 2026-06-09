"""Pure graph model for the Cytoscape HTML overview."""

from __future__ import annotations

from dataclasses import asdict, dataclass

# ---------------------------------------------------------------------------
# Helpers (ported verbatim from the consumer-repo prototype)
# ---------------------------------------------------------------------------


def pin_id(device: str, connector: str, pin: str) -> str:
    """Canonical physical-pin id: 'BMU1.J3.3', or 'X1..1' for empty connector."""
    return f"{device}.{connector}.{pin}"


def device_class(device: str) -> str:
    """Device family: strip a trailing run of digits ('BMU1' -> 'BMU').

    Hyphenated names like 'X-FUSED' and digit-free names like 'CHASSIS' are
    returned unchanged.
    """
    i = len(device)
    while i > 0 and device[i - 1].isdigit():
        i -= 1
    return device[:i] if i > 0 else device


def classify_net(name: str | None) -> str:
    """Map a net label to a visual class. Order matters (CAN before power)."""
    if not name:
        return "signal"
    low = name.lower()
    if "can" in low:
        return "CAN"
    if "gnd" in low:
        return "GND"
    if low.startswith("hvil") or "em_stop" in low:
        return "interlock"
    if any(k in low for k in ("pwr", "v24", "_pro")):
        return "power"
    return "signal"


class UnionFind:
    """Disjoint-set structure for signal grouping."""

    def __init__(self) -> None:
        """Initialize an empty union-find."""
        self.parent: dict[str, str] = {}

    def add(self, x: str) -> None:
        """Add x if not already present."""
        self.parent.setdefault(x, x)

    def find(self, x: str) -> str:
        """Return the root of x's component, with path compression."""
        self.add(x)
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a: str, b: str) -> None:
        """Merge the components containing a and b."""
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def _split_pin(pid: str) -> tuple[str, str, str]:
    parts = pid.split(".")
    return parts[0], parts[1] if len(parts) > 1 else "", ".".join(parts[2:])


def _trailing_int(tag: str) -> int | None:
    """Trailing run of digits as an int, or None ('BMU3' -> 3, 'CHASSIS' -> None)."""
    i = len(tag)
    while i > 0 and tag[i - 1].isdigit():
        i -= 1
    return int(tag[i:]) if i < len(tag) else None


# ---------------------------------------------------------------------------
# Frozen dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class Pin:
    """A physical connector pin with its signal assignment."""

    id: str
    device: str
    connector: str
    pin: str
    signal_id: int
    device_class: str
    parent: str
    pin_role: str


@dataclass(frozen=True, slots=True, kw_only=True)
class Edge:
    """A connection between two pins (harness, fuse, relay-contact, or PCB net)."""

    id: str
    kind: str
    a: str
    b: str
    label: str | None
    net_class: str
    directed: bool = False
    signal_id: int | None = None
    meta_edge: str | None = None
    relay: str | None = None
    state: str | None = None
    signal_a: int | None = None
    signal_b: int | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Signal:
    """A group of electrically-connected pins sharing one net."""

    id: int
    pins: tuple[str, ...]
    labels: tuple[str, ...]
    boards: tuple[str, ...]
    net_class: str


@dataclass(frozen=True, slots=True, kw_only=True)
class DeviceNode:
    """A device compound node (board, terminal block, etc.)."""

    id: str
    device_class: str
    string: int | None
    degree: int
    x: float = 0.0
    y: float = 0.0
    anchor: float | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ConnectorNode:
    """A connector child-node nested inside a DeviceNode."""

    id: str
    parent: str
    device: str


@dataclass(frozen=True, slots=True, kw_only=True)
class RelayNode:
    """A relay compound node nested inside a DeviceNode."""

    id: str
    parent: str
    board: str
    coil_pins: tuple[str, ...]
    contact_pairs: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class FuseNode:
    """A fuse child-node nested inside a DeviceNode."""

    id: str
    parent: str
    board: str
    pins: tuple[str, str]


@dataclass(frozen=True, slots=True, kw_only=True)
class Net:
    """A PCB copper net rendered as a line, junction, or tag."""

    id: str
    component: int
    board: str
    label: str
    net_class: str
    members: tuple[str, ...]
    render: str
    is_ground: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class MetaEdge:
    """Aggregated harness bundle between two devices."""

    id: str
    a: str
    b: str
    net_count: int
    classes: tuple[str, ...]
    mixed: bool
    net_class: str
    wires: tuple[str, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class OverviewGraph:
    """Complete graph model for one overview page."""

    pins: tuple[Pin, ...]
    edges: tuple[Edge, ...]
    signals: tuple[Signal, ...]
    devices: tuple[DeviceNode, ...]
    connectors: tuple[ConnectorNode, ...]
    relays: tuple[RelayNode, ...]
    fuses: tuple[FuseNode, ...]
    nets: tuple[Net, ...]
    meta_edges: tuple[MetaEdge, ...]
    max_visible_edge_budget: int = 250

    def to_dict(self) -> dict:  # noqa: C901
        """Emit the v2 JSON shape consumed by the Cytoscape frontend."""

        def _pin(p: Pin) -> dict:
            return {
                "id": p.id,
                "device": p.device,
                "connector": p.connector,
                "pin": p.pin,
                "signalId": p.signal_id,
                "deviceClass": p.device_class,
                "parent": p.parent,
                "pinRole": p.pin_role,
            }

        def _edge(e: Edge) -> dict:
            d: dict = {
                "id": e.id,
                "kind": e.kind,
                "a": e.a,
                "b": e.b,
                "label": e.label,
            }
            if e.kind == "harness":
                d["netClass"] = e.net_class
                d["directed"] = e.directed
                if e.signal_id is not None:
                    d["signalId"] = e.signal_id
                if e.meta_edge is not None:
                    d["metaEdge"] = e.meta_edge
            elif e.kind == "fuse":
                if e.signal_id is not None:
                    d["signalId"] = e.signal_id
            elif e.kind == "relay-contact":
                if e.signal_a is not None:
                    d["signalA"] = e.signal_a
                if e.signal_b is not None:
                    d["signalB"] = e.signal_b
                if e.relay is not None:
                    d["relay"] = e.relay
                if e.state is not None:
                    d["state"] = e.state
            return d

        def _signal(s: Signal) -> dict:
            return {
                "id": s.id,
                "pins": list(s.pins),
                "labels": list(s.labels),
                "boards": list(s.boards),
                "netClass": s.net_class,
            }

        def _device(dv: DeviceNode) -> dict:
            return {
                "id": dv.id,
                "deviceClass": dv.device_class,
                "string": dv.string,
                "degree": dv.degree,
                "x": dv.x,
                "y": dv.y,
            }

        def _connector(c: ConnectorNode) -> dict:
            return asdict(c)

        def _relay(r: RelayNode) -> dict:
            return {
                "id": r.id,
                "parent": r.parent,
                "board": r.board,
                "coilPins": list(r.coil_pins),
                "contactPairs": [list(pair) for pair in r.contact_pairs],
            }

        def _fuse(f: FuseNode) -> dict:
            return {
                "id": f.id,
                "parent": f.parent,
                "board": f.board,
                "pins": list(f.pins),
            }

        def _net(n: Net) -> dict:
            return {
                "id": n.id,
                "component": n.component,
                "board": n.board,
                "label": n.label,
                "netClass": n.net_class,
                "members": list(n.members),
                "render": n.render,
                "isGround": n.is_ground,
            }

        def _meta_edge(m: MetaEdge) -> dict:
            return {
                "id": m.id,
                "a": m.a,
                "b": m.b,
                "netCount": m.net_count,
                "classes": list(m.classes),
                "mixed": m.mixed,
                "netClass": m.net_class,
                "wires": list(m.wires),
            }

        return {
            "pins": [_pin(p) for p in self.pins],
            "edges": [_edge(e) for e in self.edges],
            "signals": [_signal(s) for s in self.signals],
            "compound": {
                "devices": [_device(dv) for dv in self.devices],
                "connectors": [_connector(c) for c in self.connectors],
                "relays": [_relay(r) for r in self.relays],
                "fuses": [_fuse(f) for f in self.fuses],
            },
            "nets": [_net(n) for n in self.nets],
            "metaEdges": [_meta_edge(m) for m in self.meta_edges],
            "meta": {
                "version": "2",
                "maxVisibleEdgeBudget": self.max_visible_edge_budget,
            },
        }


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def build_graph(  # noqa: C901, PLR0912, PLR0915
    wires: list,
    pcb_nets: list,
    fuse_links: list,
    relay_contacts: list,
    relay_pins: dict,
    *,
    max_visible_edge_budget: int = 250,
) -> OverviewGraph:
    """Build the overview graph from wire/net/relay/fuse data.

    Reproduces the v2 logic from the consumer-repo prototype as frozen
    dataclasses. Inputs are plain tuples; relay_pins maps relay id to
    dict with 'coil', 'contact', and 'contactPairs' keys.
    """
    uf = UnionFind()

    # Phase 1: union-find pass — establishes signal groups
    for a, b, _net in wires:
        uf.union(a, b)

    for board, net, members in pcb_nets:  # noqa: B007
        for m in members:
            uf.add(m)
        for m in members[1:]:
            uf.union(members[0], m)

    for _edge_id, a, b, _label in fuse_links:
        uf.union(a, b)

    for _edge_id, _relay, a, b in relay_contacts:
        uf.add(a)
        uf.add(b)  # NO union — conditional contact

    # Phase 2: build pin->signal_id mapping
    root_to_sid: dict[str, int] = {}
    for pid in sorted(uf.parent):
        root_to_sid.setdefault(uf.find(pid), len(root_to_sid))

    sid_of: dict[str, int] = {pid: root_to_sid[uf.find(pid)] for pid in uf.parent}

    # Phase 3: relay/fuse pin role tables (needed before building Pin objects)
    relay_of_pin: dict[str, str] = {}
    role_of_pin: dict[str, str] = {}
    for relay, info in relay_pins.items():
        for rpid in info.get("coil", ()):
            relay_of_pin[rpid] = relay
            role_of_pin[rpid] = "coil"
        for rpid in info.get("contact", ()):
            relay_of_pin[rpid] = relay
            role_of_pin[rpid] = "contact"

    fuse_of_pin: dict[str, str] = {}
    fuse_nodes: list[FuseNode] = []
    for fuse_id, a, b, _label in fuse_links:
        board = _split_pin(a)[0]
        fuse_of_pin[a] = fuse_id
        fuse_of_pin[b] = fuse_id
        fuse_nodes.append(FuseNode(id=fuse_id, parent=board, board=board, pins=(a, b)))

    # Phase 4: build Pin objects (single pass — computes parent + pin_role)
    devices_dict: dict[str, DeviceNode] = {}
    connectors_dict: dict[str, ConnectorNode] = {}

    pins_list: list[Pin] = []
    for pid in sorted(uf.parent):
        dev, conn, pn = _split_pin(pid)
        dc = device_class(dev)
        conn_id = f"{dev}.{conn}"

        if pid in relay_of_pin:
            parent = relay_of_pin[pid]
            pin_role = role_of_pin[pid]
        elif pid in fuse_of_pin:
            parent = fuse_of_pin[pid]
            pin_role = "normal"
        else:
            parent = conn_id
            pin_role = "normal"

        pins_list.append(
            Pin(
                id=pid,
                device=dev,
                connector=conn,
                pin=pn,
                signal_id=sid_of[pid],
                device_class=dc,
                parent=parent,
                pin_role=pin_role,
            )
        )

        devices_dict.setdefault(
            dev,
            DeviceNode(id=dev, device_class=dc, string=_trailing_int(dev), degree=0),
        )
        connectors_dict.setdefault(
            conn_id, ConnectorNode(id=conn_id, parent=dev, device=dev)
        )

    # Phase 5: signals — collect labels and board memberships
    signals_acc: dict[int, dict] = {}
    for p in pins_list:
        s = signals_acc.setdefault(
            p.signal_id,
            {"id": p.signal_id, "pins": [], "labels": set(), "boards": set()},
        )
        s["pins"].append(p.id)
        if p.device_class == "JB":
            s["boards"].add(p.device)

    # Gather labels from wire/pcb/fuse edges
    for _i, (a, _b, net) in enumerate(wires):
        if net and a in sid_of:
            signals_acc[sid_of[a]]["labels"].add(net)

    for board, net, members in pcb_nets:  # noqa: B007
        if members and members[0] in sid_of and net:
            signals_acc[sid_of[members[0]]]["labels"].add(net)

    for _fuse_id, a, _b, label in fuse_links:
        if label and a in sid_of:
            signals_acc[sid_of[a]]["labels"].add(label)

    _class_rank = ["GND", "power", "CAN", "interlock", "signal"]
    signals_list: list[Signal] = []
    for s in sorted(signals_acc.values(), key=lambda x: x["id"]):
        classes = {classify_net(lbl) for lbl in s["labels"]}
        net_class = next((c for c in _class_rank if c in classes), "signal")
        signals_list.append(
            Signal(
                id=s["id"],
                pins=tuple(sorted(s["pins"])),
                labels=tuple(sorted(s["labels"])),
                boards=tuple(sorted(s["boards"])),
                net_class=net_class,
            )
        )

    # Phase 6: relay nodes
    relay_nodes: list[RelayNode] = []
    for relay, info in relay_pins.items():
        board = _split_pin(relay)[0]
        relay_nodes.append(
            RelayNode(
                id=relay,
                parent=board,
                board=board,
                coil_pins=tuple(info.get("coil", ())),
                contact_pairs=tuple(
                    tuple(pair) for pair in info.get("contactPairs", ())
                ),  # type: ignore[arg-type]
            )
        )

    # Phase 7: PCB nets
    seen_net_ids: set[str] = set()
    net_nodes: list[Net] = []
    for board, net, raw_members in pcb_nets:
        members = list(raw_members)
        base_id = f"{board}.{net}"
        base_label = f"{board}:{net}"
        suffix = ""
        dup = 2
        while base_id + suffix in seen_net_ids:
            suffix = f"#{dup}"
            dup += 1
        net_id = base_id + suffix
        seen_net_ids.add(net_id)
        render = {2: "line", 3: "junction"}.get(len(members), "tag")
        net_class = classify_net(net)
        net_nodes.append(
            Net(
                id=net_id,
                component=sid_of[members[0]],
                board=board,
                label=base_label + suffix,
                net_class=net_class,
                members=tuple(members),
                render=render,
                is_ground=net_class == "GND",
            )
        )

    # Phase 8: build raw harness edges (before meta-edge enrichment)
    harness_edges: list[dict] = []
    for i, (a, b, net) in enumerate(wires):
        harness_edges.append(
            {
                "idx": i,
                "id": f"W{i:03d}",
                "a": a,
                "b": b,
                "label": net,
                "net_class": classify_net(net),
            }
        )

    # Phase 9: meta-edges — group harness wires by unordered device pair
    meta_acc: dict[str, dict] = {}
    for e in harness_edges:
        da = _split_pin(e["a"])[0]
        db = _split_pin(e["b"])[0]
        first, second = sorted((da, db))
        meta_id = f"meta:{first}|{second}"
        m = meta_acc.setdefault(
            meta_id,
            {
                "id": meta_id,
                "a": first,
                "b": second,
                "sids": set(),
                "classes": set(),
                "wires": [],
            },
        )
        m["sids"].add(sid_of[e["a"]])
        m["classes"].add(classify_net(e["label"]))
        m["wires"].append(e["id"])
        # Annotate the harness edge dict with meta_edge id and signal_id
        e["meta_edge"] = meta_id
        e["signal_id"] = sid_of[e["a"]]

    meta_edge_list: list[MetaEdge] = []
    for m in meta_acc.values():
        classes = tuple(sorted(m["classes"]))
        mixed = len(classes) > 1
        meta_edge_list.append(
            MetaEdge(
                id=m["id"],
                a=m["a"],
                b=m["b"],
                net_count=len(m["sids"]),
                classes=classes,
                mixed=mixed,
                net_class="mixed" if mixed else classes[0],
                wires=tuple(m["wires"]),
            )
        )

    # Phase 10: per-device degree
    adjacency: dict[str, set[str]] = {}
    for me in meta_edge_list:
        adjacency.setdefault(me.a, set()).add(me.b)
        adjacency.setdefault(me.b, set()).add(me.a)

    devices_list: list[DeviceNode] = [
        DeviceNode(
            id=dv.id,
            device_class=dv.device_class,
            string=dv.string,
            degree=len(adjacency.get(dv.id, set())),
            x=dv.x,
            y=dv.y,
            anchor=dv.anchor,
        )
        for dv in devices_dict.values()
    ]

    # Phase 11: assemble edges (harness + fuse + relay-contact; drop pcb-net)
    harness_edge_objs = [
        Edge(
            id=e["id"],
            kind="harness",
            a=e["a"],
            b=e["b"],
            label=e["label"],
            net_class=e["net_class"],
            directed=False,
            signal_id=e["signal_id"],
            meta_edge=e["meta_edge"],
        )
        for e in harness_edges
    ]
    fuse_edge_objs = [
        Edge(
            id=fuse_id,
            kind="fuse",
            a=a,
            b=b,
            label=label,
            net_class=classify_net(label),
            signal_id=sid_of[a],
        )
        for fuse_id, a, b, label in fuse_links
    ]
    relay_edge_objs = [
        Edge(
            id=edge_id,
            kind="relay-contact",
            a=a,
            b=b,
            label=None,
            net_class="signal",
            relay=relay,
            state="open-default",
            signal_a=sid_of[a],
            signal_b=sid_of[b],
        )
        for edge_id, relay, a, b in relay_contacts
    ]
    edges_list = [*harness_edge_objs, *fuse_edge_objs, *relay_edge_objs]

    return OverviewGraph(
        pins=tuple(pins_list),
        edges=tuple(edges_list),
        signals=tuple(signals_list),
        devices=tuple(devices_list),
        connectors=tuple(connectors_dict.values()),
        relays=tuple(relay_nodes),
        fuses=tuple(fuse_nodes),
        nets=tuple(net_nodes),
        meta_edges=tuple(meta_edge_list),
        max_visible_edge_budget=max_visible_edge_budget,
    )
