"""Net classification: DROPPED / CHAIN / LABEL / POWER.

Power match overrides pin count: any net whose name matches a PowerNetMap
(canonical or alias, with or without leading '/') becomes POWER even if it
has only 2 pins.
"""

from collections.abc import Iterable
from enum import Enum
from typing import Any

from schematika.pcb.model import PowerNetMap

_CHAIN_PIN_COUNT = 2


class NetKind(Enum):
    """Classification of a net by pin count and power status.

    Attributes:
        DROPPED: Net has 0 or 1 pins (unused).
        CHAIN: Net has exactly 2 pins (pass-through).
        LABEL: Net has 3 or more pins (junction).
        POWER: Net matches a configured power net (overrides pin count).
    """

    DROPPED = "dropped"
    CHAIN = "chain"
    LABEL = "label"
    POWER = "power"


def classify_net(net: Any, *, power_nets: Iterable[PowerNetMap]) -> NetKind:  # noqa: ANN401
    """Return the NetKind for ``net`` given the configured power_nets.

    Args:
        net: Object with ``name`` (str) and ``pins`` (sequence) attributes.
        power_nets: Iterable of PowerNetMap objects to check for power match.

    Returns:
        NetKind: One of POWER (if name matches any power_net), DROPPED (≤1 pins),
        CHAIN (exactly 2 pins), or LABEL (3+ pins).
    """
    for pnet in power_nets:
        if pnet.matches(net.name):
            return NetKind.POWER
    pin_count = len(net.pins)
    if pin_count <= 1:
        return NetKind.DROPPED
    if pin_count == _CHAIN_PIN_COUNT:
        return NetKind.CHAIN
    return NetKind.LABEL
