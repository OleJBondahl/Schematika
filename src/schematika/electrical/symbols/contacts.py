"""IEC 60617 contact factories: NO, NC, SPDT (changeover)."""

from schematika.electrical.model.constants import (
    COLOR_BLACK,
    GRID_SIZE,
    NC_CONTACT_PINS,
    NO_CONTACT_PINS,
    SPACING_NARROW,
    SPDT_1P_PINS,
    SPDT_PIN_LABEL_OFFSET,
    TEXT_FONT_FAMILY_AUX,
    TEXT_SIZE_PIN,
)
from schematika.electrical.model.core import Point, Port, Style, Symbol, Vector
from schematika.electrical.model.parts import (
    create_extended_blade,
    create_pin_labels,
    multipole,
    pad_pins,
    standard_style,
    standard_text,
)
from schematika.electrical.model.primitives import Element, Line, Text
from schematika.electrical.utils.transform import translate


def _no_contact_single_pole(
    label: str = "", pins: tuple[str, ...] = NO_CONTACT_PINS
) -> Symbol:
    """Single-pole normally open contact implementation."""
    h_half = GRID_SIZE  # 5.0

    # Gap: -2.5 to 2.5 (5mm gap)
    top_y = -GRID_SIZE / 2
    bot_y = GRID_SIZE / 2

    style = standard_style()

    # Vertical leads
    l1 = Line(Point(0, -h_half), Point(0, top_y), style)
    l2 = Line(Point(0, bot_y), Point(0, h_half), style)

    # Blade
    # Starts at the bottom contact point (0, 2.5)
    # End to the LEFT (-2.5, -2.5)
    blade_start = Point(0, bot_y)
    blade_end = Point(-GRID_SIZE / 2, top_y)

    blade = Line(blade_start, blade_end, style)

    elements: list[Element] = [l1, l2, blade]
    if label:
        elements.append(standard_text(label, Point(0, 0)))

    ports = {
        "1": Port("1", Point(0, -h_half), Vector(0, -1)),
        "2": Port("2", Point(0, h_half), Vector(0, 1)),
    }

    if pins:
        elements.extend(create_pin_labels(ports, pins))

    return Symbol(elements, ports, label=label)


def no_contact(
    label: str = "",
    poles: int = 1,
    pins: tuple[str, ...] | None = None,
) -> Symbol:
    """IEC 60617 normally open (NO) contact.

    Default pin IDs follow IEC 60617: ``"13"`` / ``"14"`` for a 1-pole contact.
    Multi-pole contacts use sequential pairs ``("1","2","3","4",...)`` so each
    circuit builder pole gets its own numerically-labelled ports.

    Ports:
        13, 14: IEC default for 1-pole (top/bottom).
        1, 2, 3, 4, ...: sequential pairs when poles > 1 or custom ``pins``.

    Args:
        label: Component tag, e.g. ``"K1"``.
        poles: Number of poles (1, 2, 3, ...).
        pins: Custom pin designations; defaults to IEC standard for the pole count.

    Returns:
        Symbol with one port-pair per pole.

    Examples:
        >>> from schematika.electrical.symbols import no_contact
        >>> sym = no_contact()
        >>> sorted(sym.ports.keys())
        ['13', '14']
        >>> sym2 = no_contact(poles=2)
        >>> sorted(sym2.ports.keys())
        ['1', '2', '3', '4']
    """
    if pins is None:
        if poles == 1:
            pins = NO_CONTACT_PINS
        else:
            pins = tuple(str(i) for i in range(1, poles * 2 + 1))

    if poles == 1:
        sym = _no_contact_single_pole(label=label, pins=pins)
        # Remap sequential port keys to IEC pin labels
        remapped = {}
        for old_key, pin_label in zip(("1", "2"), pins, strict=False):
            if old_key in sym.ports and pin_label:
                p = sym.ports[old_key]
                remapped[pin_label] = Port(pin_label, p.position, p.direction)
            elif old_key in sym.ports:
                remapped[old_key] = sym.ports[old_key]
        return Symbol(sym.elements, remapped, label=sym.label)

    factory = multipole(_no_contact_single_pole, poles)
    return factory(label=label, pins=pins)


def _nc_contact_single_pole(
    label: str = "", pins: tuple[str, ...] = NC_CONTACT_PINS
) -> Symbol:
    """Single-pole normally closed contact implementation."""
    h_half = GRID_SIZE  # 5.0
    top_y = -GRID_SIZE / 2  # -2.5
    bot_y = GRID_SIZE / 2  # 2.5

    style = standard_style()

    # Vertical lines (Terminals)
    l1 = Line(Point(0, -h_half), Point(0, top_y), style)
    l2 = Line(Point(0, bot_y), Point(0, h_half), style)

    # Horizontal Seat (Contact point)
    # Extends from top contact point to the right, to meet the blade
    seat_end_x = GRID_SIZE / 2  # 2.5
    seat = Line(Point(0, top_y), Point(seat_end_x, top_y), style)

    # Blade: starts bottom-center, passes through the seat endpoint
    blade_start = Point(0, bot_y)
    blade_target = Point(seat_end_x, top_y)
    blade = create_extended_blade(blade_start, blade_target, style)

    elements: list[Element] = [l1, l2, seat, blade]

    if label:
        elements.append(standard_text(label, Point(0, 0)))

    ports = {
        "1": Port("1", Point(0, -h_half), Vector(0, -1)),
        "2": Port("2", Point(0, h_half), Vector(0, 1)),
    }

    if pins:
        elements.extend(create_pin_labels(ports, pins))

    return Symbol(elements, ports, label=label)


