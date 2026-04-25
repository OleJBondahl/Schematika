"""Pure `translate` / `rotate` (singledispatch) for Points, Ports, Symbols, Elements."""

import math
import warnings
from dataclasses import replace
from functools import singledispatch
from typing import Any, Final, cast

import deal

from schematika._purity import pure
from schematika.core.constants import TEXT_OFFSET_X
from schematika.core.geometry import Element, Point, Vector
from schematika.core.primitives import Circle, Group, Line, Path, Polygon, Text
from schematika.core.svg_path import parse as _svg_parse
from schematika.core.svg_path import serialize as _svg_serialize
from schematika.core.svg_path import tokenize_path_d  # re-export for old import paths
from schematika.core.svg_path import translate_command as _svg_translate_command
from schematika.core.symbol import Port, Symbol

_ORIGIN = Point(0, 0)

# Tolerance for comparing angles to 180° for text anchor flipping.
_TEXT_ANGLE_THRESHOLD: Final = 0.1


@pure
def translate[T: Element | Point | Port | Vector](obj: T, dx: float, dy: float) -> T:
    """Returns a new instance translated by (dx, dy)."""
    result: object
    match obj:
        case Point(x, y):
            result = Point(x + dx, y + dy)
        case Port():
            result = replace(obj, position=translate(obj.position, dx, dy))
        case Line():
            result = replace(
                obj,
                start=translate(obj.start, dx, dy),
                end=translate(obj.end, dx, dy),
            )
        case Circle():
            result = replace(obj, center=translate(obj.center, dx, dy))
        case Text():
            result = replace(obj, position=translate(obj.position, dx, dy))
        case Group():
            result = replace(obj, elements=[translate(e, dx, dy) for e in obj.elements])
        case Polygon():
            result = replace(obj, points=[translate(p, dx, dy) for p in obj.points])
        case Path():
            new_d = _translate_path_d(obj.d, dx, dy)
            result = replace(obj, d=new_d)
        case Symbol():
            new_elements = [translate(e, dx, dy) for e in obj.elements]
            new_ports = {k: translate(p, dx, dy) for k, p in obj.ports.items()}
            result = replace(obj, elements=new_elements, ports=new_ports)
        case _:
            warnings.warn(
                f"translate() has no handler for {type(obj).__name__},"
                " returning unchanged",
                RuntimeWarning,
                stacklevel=2,
            )
            result = obj
    return cast("T", result)


@deal.pure
def rotate_point(p: Point, angle_deg: float, center: Point = _ORIGIN) -> Point:
    """Clockwise in SVG coords (Y points down)."""
    angle_rad = math.radians(angle_deg)
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)

    # Translate to origin
    tx = p.x - center.x
    ty = p.y - center.y

    # Rotate
    rx = tx * cos_a - ty * sin_a
    ry = tx * sin_a + ty * cos_a

    # Translate back
    return Point(rx + center.x, ry + center.y)


@deal.pure
def rotate_vector(v: Vector, angle_deg: float) -> Vector:
    """Rotates a vector by *angle_deg*."""
    angle_rad = math.radians(angle_deg)
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    return Vector(v.dx * cos_a - v.dy * sin_a, v.dx * sin_a + v.dy * cos_a)


@deal.pure
def _translate_path_d(d: str, dx: float, dy: float) -> str:
    """Shifts absolute SVG path coords; relative (lowercase) commands pass through."""
    return _svg_serialize(_svg_translate_command(c, dx, dy) for c in _svg_parse(d))


@pure
@singledispatch
def rotate(obj: Any, angle: float, center: Point = _ORIGIN) -> Any:  # noqa: ANN401, ARG001
    """Singledispatch; default handler warns and returns *obj* unchanged."""
    warnings.warn(
        f"rotate() has no handler for {type(obj).__name__}, returning unchanged",
        RuntimeWarning,
        stacklevel=2,
    )
    return obj


@pure
@rotate.register
def _(obj: Point, angle: float, center: Point = _ORIGIN) -> Point:
    return rotate_point(obj, angle, center)


@pure
@rotate.register
def _(obj: Port, angle: float, center: Point = _ORIGIN) -> Port:
    return replace(
        obj,
        position=rotate_point(obj.position, angle, center),
        direction=rotate_vector(obj.direction, angle),
    )


@pure
@rotate.register
def _(obj: Line, angle: float, center: Point = _ORIGIN) -> Line:
    return replace(
        obj,
        start=rotate_point(obj.start, angle, center),
        end=rotate_point(obj.end, angle, center),
    )


