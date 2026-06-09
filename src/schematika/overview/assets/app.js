"use strict";

// Built-in default palette / class config. A deployment can override any of
// these by supplying a `config` block in the graph data (read inside runV2,
// where `data` is in scope — not at module top-level where `data` is absent).
// Keep these values as the documented fallbacks; when a deployment mirrors
// them the rendered output is unchanged.
const BUILTIN_NET_COLORS = {
  power: "#E69F00",     // orange
  CAN: "#56B4E9",       // sky blue
  GND: "#999999",       // grey
  interlock: "#D55E00", // vermillion
  signal: "#009E73",    // bluish green
  mixed: "#6e7681",
};
const BUILTIN_CLASS_COLORS = {
  X: "#d2a8ff",    // terminal blocks (spine)
  Q: "#e3b341",    // contactors
  F: "#f0883e",    // breakers
  FT: "#f85149",   // thermal overloads
  K: "#58a6ff",    // relays / coils
  CT: "#7ee787",   // current transformers
  G: "#bc8cff",    // PSUs / supplies
  U: "#79c0ff",    // blocks
  PLC: "#ff9e64",  // PLC modules
  FIELD: "#39c5cf",   // field devices (rightmost column)
};
const BUILTIN_DEFAULT_CLASS_COLOR = "#8b949e";  // field devices & any unlisted class

// BUNDLE:LOADER-START
(window.OVERVIEW_DATA
  ? Promise.resolve(window.OVERVIEW_DATA)
  : fetch("overview.json", { cache: "no-store" }).then((r) => r.json())
).then((data) => {
  runV2(data);
});
// BUNDLE:LOADER-END

