"""Route — a signal through N concrete points, decomposed into Wires.

A field-device run (device-pin -> terminal -> PLC) is a 3-waypoint ``Route``
that decomposes into two ``Wire``s sharing one net. ``Route`` is the reusable
multi-point primitive that complements the 2-point ``Wire``; it is transient
(decomposed at build time), the stored truth being the ``Wire``s it yields.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from schematika.catalog.errors import CatalogValidationError
from schematika.catalog.wires import Wire

if TYPE_CHECKING:
    from schematika.catalog.identifiers import NetId
    from schematika.catalog.refs import PinRef


_MIN_WAYPOINTS = 2


@dataclass(frozen=True, slots=True, kw_only=True)
class Route:
    """A signal routed through ``N >= 2`` concrete waypoints.

    Attributes:
        net: Net carried by every wire this route decomposes into.
        waypoints: Ordered pins the signal passes through; length ``>= 2``.

    Examples:
        >>> from schematika.catalog.identifiers import DeviceTag, NetId
        >>> from schematika.catalog.refs import PinRef
        >>> from schematika.catalog.routes import Route, route_to_wires
        >>> a = PinRef(device=DeviceTag("-M1"), port_id="U")
        >>> t = PinRef(device=DeviceTag("X100"), port_id="1")
        >>> len(route_to_wires(Route(net=NetId("M1_U"), waypoints=(a, t))))
        1
    """

    net: NetId
    waypoints: tuple[PinRef, ...]

    def __post_init__(self) -> None:
        """Reject a route that cannot decompose into at least one wire."""
        if len(self.waypoints) < _MIN_WAYPOINTS:
            msg = (
                f"Route needs >= {_MIN_WAYPOINTS} waypoints, got {len(self.waypoints)}"
            )
            raise CatalogValidationError(msg)


def route_to_wires(route: Route, /) -> tuple[Wire, ...]:
    """Decompose a route into one ``Wire`` per consecutive waypoint pair.

    Each emitted wire carries ``route.net``; colors/lengths are not set here
    (they are attached by the Layer-2 builder from cable data).

    Args:
        route: The route to decompose.

    Returns:
        One ``Wire`` per adjacent waypoint pair, in order.

    Examples:
        >>> from schematika.catalog.identifiers import DeviceTag, NetId
        >>> from schematika.catalog.refs import PinRef
        >>> from schematika.catalog.routes import Route, route_to_wires
        >>> a = PinRef(device=DeviceTag("-M1"), port_id="U")
        >>> t = PinRef(device=DeviceTag("X100"), port_id="1")
        >>> p = PinRef(device=DeviceTag("PLC-DI1"), port_id="3")
        >>> [w.net for w in route_to_wires(Route(net=NetId("s"), waypoints=(a, t, p)))]
        ['s', 's']
    """
    pairs = zip(route.waypoints, route.waypoints[1:], strict=False)
    return tuple(Wire(net=route.net, source=a, target=b) for a, b in pairs)