@pure
@rotate.register
def _(obj: Group, angle: float, center: Point = _ORIGIN) -> Group:
    return replace(obj, elements=[rotate(e, angle, center) for e in obj.elements])


@pure
@rotate.register
def _(obj: Polygon, angle: float, center: Point = _ORIGIN) -> Polygon:
    return replace(obj, points=[rotate_point(p, angle, center) for p in obj.points])


@pure
@rotate.register
def _(obj: Symbol, angle: float, center: Point = _ORIGIN) -> Symbol:
    new_elements = []
    for e in obj.elements:
        rotated_e = rotate(e, angle, center)

        # Special case: If this is the main label, force it to stick to the Left
        # We identify the main label if it matches the Symbol's label content
        if isinstance(rotated_e, Text) and obj.label and rotated_e.content == obj.label:
            forced_pos = Point(center.x + TEXT_OFFSET_X, center.y)

            rotated_e = replace(
                rotated_e, position=forced_pos, anchor="end"
            )  # Always end-aligned (growing left)

        new_elements.append(rotated_e)

    new_ports = {k: rotate(p, angle, center) for k, p in obj.ports.items()}
    return replace(obj, elements=new_elements, ports=new_ports)


@pure
@rotate.register
def _(obj: Circle, angle: float, center: Point = _ORIGIN) -> Circle:
    return replace(obj, center=rotate_point(obj.center, angle, center))


@pure
@rotate.register
def _(obj: Text, angle: float, center: Point = _ORIGIN) -> Text:
    new_pos = rotate_point(obj.position, angle, center)
    new_anchor = obj.anchor

    # Handle 180 degree rotation for text readability/positioning
    norm_angle = angle % 360
    if abs(norm_angle - 180) < _TEXT_ANGLE_THRESHOLD:
        if obj.anchor == "start":
            new_anchor = "end"
        elif obj.anchor == "end":
            new_anchor = "start"

    return replace(obj, position=new_pos, anchor=new_anchor)


@pure
@rotate.register
def _(obj: Path, angle: float, center: Point = _ORIGIN) -> Path:
    new_d = _rotate_path_d(obj.d, angle, center)
    return replace(obj, d=new_d)


@deal.pure
def _rotate_path_d(d: str, angle_deg: float, center: Point) -> str:
    """H/V become L after rotation; relative commands pass through."""
    angle_rad = math.radians(angle_deg)
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)

    def _rot(x: float, y: float) -> tuple[float, float]:
        tx = x - center.x
        ty = y - center.y
        rx = tx * cos_a - ty * sin_a
        ry = tx * sin_a + ty * cos_a
        return rx + center.x, ry + center.y

    tokens = tokenize_path_d(d)
    result: list[str] = []
    i = 0
    cmd = ""
    last_x, last_y = 0.0, 0.0

    while i < len(tokens):
        token = tokens[i]
        if token.isalpha():
            cmd = token
            if cmd not in ("H", "V"):
                result.append(cmd)
            i += 1
            continue

        if cmd in ("M", "L", "T"):
            if i + 1 < len(tokens) and not tokens[i + 1].isalpha():
                x, y = float(token), float(tokens[i + 1])
                rx, ry = _rot(x, y)
                result.append(f"{rx} {ry}")
                last_x, last_y = x, y
                i += 2
            else:
                result.append(token)
                i += 1
        elif cmd == "H":
            x = float(token)
            result.append("L")
            rx, ry = _rot(x, last_y)
            result.append(f"{rx} {ry}")
            last_x = x
            i += 1
        elif cmd == "V":
            y = float(token)
            result.append("L")
            rx, ry = _rot(last_x, y)
            result.append(f"{rx} {ry}")
            last_y = y
            i += 1
        elif cmd in ("C", "S", "Q"):
            pair_count = {"C": 3, "S": 2, "Q": 2}[cmd]
            for _ in range(pair_count):
                if i + 1 < len(tokens) and not tokens[i + 1].isalpha():
                    x, y = float(tokens[i]), float(tokens[i + 1])
                    rx, ry = _rot(x, y)
                    result.append(f"{rx} {ry}")
                    last_x, last_y = x, y
                    i += 2
                else:
                    result.append(tokens[i])
                    i += 1
                    break
        elif cmd in ("z", "Z"):
            i += 1
        else:
            result.append(token)
            i += 1

    return " ".join(result)
