"""SVG path command ADT: parse, serialize, and per-command translate."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

import deal

if TYPE_CHECKING:
    from collections.abc import Iterable

_PATH_TOKEN_RE = re.compile(r"[a-zA-Z]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


@dataclass(frozen=True, slots=True)
class Move:
    """Absolute M command."""

    x: float
    y: float


@dataclass(frozen=True, slots=True)
class Line:
    """Absolute L command."""

    x: float
    y: float


@dataclass(frozen=True, slots=True)
class HLine:
    """Absolute H command."""

    x: float


@dataclass(frozen=True, slots=True)
class VLine:
    """Absolute V command."""

    y: float


@dataclass(frozen=True, slots=True)
class Curve:
    """Absolute C command (cubic bezier)."""

    x1: float
    y1: float
    x2: float
    y2: float
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class Smooth:
    """Absolute S command (smooth cubic bezier)."""

    x2: float
    y2: float
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class Quad:
    """Absolute Q command (quadratic bezier)."""

    x1: float
    y1: float
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class Tangent:
    """Absolute T command (smooth quadratic bezier)."""

    x: float
    y: float


@dataclass(frozen=True, slots=True)
class Close:
    """Preserves original 'Z' vs 'z' case."""

    case: str


@dataclass(frozen=True, slots=True)
class PassThrough:
    """Non-absolute or unknown token — round-trips unchanged."""

    token: str


PathCommand = (
    Move | Line | HLine | VLine | Curve | Smooth | Quad | Tangent | Close | PassThrough
)


@deal.pure
def tokenize_path_d(d: str) -> list[str]:
    """Shared by parse() and _rotate_path_d to avoid duplicating the regex."""
    return _PATH_TOKEN_RE.findall(d)


@deal.pure
def parse(d: str) -> tuple[PathCommand, ...]:
    """Tokenize *d* and fold tokens into typed PathCommand values."""
    tokens = tokenize_path_d(d)
    result: list[PathCommand] = []
    i = 0
    cmd = ""

    while i < len(tokens):
        token = tokens[i]
        if token.isalpha():
            cmd = token
            if cmd in ("Z", "z"):
                result.append(Close(cmd))
            elif cmd not in ("M", "L", "H", "V", "C", "S", "Q", "T"):
                # Relative or unknown command — emit the letter as PassThrough
                result.append(PassThrough(cmd))
            i += 1
            continue

        if cmd in ("Z", "z"):
            # Spurious numbers after Z/z — skip them (mirrors old state-machine)
            i += 1
        elif cmd == "M" and i + 1 < len(tokens) and not tokens[i + 1].isalpha():
            result.append(Move(float(token), float(tokens[i + 1])))
            i += 2
        elif cmd == "L" and i + 1 < len(tokens) and not tokens[i + 1].isalpha():
            result.append(Line(float(token), float(tokens[i + 1])))
            i += 2
        elif cmd == "T" and i + 1 < len(tokens) and not tokens[i + 1].isalpha():
            result.append(Tangent(float(token), float(tokens[i + 1])))
            i += 2
        elif cmd == "H":
            result.append(HLine(float(token)))
            i += 1
        elif cmd == "V":
            result.append(VLine(float(token)))
            i += 1
        elif cmd in ("S", "Q"):
            new_cmds, consumed = _parse_csq_pairs(tokens, i, 2, cmd)
            result.extend(new_cmds)
            i += consumed
        elif cmd == "C":
            new_cmds, consumed = _parse_csq_pairs(tokens, i, 3, cmd)
            result.extend(new_cmds)
            i += consumed
        else:
            # Relative or unknown number — pass through raw
            result.append(PassThrough(token))
            i += 1

    return tuple(result)


@deal.pure
def _parse_csq_pairs(
    tokens: list[str],
    start: int,
    pair_count: int,
    letter: str,
) -> tuple[tuple[PathCommand, ...], int]:
    """Returns (commands_to_emit, tokens_consumed). PassThrough on incomplete pairs."""
    raw_tokens: list[str] = []
    coords: list[float] = []
    i = start
    complete = True
    for _ in range(pair_count):
        if i + 1 < len(tokens) and not tokens[i + 1].isalpha():
            raw_tokens.append(tokens[i])
            raw_tokens.append(tokens[i + 1])
            coords.append(float(tokens[i]))
            coords.append(float(tokens[i + 1]))
            i += 2
        else:
            # Orphan token — collect it and stop
            raw_tokens.append(tokens[i])
            i += 1
            complete = False
            break

    new_cmds: list[PathCommand]
    if complete:
        if letter == "C":
            new_cmds = [
                Curve(coords[0], coords[1], coords[2], coords[3], coords[4], coords[5])
            ]
        elif letter == "S":
            new_cmds = [Smooth(coords[0], coords[1], coords[2], coords[3])]
        else:
            new_cmds = [Quad(coords[0], coords[1], coords[2], coords[3])]
    else:
        # Incomplete C/S/Q: emit letter + all collected numbers as PassThrough.
        # Translation skips this whole arm (round-trips unchanged) — mirrors the
        # original _translate_path_d which broke out without translating partial pairs.
        new_cmds = [PassThrough(letter)]
        for token_text in raw_tokens:
            new_cmds.append(PassThrough(token_text))

    return tuple(new_cmds), i - start


@deal.pure
def serialize(commands: Iterable[PathCommand]) -> str:
    """Inverse of parse — join commands back to an SVG path 'd' string."""
    parts: list[str] = []
    for cmd in commands:
        match cmd:
            case Move(x, y):
                parts.extend(["M", str(x), str(y)])
            case Line(x, y):
                parts.extend(["L", str(x), str(y)])
            case HLine(x):
                parts.extend(["H", str(x)])
            case VLine(y):
                parts.extend(["V", str(y)])
            case Curve(x1, y1, x2, y2, x, y):
                parts.extend(["C", str(x1), str(y1), str(x2), str(y2), str(x), str(y)])
            case Smooth(x2, y2, x, y):
                parts.extend(["S", str(x2), str(y2), str(x), str(y)])
            case Quad(x1, y1, x, y):
                parts.extend(["Q", str(x1), str(y1), str(x), str(y)])
            case Tangent(x, y):
                parts.extend(["T", str(x), str(y)])
            case Close(case):
                parts.append(case)
            case PassThrough(token):
                parts.append(token)
    return " ".join(parts)


@deal.pure
def translate_command(cmd: PathCommand, dx: float, dy: float) -> PathCommand:
    """Translate a single absolute command by (dx, dy); PassThrough/Close unchanged."""
    result: PathCommand
    match cmd:
        case Move(x, y):
            result = Move(x + dx, y + dy)
        case Line(x, y):
            result = Line(x + dx, y + dy)
        case HLine(x):
            result = HLine(x + dx)
        case VLine(y):
            result = VLine(y + dy)
        case Curve(x1, y1, x2, y2, x, y):
            result = Curve(x1 + dx, y1 + dy, x2 + dx, y2 + dy, x + dx, y + dy)
        case Smooth(x2, y2, x, y):
            result = Smooth(x2 + dx, y2 + dy, x + dx, y + dy)
        case Quad(x1, y1, x, y):
            result = Quad(x1 + dx, y1 + dy, x + dx, y + dy)
        case Tangent(x, y):
            result = Tangent(x + dx, y + dy)
        case Close() | PassThrough():
            result = cmd
    return result
