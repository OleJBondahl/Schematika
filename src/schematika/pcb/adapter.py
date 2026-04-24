"""Walk a SKiDL Circuit and emit internal IR for pcb.builder consumption."""

from dataclasses import dataclass

import skidl  # noqa: F401


@dataclass(frozen=True)
class PinRef:
    """Reference to a pin on a part within a net."""

    part_ref: str  # e.g. "F1", "K1", "J2"
    pin_name: str  # SKiDL pin number as string, e.g. "1", "13", "A1"


@dataclass(frozen=True)
class PartRef:
    """Reference to a part in the circuit."""

    ref: str  # e.g. "F1"
    template_name: str  # e.g. "Fuse", "Relay_SPST-NO"
    pin_numbers: tuple[str, ...]  # all pins on this part, stringified


@dataclass(frozen=True)
class NetRef:
    """Reference to a net in the circuit."""

    name: str  # SKiDL net.name (string)
    pins: tuple[PinRef, ...]  # all pins on this net, ordered


@dataclass(frozen=True)
class CircuitIR:
    """Internal IR representation of a SKiDL Circuit."""

    parts: tuple[PartRef, ...]
    nets: tuple[NetRef, ...]


def adapt(circuit: object) -> CircuitIR:
    """Walk a SKiDL Circuit and produce internal IR.

    This is the ONLY place skidl is imported in the pcb package.
    """
    # Collect parts
    parts_list: list[PartRef] = []
    for part in circuit.parts:  # type: ignore[union-attr]
        pin_nums = tuple(str(pin.num) for pin in part.pins)
        parts_list.append(
            PartRef(
                ref=part.ref,
                template_name=part.name,
                pin_numbers=pin_nums,
            )
        )

    # Collect nets, excluding NC
    nets_list: list[NetRef] = []
    nc_net = circuit.NC  # type: ignore[union-attr]

    for net in circuit.nets:  # type: ignore[union-attr]
        # Skip NC net
        if net is nc_net:
            continue

        # Collect pins on this net
        pins_on_net: list[PinRef] = []
        for pin in net.pins:  # type: ignore[union-attr]
            pins_on_net.append(
                PinRef(
                    part_ref=pin.part.ref,
                    pin_name=str(pin.num),
                )
            )

        nets_list.append(
            NetRef(
                name=net.name,
                pins=tuple(pins_on_net),
            )
        )

    return CircuitIR(
        parts=tuple(parts_list),
        nets=tuple(nets_list),
    )