// ===================== compound graph with collapse/expand =====================
function runV2(data) {
  // Palette / class config: read from data.config with built-in fallbacks.
  // `data` is only in scope here, so these live inside the run function.
  const cfg = (data && data.config) || {};
  const NET_COLOR = cfg.netColors || BUILTIN_NET_COLORS;
  const CLASS_COLOR = cfg.classColors || BUILTIN_CLASS_COLORS;
  const DEFAULT_CLASS_COLOR = cfg.defaultClassColor || BUILTIN_DEFAULT_CLASS_COLOR;
  const spineSet = new Set(cfg.spineClasses || []);

  const pinMap = new Map(data.pins.map((p) => [p.id, p]));
  const c = data.compound;

  // --- device parents at frozen build-time positions ---
  const devClass = new Map(c.devices.map((d) => [d.id, d.deviceClass]));
  const devPos = new Map();
  for (const d of c.devices) {
    devPos.set(d.id, { x: d.x, y: d.y });
  }

  // --- container nodes (connectors, relay/fuse sub-parents) ---
  const relaySet = new Set(c.relays.map((r) => r.id));
  const fuseSet = new Set(c.fuses.map((f) => f.id));
  const containerParent = new Map(); // containerId -> parent node id
  const containerKind = new Map();   // containerId -> "connector"|"relay"|"fuse"
  for (const r of c.relays) { containerParent.set(r.id, r.parent); containerKind.set(r.id, "relay"); }
  for (const f of c.fuses) { containerParent.set(f.id, f.parent); containerKind.set(f.id, "fuse"); }
  // connectors from pin.parent values not already a relay/fuse sub-parent
  for (const p of data.pins) {
    if (containerParent.has(p.parent)) continue;
    containerParent.set(p.parent, p.device);
    containerKind.set(p.parent, "connector");
  }

  // --- layout: lay containers + pins on a fixed local grid per device ---
  const PIN_W = 32, PIN_H = 22, PIN_GAP = 7;
  const CONT_PAD = 12, CONT_GAP = 16;
  const nodes = [];

  // device parents
  const degreeBucket = (deg) =>
    deg <= 0 ? "leaf" : deg <= 2 ? "low" : deg <= 6 ? "mid" : "hub";
  for (const d of c.devices) {
    const deg = d.degree || 0;
    nodes.push({
      data: {
        id: d.id, kind: "device", deviceClass: d.deviceClass,
        degree: deg, degreeBucket: degreeBucket(deg),
        label: `${d.id} ·${deg}`,
      },
      position: { ...devPos.get(d.id) },
    });
  }

  // group containers by parent device, group pins by container
  const pinsByContainer = new Map();
  for (const p of data.pins) {
    if (!pinsByContainer.has(p.parent)) pinsByContainer.set(p.parent, []);
    pinsByContainer.get(p.parent).push(p);
  }
  // every container's parent (device or board) is itself a device node, so group by it directly
  const containersByDevice = new Map();
  for (const [cid, dev] of containerParent) {
    if (!containersByDevice.has(dev)) containersByDevice.set(dev, []);
    containersByDevice.get(dev).push(cid);
  }

  // index harness edges by pin id, for partner-direction internal layout
  const harnessByPin = new Map();
  for (const e of data.edges) {
    if (e.kind !== "harness") continue;
    for (const pin of [e.a, e.b]) {
      if (!harnessByPin.has(pin)) harnessByPin.set(pin, []);
      harnessByPin.get(pin).push(e);
    }
  }
  // mean direction (relative to the device) of the external devices a pin-set wires to
  const preferredDir = (pins, dev, base) => {
    let sx = 0, sy = 0, n = 0;
    for (const p of pins) {
      for (const e of harnessByPin.get(p.id) || []) {
        const other = e.a === p.id ? e.b : e.a;
        const od = (pinMap.get(other) || {}).device;
        if (!od || od === dev) continue;
        const op = devPos.get(od);
        if (!op) continue;
        sx += op.x; sy += op.y; n += 1;
      }
    }
    return n ? { dx: sx / n - base.x, dy: sy / n - base.y, n } : { dx: 0, dy: 0, n: 0 };
  };

  // Track which containers/pins/hubs belong to which device (for expand/collapse)
  const childrenOfDevice = new Map(); // devId -> Set of node ids (containers + pins + hubs)
  for (const d of c.devices) childrenOfDevice.set(d.id, new Set());

  for (const [dev, conts] of containersByDevice) {
    const base = devPos.get(dev) || { x: 0, y: 0 };
    const isSpine = spineSet.has(devClass.get(dev));
    const devChildren = childrenOfDevice.get(dev) || new Set();

    // compute each container's preferred horizontal direction toward its wire partners
    const metas = conts.map((cid) => {
      const pins = (pinsByContainer.get(cid) || []).slice();
      const dir = preferredDir(pins, dev, base);
      return { cid, kind: containerKind.get(cid), pins, dx: dir.dx, dy: dir.dy, wired: dir.n > 0 };
    });
    // order connectors left->right by partner direction; relays/fuses and unwired go right
    const rank = (m) =>
      m.kind !== "connector" ? Infinity : !m.wired ? 1e9 : m.dx;
    metas.sort((A, B) => (rank(A) - rank(B)) || (A.dy - B.dy) || A.cid.localeCompare(B.cid));
    // within each container, order pins top->bottom by their own partner direction
    for (const m of metas) {
      m.pins.sort((a, b) =>
        (preferredDir([a], dev, base).dy - preferredDir([b], dev, base).dy)
        || a.id.localeCompare(b.id));
    }

    // tile a list of containers into a column grid starting at (startX, startY)
    const COL_STEP = PIN_W + CONT_PAD + CONT_GAP;
    const placeBand = (items, startX, startY) => {
      let cx = startX, cy = startY, colMax = 0, perCol = 0;
      for (const m of items) {
        nodes.push({
          data: {
            id: m.cid, parent: dev, kind: m.kind,
            label: m.cid.slice(dev.length + 1),
            deviceClass: devClass.get(dev),
          },
        });
        devChildren.add(m.cid);
        let py = cy;
        for (const p of m.pins) {
          nodes.push({
            data: {
              id: p.id, parent: m.cid, kind: "pin",
              label: p.pin, pinRole: p.pinRole,
              signalId: p.signalId, deviceClass: p.deviceClass,
            },
            position: { x: cx, y: py },
          });
          devChildren.add(p.id);
          py += PIN_H + PIN_GAP;
        }
        const colH = m.pins.length * (PIN_H + PIN_GAP);
        colMax = Math.max(colMax, colH);
        cx += COL_STEP;
        perCol += 1;
        if (perCol >= 6) { perCol = 0; cx = startX; cy += colMax + 60; colMax = 0; }
      }
    };

    if (isSpine) {
      // split a spine device: left-partner connectors on the left, the rest on the right
      const left = metas.filter((m) => m.kind === "connector" && m.wired && m.dx < 0);
      const right = metas.filter((m) => !(m.kind === "connector" && m.wired && m.dx < 0));
      const leftCols = Math.min(Math.max(left.length, 1), 6);
      placeBand(left, base.x - 40 - leftCols * COL_STEP, base.y + 60);
      placeBand(right, base.x + 40, base.y + 60);
    } else {
      placeBand(metas, base.x - 120, base.y + 60);
    }
  }

  // --- net-tier nodes/edges (line / junction / tag) ---
  // Junctions are positioned at member centroid after the build pass.
  // Tags are offset next to their member pin after the build pass.
  const junctionMembers = new Map();   // junctionId -> [pinId...]
  const tagAnchors = new Map();         // tagId -> pinId (for post-build offset)
  const netEdges = [];                  // net-line / net-spoke edge defs
  // Map net element id -> board device (for collapse/expand visibility)
  const netElemBoard = new Map();
  for (const net of data.nets) {
    const board = net.board;
    const devChildren = childrenOfDevice.get(board);
    if (net.render === "line") {
      const id = "net:" + net.id;
      netEdges.push({ data: {
        id, source: net.members[0], target: net.members[1], kind: "net-line",
        netClass: net.netClass, label: net.label, component: net.component,
      } });
      netElemBoard.set(id, board);
    } else if (net.render === "junction") {
      const jid = "jnc:" + net.id;
      nodes.push({ data: {
        id: jid, parent: board, kind: "junction",
        netClass: net.netClass, label: net.label, component: net.component,
      } });
      junctionMembers.set(jid, net.members.slice());
      if (devChildren) devChildren.add(jid);
      netElemBoard.set(jid, board);
      net.members.forEach((m, i) => {
        const sid = "spk:" + net.id + ":" + i;
        netEdges.push({ data: {
          id: sid, source: jid, target: m, kind: "net-spoke",
          netClass: net.netClass, component: net.component,
        } });
        netElemBoard.set(sid, board);
      });
    } else if (net.render === "tag") {
      // Strip redundant board prefix ("BOARD:GND" -> "GND"); label only the
      // first member's tag to avoid repeated-label pileup (connectivity is
      // conveyed by the shared glyph + color across all member tags).
      const shortLabel = net.label.includes(":") ? net.label.split(":").slice(1).join(":") : net.label;
      net.members.forEach((m, i) => {
        const tid = "tag:" + net.id + ":" + i;
        nodes.push({ data: {
          id: tid, parent: board, kind: "net-tag",
          netClass: net.netClass, label: i === 0 ? shortLabel : "", component: net.component,
          isGround: net.isGround ? 1 : 0,
        } });
        tagAnchors.set(tid, m);
        if (devChildren) devChildren.add(tid);
        netElemBoard.set(tid, board);
      });
    }
  }

  // --- edges ---
  // assert: never connect a coil pin and contact pin of the same relay
  const pinRelay = new Map(); // pinId -> relayId  (for coil/contact pins)
  const pinRoleOf = new Map();
  for (const p of data.pins) pinRoleOf.set(p.id, p.pinRole);
  for (const r of c.relays) {
    for (const cp of r.coilPins) pinRelay.set(cp, r.id);
    for (const pair of r.contactPairs) for (const pin of pair) pinRelay.set(pin, r.id);
  }
  const isCoilContactSameRelay = (a, b) => {
    const ra = pinRelay.get(a), rb = pinRelay.get(b);
    if (!ra || ra !== rb) return false;
    const roleA = pinRoleOf.get(a), roleB = pinRoleOf.get(b);
    return (roleA === "coil" && roleB === "contact") || (roleA === "contact" && roleB === "coil");
  };

  // Track which harness edge belongs to which meta-edge
  // Also track which edges are "internal" to a device (pcb-net, relay-contact, fuse)
  const cyEdges = [];
  // Map metaEdgeId -> Set of harness edge ids
  const metaEdgeToWires = new Map();
  // Map edgeId -> devId for internal edges
  const edgeInternalTo = new Map();

  for (const e of data.edges) {
    if (e.kind === "harness") {
      if (isCoilContactSameRelay(e.a, e.b)) continue;
      cyEdges.push({ data: {
        id: e.id, source: e.a, target: e.b, kind: "harness",
        netClass: e.netClass, signalId: e.signalId, label: e.label,
        metaEdge: e.metaEdge,
      } });
      if (e.metaEdge) {
        if (!metaEdgeToWires.has(e.metaEdge)) metaEdgeToWires.set(e.metaEdge, new Set());
        metaEdgeToWires.get(e.metaEdge).add(e.id);
      }
    } else if (e.kind === "relay-contact") {
      if (isCoilContactSameRelay(e.a, e.b)) continue;
      cyEdges.push({ data: {
        id: e.id, source: e.a, target: e.b, kind: "relay-contact",
        relay: e.relay, signalA: e.signalA, signalB: e.signalB,
      } });
      // relay-contact is internal to the device containing the relay
      const relayParent = (c.relays.find((r) => r.id === e.relay) || {}).parent;
      if (relayParent) edgeInternalTo.set(e.id, relayParent);
    } else if (e.kind === "fuse") {
      if (isCoilContactSameRelay(e.a, e.b)) continue;
      cyEdges.push({ data: {
        id: e.id, source: e.a, target: e.b, kind: "fuse",
        signalId: e.signalId, label: e.label,
      } });
      // fuse is internal to the device containing the fuse
      const fuseParent = (c.fuses.find((f) => {
        const pins = pinsByContainer.get(f.id) || [];
        return pins.some((p) => p.id === e.a || p.id === e.b);
      }) || {}).parent;
      if (fuseParent) edgeInternalTo.set(e.id, fuseParent);
    }
  }

  // net-tier edges (lines + junction spokes), board-internal
  for (const ne of netEdges) {
    cyEdges.push(ne);
    edgeInternalTo.set(ne.data.id, netElemBoard.get(ne.data.id));
  }

  // --- meta-edge elements (one per device pair, used in collapsed view) ---
  for (const me of data.metaEdges) {
    cyEdges.push({ data: {
      id: me.id, source: me.a, target: me.b, kind: "meta",
      netClass: me.netClass, mixed: me.mixed, netCount: me.netCount,
      label: `${me.netCount} nets`,
      wires: me.wires,
    } });
  }

  // Build a map: metaEdgeId -> {a, b} devices
  const metaEdgeDevices = new Map();
  for (const me of data.metaEdges) {
    metaEdgeDevices.set(me.id, { a: me.a, b: me.b });
  }

  // Build reverse: (devA, devB) -> metaEdgeId
  const pairToMeta = new Map();
  for (const me of data.metaEdges) {
    pairToMeta.set(`${me.a}|${me.b}`, me.id);
    pairToMeta.set(`${me.b}|${me.a}`, me.id);
  }

  const cy = cytoscape({
    container: document.getElementById("cy"),
    layout: { name: "preset" },
    elements: { nodes, edges: cyEdges },
    style: [
      { selector: "node[kind = 'device']", style: {
        "background-color": (n) => (CLASS_COLOR[n.data("deviceClass")] || DEFAULT_CLASS_COLOR),
        "background-opacity": 0.15, "border-width": 2,
        "border-color": (n) => (CLASS_COLOR[n.data("deviceClass")] || DEFAULT_CLASS_COLOR),
        label: "data(label)", color: "#c9d1d9", "font-weight": "bold", "font-size": 29,
        "text-valign": "top", "text-halign": "center", "text-margin-y": -2,
        shape: "round-rectangle", padding: 12,
        width: 80, height: 40,
      } },
      { selector: "node[kind = 'device'][degreeBucket = 'leaf']", style: {
        "border-width": 1, "border-style": "dashed",
      } },
      { selector: "node[kind = 'device'][degreeBucket = 'low']", style: {
        "border-width": 2, "border-style": "solid",
      } },
      { selector: "node[kind = 'device'][degreeBucket = 'mid']", style: {
        "border-width": 4, "border-style": "solid",
      } },
      { selector: "node[kind = 'device'][degreeBucket = 'hub']", style: {
        "border-width": 6, "border-style": "double",
      } },
      { selector: "node[kind = 'device'].expanded", style: {
        "border-width": 3,
        "border-color": "#ffffff",
        "background-color": "#0d1117",
        "background-opacity": 0.92,
        "z-index": 10,
      } },
      // expanded subtree draws above foreign collapsed devices
      { selector: ".infront", style: { "z-index": 20 } },
      { selector: "node[kind = 'connector']", style: {
        "background-opacity": 0.06, "border-width": 1, "border-color": "#30363d",
        label: "data(label)", color: "#8b949e", "font-size": 12,
        "text-valign": "top", "text-halign": "center", shape: "round-rectangle", padding: 3,
      } },
      { selector: "node[kind = 'relay']", style: {
        "background-color": "#bc8cff", "background-opacity": 0.12,
        "border-width": 1, "border-color": "#bc8cff",
        label: "data(label)", color: "#bc8cff", "font-size": 13, "font-weight": "bold",
        "text-valign": "top", "text-halign": "center", shape: "round-rectangle", padding: 4,
      } },
      { selector: "node[kind = 'fuse']", style: {
        "background-color": "#f0883e", "background-opacity": 0.12,
        "border-width": 1, "border-color": "#f0883e",
        label: "data(label)", color: "#f0883e", "font-size": 13, "font-weight": "bold",
        "text-valign": "top", "text-halign": "center", shape: "round-rectangle", padding: 4,
      } },
      { selector: "node[kind = 'pin']", style: {
        "background-color": (n) => NET_COLOR[(data.signals[n.data("signalId")] || {}).netClass] || "#6e7681",
        label: "data(label)", color: "#0d1117", "font-size": 10,
        "text-valign": "center", "text-halign": "center",
        width: 28, height: 18, shape: "round-rectangle",
      } },
      { selector: "node[kind = 'pin'][pinRole = 'coil']", style: {
        shape: "ellipse", "border-width": 2, "border-color": "#bc8cff", "background-color": "#3a2d52",
        color: "#e0d4ff",
      } },
      { selector: "node[kind = 'pin'][pinRole = 'contact']", style: {
        shape: "diamond", "border-width": 1, "border-color": "#bc8cff",
      } },
      { selector: "node[kind = 'junction']", style: {
        "background-color": (n) => NET_COLOR[n.data("netClass")] || "#6e7681",
        shape: "ellipse", width: 10, height: 10,
        "border-width": 1, "border-color": "#0d1117",
      } },
      { selector: "node[kind = 'net-tag']", style: {
        "background-color": (n) => NET_COLOR[n.data("netClass")] || "#6e7681",
        "background-opacity": 0.85,
        shape: "round-tag", width: 16, height: 12,
        label: "data(label)", color: "#c9d1d9", "font-size": 9,
        "text-valign": "center", "text-halign": "right", "text-margin-x": 2,
        "border-width": 1, "border-color": "#0d1117",
      } },
      { selector: "node[kind = 'net-tag'][isGround = 1]", style: {
        "background-color": NET_COLOR.GND, shape: "rectangle",
        width: 14, height: 14,
      } },
      { selector: "edge[kind = 'meta']", style: {
        "line-color": (e) => e.data("mixed") ? "#6e7681" : (NET_COLOR[e.data("netClass")] || "#6e7681"),
        "line-style": (e) => e.data("mixed") ? "dashed" : "solid",
        "line-dash-pattern": [8, 4],
        width: 3, "curve-style": "bezier", opacity: 0.9,
        label: "data(label)", color: "#c9d1d9", "font-size": 13,
        "text-background-color": "#0d1117", "text-background-opacity": 0.7, "text-background-padding": 2,
        "text-rotation": "autorotate",
      } },
      { selector: "edge[kind = 'harness']", style: {
        "line-color": (e) => NET_COLOR[e.data("netClass")] || "#8b949e",
        width: 1.5, "curve-style": "bezier", opacity: 0.7,
        label: "data(label)", color: "#8b949e", "font-size": 9,
        "min-zoomed-font-size": 7,
        "text-background-color": "#0d1117", "text-background-opacity": 0.6,
        "text-background-padding": 1, "text-rotation": "autorotate",
      } },
      { selector: "edge[kind = 'net-line']", style: {
        "line-color": (e) => NET_COLOR[e.data("netClass")] || "#6e7681",
        width: 2, "curve-style": "straight", opacity: 0.8, "z-index": 15,
        label: "data(label)", color: "#8b949e", "font-size": 9,
        "min-zoomed-font-size": 7,
        "text-background-color": "#0d1117", "text-background-opacity": 0.6,
        "text-background-padding": 1, "text-rotation": "autorotate",
      } },
      { selector: "edge[kind = 'net-spoke']", style: {
        "line-color": (e) => NET_COLOR[e.data("netClass")] || "#6e7681",
        width: 1.5, "curve-style": "straight", opacity: 0.7, "z-index": 15,
      } },
      { selector: "edge[kind = 'fuse']", style: {
        "line-color": "#f0883e", width: 2, "curve-style": "straight",
      } },
      { selector: "edge[kind = 'relay-contact']", style: {
        "line-color": "#f85149", width: 2, "curve-style": "bezier",
        "line-style": "dashed", "line-dash-pattern": [6, 4],
        "source-arrow-shape": "tee", "target-arrow-shape": "tee",
        "source-arrow-color": "#f85149", "target-arrow-color": "#f85149",
      } },
      { selector: ".hl", style: { "border-width": 3, "border-color": "#ffffff", "line-color": "#ffffff", opacity: 1, "z-index": 99 } },
      { selector: ".dim", style: { opacity: 0.08 } },
    ],
  });

  window.cy = cy; // expose for debugging / screenshot tooling

  // position junction nodes at centroid of member pins (positions now resolved)
  for (const [jid, members] of junctionMembers) {
    const ps = members.map((m) => cy.getElementById(m)).filter((n) => n.length);
    if (!ps.length) continue;
    let sx = 0, sy = 0;
    for (const n of ps) { const p = n.position(); sx += p.x; sy += p.y; }
    cy.getElementById(jid).position({ x: sx / ps.length, y: sy / ps.length });
  }

  // position net tags adjacent to their anchor pin
  for (const [tid, pinId] of tagAnchors) {
    const pin = cy.getElementById(pinId);
    if (!pin.length) continue;
    const p = pin.position();
    cy.getElementById(tid).position({ x: p.x + 22, y: p.y });
  }

  // ===================== Collapse/Expand State Machine =====================

  // Track expanded devices
  const expandedDevices = new Set();

  // Set of all internal edge ids (pcb-net, relay-contact, fuse) — hidden when device collapsed
  // Also harness edges are hidden unless BOTH endpoints are expanded

  // All child node ids per device (for show/hide)
  // childrenOfDevice is already built above

  // Apply initial collapsed state: hide all children + all detail/spoke/internal edges
  function applyCollapsedDefaults() {
    // Hide all non-device nodes (connectors, pins, relays, fuses, hubs)
    cy.nodes().not("[kind = 'device']").style("display", "none");
    // Hide all detail edges (harness, pcb-net, relay-contact, fuse)
    cy.edges().not("[kind = 'meta']").style("display", "none");
    // Show meta-edges
    cy.edges("[kind = 'meta']").style("display", "element");
    // Show all device nodes
    cy.nodes("[kind = 'device']").style("display", "element");
  }

  // Recompute visibility of all edges based on expand state
  // Locked rule:
  //   meta-edge(A,B) shown iff (A collapsed OR B collapsed)
  //   detail wires(A,B) shown iff (A expanded AND B expanded)
  //   internal edge (pcb-net/relay-contact/fuse) shown iff its device is expanded
  function recomputeEdgeVisibility() {
    // Meta-edges
    cy.edges("[kind = 'meta']").forEach((e) => {
      const devs = metaEdgeDevices.get(e.id());
      if (!devs) return;
      const aExp = expandedDevices.has(devs.a);
      const bExp = expandedDevices.has(devs.b);
      // show meta if EITHER collapsed
      e.style("display", (aExp && bExp) ? "none" : "element");
    });

    // Harness edges (detail wires)
    cy.edges("[kind = 'harness']").forEach((e) => {
      const metaId = e.data("metaEdge");
      if (!metaId) { e.style("display", "none"); return; }
      const devs = metaEdgeDevices.get(metaId);
      if (!devs) { e.style("display", "none"); return; }
      const aExp = expandedDevices.has(devs.a);
      const bExp = expandedDevices.has(devs.b);
      e.style("display", (aExp && bExp) ? "element" : "none");
    });

    // Internal edges (net-line, net-spoke, relay-contact, fuse) — show only if their device is expanded
    cy.edges("[kind = 'net-line'], [kind = 'net-spoke'], [kind = 'relay-contact'], [kind = 'fuse']").forEach((e) => {
      const dev = edgeInternalTo.get(e.id());
      const show = dev && expandedDevices.has(dev);
      e.style("display", show ? "element" : "none");
    });
  }

  function expandDevice(devId) {
    if (expandedDevices.has(devId)) return;
    expandedDevices.add(devId);
    cy.getElementById(devId).addClass("expanded");
    // Show all children of this device; raise them above foreign collapsed boxes
    const children = childrenOfDevice.get(devId) || new Set();
    for (const cid of children) {
      cy.getElementById(cid).style("display", "element").addClass("infront");
    }
    recomputeEdgeVisibility();
  }

  function collapseDevice(devId) {
    if (!expandedDevices.has(devId)) return;
    expandedDevices.delete(devId);
    cy.getElementById(devId).removeClass("expanded");
    // Hide all children of this device
    const children = childrenOfDevice.get(devId) || new Set();
    for (const cid of children) {
      cy.getElementById(cid).style("display", "none").removeClass("infront");
    }
    recomputeEdgeVisibility();
  }

  function collapseAll() {
    for (const devId of [...expandedDevices]) {
      collapseDevice(devId);
    }
    clearHighlight();
  }

  function resetView() {
    collapseAll();          // also clears highlight (collapseAll calls clearHighlight)
    search.value = "";
    applySearch();
    cy.fit(undefined, 40);  // back to the full collapsed overview
  }

  // Expose for tooling
  window.expandDevice = expandDevice;
  window.collapseDevice = collapseDevice;
  window.collapseAll = collapseAll;
  window.resetView = resetView;
  window.selectSignal = selectSignal;

  // Apply defaults
  applyCollapsedDefaults();

  // ===================== Interaction handlers =====================

  cy.on("tap", "node[kind = 'device']", (evt) => {
    const devId = evt.target.id();
    if (expandedDevices.has(devId)) {
      collapseDevice(devId);
    } else {
      expandDevice(devId);
    }
    // Clear highlight on device tap (non-signal tap)
    clearHighlight();
  });

  cy.on("tap", "edge[kind = 'meta']", (evt) => {
    const devs = metaEdgeDevices.get(evt.target.id());
    if (!devs) return;
    const aExp = expandedDevices.has(devs.a);
    const bExp = expandedDevices.has(devs.b);
    if (aExp && bExp) {
      // Both expanded — collapse both
      collapseDevice(devs.a);
      collapseDevice(devs.b);
    } else {
      // Expand both
      expandDevice(devs.a);
      expandDevice(devs.b);
    }
    clearHighlight();
  });

  cy.on("tap", "edge[kind = 'harness']", (evt) => {
    const sid = evt.target.data("signalId");
    if (sid != null) selectSignal(sid);
  });

  cy.on("tap", "edge[kind = 'net-line']", (evt) => {
    const comp = evt.target.data("component");
    if (comp != null) selectSignal(comp);
  });

  cy.on("tap", (evt) => {
    // Background click intentionally does nothing — Escape and the Reset view
    // button are the only reset affordances, so a misclick never clears a trace.
    void evt;
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      resetView();
    }
  });

  // ===================== Legend =====================
  const legend = document.getElementById("legend");
  // net-class line swatch (hue on edges/junctions/tags)
  const netItem = (color, text, dashed) => {
    const s = dashed
      ? `border-bottom: 2px dashed ${color}; background: transparent; width: 18px; height: 0;`
      : `background:${color}`;
    return `<span class="item"><span class="swatch" style="${s}"></span>${text}</span>`;
  };
  // device-class fill swatch (hue on node fills, drawn as outlined box)
  const devItem = (color, text) =>
    `<span class="item"><span class="swatch" style="background:${color};opacity:0.35;border:1px solid ${color}"></span>${text}</span>`;
  const glyph = (html, text) =>
    `<span class="item">${html} ${text}</span>`;

  legend.innerHTML =
    `<span class="item" style="opacity:.6">nets:</span>` +
    netItem(NET_COLOR.power, "power") + netItem(NET_COLOR.CAN, "CAN") +
    netItem(NET_COLOR.GND, "GND") + netItem(NET_COLOR.interlock, "interlock") +
    netItem(NET_COLOR.signal, "signal") + netItem(NET_COLOR.mixed, "mixed", true) +
    glyph(`<span style="color:${NET_COLOR.signal}">●</span>`, "junction") +
    glyph(`<span style="background:${NET_COLOR.GND};display:inline-block;width:11px;height:11px;vertical-align:middle"></span>`, "GND tag") +
    glyph(`<span style="color:#f0883e">▭</span>`, "fuse") +
    glyph(`<span style="color:#f85149">⎯/⎯</span>`, "relay break") +
    `<span class="item" style="opacity:.6">devices:</span>` +
    devItem(CLASS_COLOR.X, "X") + devItem(CLASS_COLOR.Q, "Q") +
    devItem(CLASS_COLOR.F, "F") + devItem(CLASS_COLOR.FT, "FT") +
    devItem(CLASS_COLOR.K, "K") + devItem(CLASS_COLOR.CT, "CT") +
    devItem(CLASS_COLOR.G, "G") + devItem(CLASS_COLOR.U, "U") +
    devItem(CLASS_COLOR.PLC, "PLC") + devItem(DEFAULT_CLASS_COLOR, "field") +
    `<span class="item" style="opacity:.6">degree (·N):</span>` +
    glyph(`<span style="display:inline-block;width:11px;height:11px;border:1px dashed #8b949e;vertical-align:middle"></span>`, "leaf ≤0") +
    glyph(`<span style="display:inline-block;width:11px;height:11px;border:2px solid #8b949e;vertical-align:middle"></span>`, "low ≤2") +
    glyph(`<span style="display:inline-block;width:11px;height:11px;border:4px solid #c9d1d9;vertical-align:middle"></span>`, "mid ≤6") +
    glyph(`<span style="display:inline-block;width:11px;height:11px;border:5px double #c9d1d9;vertical-align:middle"></span>`, "hub >6");

  // ===================== Titlebar hint =====================
  const titlebar = document.getElementById("titlebar");
  const hintSpan = document.createElement("span");
  hintSpan.style.cssText = "font-size:10px; font-weight:normal; color:#8b949e; margin-left:8px;";
  hintSpan.textContent = "Click a box or a line to expand · click a signal to trace · Reset view to clear";
  titlebar.appendChild(hintSpan);

  const crumb = document.createElement("span");
  crumb.id = "breadcrumb";
  crumb.style.cssText = "font-size:11px; font-weight:normal; color:#58a6ff; margin-left:8px;";
  crumb.style.display = "none";
  const crumbExit = document.createElement("button");
  crumbExit.textContent = "✕ Exit trace";
  crumbExit.id = "btn-exit-trace";
  crumbExit.style.cssText = "padding:3px 10px; font-size:11px; cursor:pointer; background:#21262d; color:#c9d1d9; border:1px solid #30363d; border-radius:4px;";
  crumbExit.style.display = "none";
  crumbExit.onclick = () => clearHighlight();
  titlebar.appendChild(crumb);
  titlebar.appendChild(crumbExit);

  const resetBtn = document.createElement("button");
  resetBtn.id = "btn-reset-view";
  resetBtn.textContent = "Reset view";
  resetBtn.style.cssText = "margin-left:auto; padding:3px 10px; font-size:11px; cursor:pointer; background:#21262d; color:#c9d1d9; border:1px solid #30363d; border-radius:4px;";
  resetBtn.onclick = () => resetView();
  titlebar.appendChild(resetBtn);

  const expandFocusBtn = document.createElement("button");
  expandFocusBtn.id = "btn-expand-focus";
  expandFocusBtn.textContent = "Expand & focus";
  expandFocusBtn.style.cssText = "padding:3px 10px; font-size:11px; cursor:pointer; background:#21262d; color:#c9d1d9; border:1px solid #30363d; border-radius:4px;";
  expandFocusBtn.onclick = () => expandAndFocusSelected();
  titlebar.appendChild(expandFocusBtn);

  // ===================== Signal index =====================
  const sigIndex = new Map();
  for (const s of data.signals) {
    sigIndex.set(s.id, {
      id: s.id, labels: s.labels, netClass: s.netClass,
      pinIds: s.pins, deviceSet: new Set(),
      harnessEdges: [], pcbNets: [], fuseLinks: [], relayBreaks: [],
    });
    for (const pid of s.pins) {
      const d = (pinMap.get(pid) || {}).device;
      if (d) sigIndex.get(s.id).deviceSet.add(d);
    }
  }
  for (const e of data.edges) {
    if (e.kind === "harness") {
      const idx = sigIndex.get(e.signalId);
      if (idx) idx.harnessEdges.push(e);
    } else if (e.kind === "pcb-net") {
      const idx = sigIndex.get(e.signalId);
      if (idx) idx.pcbNets.push(e);
    } else if (e.kind === "fuse") {
      const idx = sigIndex.get(e.signalId);
      if (idx) idx.fuseLinks.push(e);
    } else if (e.kind === "relay-contact") {
      for (const sid of [e.signalA, e.signalB]) {
        const idx = sigIndex.get(sid);
        if (idx && !idx.relayBreaks.includes(e)) idx.relayBreaks.push(e);
      }
    }
  }

  // ===================== Side panel =====================
  const siglist = document.getElementById("siglist");
  const detail = document.getElementById("detail");
  const search = document.getElementById("search");
  const esc = (s) => String(s).replace(/[&<>]/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[ch]));
  const dot = (cls) => `<span style="color:${NET_COLOR[cls] || "#8b949e"}">●</span>`;

  function renderList() {
    siglist.innerHTML = "";
    for (const s of data.signals) {
      const labels = s.labels.join(" + ") || "(unnamed)";
      const row = document.createElement("div");
      row.className = "sig";
      row.innerHTML = `${dot(s.netClass)} <b>#${s.id}</b> ${esc(labels)}`;
      row.dataset.text = (labels + " #" + s.id).toLowerCase();
      row.onclick = () => selectSignal(s.id);
      siglist.appendChild(row);
    }
    applySearch();
  }

  function applySearch() {
    const q = search.value.toLowerCase().trim();
    for (const row of siglist.children) {
      row.style.display = !q || row.dataset.text.includes(q) ? "" : "none";
    }
  }
  search.addEventListener("input", applySearch);

  function clearHighlight() {
    cy.elements().removeClass("hl dim");
    detail.innerHTML = "";
    currentSignalId = null;
    crumb.style.display = "none";
    crumbExit.style.display = "none";
    document.getElementById("cy").classList.remove("tracing");
  }

  // Track the currently highlighted signal for "Expand & focus"
  let currentSignalId = null;

  // Non-mutating selectSignal: highlight in place without auto-fit or expand
  function selectSignal(sid) {
    const idx = sigIndex.get(sid);
    if (!idx) return;
    currentSignalId = sid;
    cy.elements().removeClass("hl dim");
    const hl = cy.collection();

    for (const pid of idx.pinIds) {
      const pinNode = cy.getElementById(pid);
      if (pinNode.length && pinNode.style("display") !== "none") {
        hl.merge(pinNode);
        hl.merge(pinNode.ancestors());
      } else {
        // Pin is inside a collapsed device — highlight the device body
        const dev = (pinMap.get(pid) || {}).device;
        if (dev) hl.merge(cy.getElementById(dev));
      }
    }

    // Highlight visible edges carrying this signal
    cy.edges().filter((e) => {
      if (e.style("display") === "none") return false;
      return e.data("signalId") === sid ||
             e.data("signalA") === sid || e.data("signalB") === sid;
    }).forEach((e) => hl.merge(e));

    // Highlight visible meta-edges whose wires carry this signal
    cy.edges("[kind = 'meta']").forEach((e) => {
      const wires = e.data("wires") || [];
      // Check if any wire in this meta-edge belongs to our signal
      const matchingHarness = cy.edges("[kind = 'harness']").filter((he) =>
        wires.includes(he.id()) && he.data("signalId") === sid
      );
      if (matchingHarness.length > 0) {
        if (e.style("display") !== "none") hl.merge(e);
        // Also highlight endpoint devices
        const devs = metaEdgeDevices.get(e.id());
        if (devs) {
          hl.merge(cy.getElementById(devs.a));
          hl.merge(cy.getElementById(devs.b));
        }
      }
    });

    // net tier (lines, junctions, tags) of the same electrical component — only the
    // ones currently visible (their board is expanded), so we never flood the canvas.
    cy.elements(`[component = ${sid}]`).forEach((el) => {
      if (el.style("display") !== "none") hl.merge(el);
    });

    hl.addClass("hl");
    cy.elements().not(hl).addClass("dim");
    // NO cy.fit — non-mutating

    const lbls = idx.labels && idx.labels.length ? idx.labels.join(", ") : "(unlabeled)";
    crumb.textContent = `▶ Tracing #${sid} · ${lbls}`;
    crumb.style.display = "";
    crumbExit.style.display = "";
    document.getElementById("cy").classList.add("tracing");

    renderDetail(idx);
  }

  // Expand & focus: expand all devices containing the current signal + fit
  function expandAndFocusSelected() {
    if (currentSignalId == null) return;
    const idx = sigIndex.get(currentSignalId);
    if (!idx) return;
    for (const dev of idx.deviceSet) expandDevice(dev);
    // Re-apply highlight after expanding
    selectSignalAndFit(currentSignalId);
  }

  function selectSignalAndFit(sid) {
    const idx = sigIndex.get(sid);
    if (!idx) return;
    cy.elements().removeClass("hl dim");
    const hl = cy.collection();
    for (const pid of idx.pinIds) {
      const n = cy.getElementById(pid);
      if (n.length) { hl.merge(n); hl.merge(n.ancestors()); }
    }
    cy.edges().filter((e) => {
      if (e.style("display") === "none") return false;
      return e.data("signalId") === sid ||
             e.data("signalA") === sid || e.data("signalB") === sid;
    }).forEach((e) => hl.merge(e));
    hl.addClass("hl");
    cy.elements().not(hl).addClass("dim");
    if (hl.length) cy.fit(hl, 60);
    renderDetail(idx);
  }

  function renderDetail(idx) {
    const lines = [];
    lines.push(`<h3>#${idx.id} ${dot(idx.netClass)}</h3>`);
    lines.push(`<div>${esc(idx.labels.join(" + ") || "(unnamed)")}</div>`);
    lines.push(`<h3>devices</h3><div>${esc([...idx.deviceSet].sort().join(", "))}</div>`);
    lines.push(`<h3>path</h3><ul>`);
    for (const e of idx.harnessEdges) {
      lines.push(`<li>${esc(e.a)} — ${esc(e.b)}  [${esc(e.label || "")}]</li>`);
    }
    for (const e of idx.pcbNets) {
      lines.push(`<li>${esc(e.board)}: ${esc(e.member)}</li>`);
    }
    for (const e of idx.fuseLinks) {
      const ref = e.a.split(".").slice(0, 2).join(".");
      lines.push(`<li>${esc(ref)}: ${esc(e.a.split(".").pop())}—${esc(e.b.split(".").pop())} fuse</li>`);
    }
    for (const e of idx.relayBreaks) {
      const ref = e.a.split(".").slice(0, 2).join(".");
      const ap = e.a.split(".").pop(), bp = e.b.split(".").pop();
      lines.push(`<li class="break">${esc(ref)}: ${esc(ap)} ⎯/⎯ ${esc(bp)}  (${esc(e.relay)} contact, conditional)</li>`);
    }
    lines.push(`</ul>`);
    detail.innerHTML = lines.join("");
  }

  cy.on("tap", "node[kind = 'pin']", (evt) => {
    const sid = evt.target.data("signalId");
    if (sid != null) selectSignal(sid);
  });

  cy.on("tap", "node[kind = 'net-tag'], node[kind = 'junction']", (evt) => {
    const comp = evt.target.data("component");
    if (comp != null) selectSignal(comp);
  });

  renderList();
}