def nc_contact(
    label: str = "",
    poles: int = 1,
    pins: tuple[str, ...] | None = None,
) -> Symbol:
    """IEC 60617 normally closed (NC) contact.

    Default pin IDs follow IEC 60617: ``"11"`` / ``"12"`` for a 1-pole contact.
    Multi-pole contacts use sequential pairs.

    Ports:
        11, 12: IEC default for 1-pole (top/bottom).
        1, 2, 3, 4, ...: sequential pairs when poles > 1 or custom ``pins``.

    Args:
        label: Component tag, e.g. ``"K1"``.
        poles: Number of poles (1, 2, 3, ...).
        pins: Custom pin designations; defaults to IEC standard for the pole count.

    Returns:
        Symbol with one port-pair per pole.

    Examples:
        >>> from schematika.electrical.symbols import nc_contact
        >>> sym = nc_contact()
        >>> sorted(sym.ports.keys())
        ['11', '12']
        >>> sym2 = nc_contact(poles=2)
        >>> sorted(sym2.ports.keys())
        ['1', '2', '3', '4']
    """
    if pins is None:
        if poles == 1:
            pins = NC_CONTACT_PINS
        else:
            pins = tuple(str(i) for i in range(1, poles * 2 + 1))

    if poles == 1:
        sym = _nc_contact_single_pole(label=label, pins=pins)
        # Remap sequential port keys to IEC pin labels
        remapped = {}
        for old_key, pin_label in zip(("1", "2"), pins, strict=False):
            if old_key in sym.ports and pin_label:
                p = sym.ports[old_key]
                remapped[pin_label] = Port(pin_label, p.position, p.direction)
            elif old_key in sym.ports:
                remapped[old_key] = sym.ports[old_key]
        return Symbol(sym.elements, remapped, label=sym.label)

    factory = multipole(_nc_contact_single_pole, poles)
    return factory(label=label, pins=pins)


def _spdt_contact_single_pole(
    label: str = "", pins: tuple[str, ...] = SPDT_1P_PINS, *, inverted: bool = False
) -> Symbol:
    r"""Single-pole SPDT contact implementation."""
    h_half = GRID_SIZE  # 5.0

    # Standard Orientation
    top_y = -GRID_SIZE / 2  # -2.5
    bot_y = GRID_SIZE / 2  # 2.5

    x_right = GRID_SIZE / 2  # 2.5
    x_left = -GRID_SIZE / 2  # -2.5

    style = standard_style()

    elements: list[Element] = []

    # Port keys = pin labels
    p_safe = pad_pins(pins, 3)
    com_key = p_safe[0] or "11"
    nc_key = p_safe[1] or "12"
    no_key = p_safe[2] or "14"

    if not inverted:
        # Standard: Common (Input) - Bottom Right
        l_com = Line(Point(x_right, bot_y), Point(x_right, h_half), style)

        # NO (Output) - Top Right
        l_no = Line(Point(x_right, -h_half), Point(x_right, top_y), style)

        # NC (Output) - Top Left
        l_nc = Line(Point(x_left, -h_half), Point(x_left, top_y), style)

        # NC Seat (Top)
        nc_seat_end_x = 0
        seat_nc = Line(Point(x_left, top_y), Point(nc_seat_end_x, top_y), style)

        # Blade: Common (Bot Right) -> NC Seat (Top Center)
        blade_start = Point(x_right, bot_y)
        target_x = nc_seat_end_x
        target_y = top_y

        ports = {
            com_key: Port(com_key, Point(x_right, h_half), Vector(0, 1)),
            nc_key: Port(nc_key, Point(x_left, -h_half), Vector(0, -1)),
            no_key: Port(no_key, Point(x_right, -h_half), Vector(0, -1)),
        }
    else:
        # Inverted: Common (Input) - Top Right
        # Common line goes UP from pivot
        l_com = Line(Point(x_right, top_y), Point(x_right, -h_half), style)

        # NO (Output) - Bottom Right
        l_no = Line(Point(x_right, bot_y), Point(x_right, h_half), style)

        # NC (Output) - Bottom Left
        l_nc = Line(Point(x_left, bot_y), Point(x_left, h_half), style)

        # NC Seat (Bottom)
        nc_seat_end_x = 0
        seat_nc = Line(Point(x_left, bot_y), Point(nc_seat_end_x, bot_y), style)

        # Blade: Common (Top Right) -> NC Seat (Bottom Center)
        blade_start = Point(x_right, top_y)
        target_x = nc_seat_end_x
        target_y = bot_y

        ports = {
            com_key: Port(com_key, Point(x_right, -h_half), Vector(0, -1)),
            nc_key: Port(nc_key, Point(x_left, h_half), Vector(0, 1)),
            no_key: Port(no_key, Point(x_right, h_half), Vector(0, 1)),
        }

    # Calculate Blade (Shared Logic)
    blade_target = Point(target_x, target_y)
    blade = create_extended_blade(blade_start, blade_target, style)

    elements.extend([l_com, l_no, l_nc, seat_nc, blade])

    if label:
        elements.append(standard_text(label, Point(0, 0)))

    if pins:
        common_pin, nc_pin, no_pin = p_safe[0], p_safe[1], p_safe[2]

        offset = SPDT_PIN_LABEL_OFFSET

        if common_pin:
            pos = ports[com_key].position
            elements.append(
                Text(
                    content=common_pin,
                    position=Point(pos.x + offset, pos.y),
                    anchor="start",
                    font_size=TEXT_SIZE_PIN,
                    style=Style(
                        stroke="none",
                        fill=COLOR_BLACK,
                        font_family=TEXT_FONT_FAMILY_AUX,
                    ),
                )
            )

        if nc_pin:
            pos = ports[nc_key].position
            elements.append(
                Text(
                    content=nc_pin,
                    position=Point(pos.x - offset, pos.y),
                    anchor="end",
                    font_size=TEXT_SIZE_PIN,
                    style=Style(
                        stroke="none",
                        fill=COLOR_BLACK,
                        font_family=TEXT_FONT_FAMILY_AUX,
                    ),
                )
            )

        if no_pin:
            pos = ports[no_key].position
            elements.append(
                Text(
                    content=no_pin,
                    position=Point(pos.x + offset, pos.y),
                    anchor="start",
                    font_size=TEXT_SIZE_PIN,
                    style=Style(
                        stroke="none",
                        fill=COLOR_BLACK,
                        font_family=TEXT_FONT_FAMILY_AUX,
                    ),
                )
            )

    return Symbol(elements, ports, label=label)


