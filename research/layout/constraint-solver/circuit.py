"""Synthetic cabinet-circuit generator, grounded in Schematika's real mm scale.

Sizes below are illustrative bounding boxes for IEC 60617 symbols, derived
from ``schematika.core.constants`` (``GRID_SIZE = 5.0`` mm,
``DEFAULT_POLE_SPACING = 10.0`` mm). They are not pulled from a specific
symbol factory's actual SVG bounds -- this is a research spike, not a
production layout engine -- but they are the right order of magnitude for a
fuse, contactor, relay, or terminal block footprint.

Zones mirror a typical ladder-diagram cabinet layout, top to bottom:
incoming disconnect -> protection (fuses/breakers) -> power switching
(contactors) -> control relays -> terminal strip.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

GRID_SIZE = 5.0  # mm, matches schematika.core.constants.GRID_SIZE
GAP = 2 * GRID_SIZE  # mm, minimum clearance between adjacent components

# Y-band (mm) per component kind: "zone pinning by component type".
# Fixed by type, never a decision variable -- IEC ladder convention dictates
# the vertical order, not the solver.
ZONE_Y: dict[str, float] = {
    "MAIN": 0.0,  # incoming disconnect / main breaker
    "F": 60.0,  # fuses / miniature circuit breakers
    "Q": 130.0,  # contactors (power switching)
    "K": 200.0,  # control relays
    "X": 270.0,  # terminal strip
}

# Bounding box (width, height) in mm per kind, illustrative order-of-magnitude.
SIZE: dict[str, tuple[float, float]] = {
    "MAIN": (40.0, 60.0),
    "F": (20.0, 45.0),
    "Q": (35.0, 55.0),
    "K": (30.0, 45.0),
    "X": (8.0, 15.0),
}

# Probability a given circuit touches each optional zone (MAIN and F are
# always present; not every circuit has a contactor or a relay).
ZONE_PRESENCE_P: dict[str, float] = {
    "Q": 0.45,
    "K": 0.65,
}


@dataclass(frozen=True)
class Component:
    """One placed cabinet component: an id, its type, and its circuit.

    Attributes:
        id: Unique tag, e.g. "F3", "K12", "X30".
        kind: Zone key into `ZONE_Y`/`SIZE` ("MAIN", "F", "Q", "K", "X").
        circuit: 1-based circuit index. Column ordering is by this value.
        width: Bounding-box width in mm.
        height: Bounding-box height in mm.
    """

    id: str
    kind: str
    circuit: int
    width: float
    height: float


def generate_cabinet(n_circuits: int, seed: int = 42) -> list[Component]:
    """Build a synthetic cabinet of `n_circuits` ladder circuits.

    Circuit 1 always carries the incoming MAIN disconnect. Every circuit
    gets a fuse (F) and a terminal (X); contactor (Q) and relay (K) are
    present with fixed probability, matching real cabinets where not every
    circuit is motor-switched or relay-controlled.

    Args:
        n_circuits: Number of ladder circuits (columns) to generate.
        seed: RNG seed for reproducible synthetic layouts.

    Returns:
        Flat list of `Component`, unordered across circuits.
    """
    rng = random.Random(seed)
    components: list[Component] = []

    if n_circuits >= 1:
        w, h = SIZE["MAIN"]
        components.append(Component("MAIN1", "MAIN", 1, w, h))

    for circuit in range(1, n_circuits + 1):
        w, h = SIZE["F"]
        components.append(Component(f"F{circuit}", "F", circuit, w, h))

        if rng.random() < ZONE_PRESENCE_P["Q"]:
            w, h = SIZE["Q"]
            components.append(Component(f"Q{circuit}", "Q", circuit, w, h))

        if rng.random() < ZONE_PRESENCE_P["K"]:
            w, h = SIZE["K"]
            components.append(Component(f"K{circuit}", "K", circuit, w, h))

        w, h = SIZE["X"]
        components.append(Component(f"X{circuit}", "X", circuit, w, h))

    return components