def _multi_pole_spdt(
    label: str = "",
    poles: int = 3,
    pins: tuple[str, ...] = (),
) -> Symbol:
    """Multi-pole SPDT contact composition."""
    expected = poles * 3
    if not pins:
        pins = tuple(f"{p}{s}" for p in range(1, poles + 1) for s in ("1", "2", "4"))
    if len(pins) < expected:
        pins = tuple(list(pins) + [""] * (expected - len(pins)))

    spacing = SPACING_NARROW

    all_elements = []
    all_ports: dict = {}
    for i in range(poles):
        p = _spdt_contact_single_pole(
            label=label if i == 0 else "", pins=pins[i * 3 : i * 3 + 3]
        )
        if i > 0:
            p = translate(p, spacing * i, 0)
        all_elements.extend(p.elements)
        all_ports.update(p.ports)

    return Symbol(all_elements, all_ports, label=label)


def spdt_contact(
    label: str = "",
    poles: int = 1,
    pins: tuple[str, ...] | None = None,
    *,
    inverted: bool = False,
) -> Symbol:
    """IEC 60617 changeover (SPDT) contact — 3 ports per pole: COM, NC, NO.

    Default IEC pin IDs for 1-pole: ``"11"`` (COM), ``"12"`` (NC), ``"14"`` (NO).
    For multi-pole the pattern is ``"N1"``, ``"N2"``, ``"N4"`` per pole N.

    Ports:
        11: common (COM) — pole 1.
        12: normally closed (NC) — pole 1.
        14: normally open (NO) — pole 1.
        21, 22, 24: COM/NC/NO for pole 2 (if poles >= 2); etc.

    Args:
        label: Component tag, e.g. ``"S1"``.
        poles: Number of poles (1, 2, 3, ...).
        pins: Custom pin designations (3 per pole); defaults to IEC non-sequential.
        inverted: When ``True``, COM is at the top instead of the bottom.

    Returns:
        Symbol with 3 ports per pole.

    Examples:
        >>> from schematika.electrical.symbols import spdt_contact
        >>> sym = spdt_contact()
        >>> sorted(sym.ports.keys())
        ['11', '12', '14']
        >>> sym2 = spdt_contact(poles=2)
        >>> sorted(sym2.ports.keys())
        ['11', '12', '14', '21', '22', '24']
    """
    if pins is None:
        if poles == 1:
            pins = SPDT_1P_PINS
        else:
            pins = tuple(
                f"{p}{s}" for p in range(1, poles + 1) for s in ("1", "2", "4")
            )

    if poles == 1:
        return _spdt_contact_single_pole(label=label, pins=pins, inverted=inverted)

    return _multi_pole_spdt(label=label, poles=poles, pins=pins)
