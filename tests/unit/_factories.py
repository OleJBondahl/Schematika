"""Canonical test factories.

Audit §3 flagged 12+ duplicate `_make_symbol` / `_port` / `factory_with_ports`
helpers across `tests/unit/`. This module holds the single canonical version
for the shapes that were genuinely duplicated. Helpers whose signatures diverge
for good reason (e.g. positional `_make_symbol(x, y, label)` in PID validation
tests that bake geometry into the fixture) stay local to their file.

All names are underscore-free so call sites read naturally; the module's
leading underscore marks the whole file as test-internal.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

from schematika.core.geometry import Point, Vector
from schematika.core.symbol import Port, Symbol

if TYPE_CHECKING:
    from collections.abc import Callable


def make_fake_template(
    name: str,
    pin_nums: tuple[str, ...],
    ref_prefix: str = "U",
) -> SimpleNamespace:
    """Skidl-like template stub with .name, .ref_prefix, .pins[*].num."""
    pins = tuple(SimpleNamespace(num=n) for n in pin_nums)
    return SimpleNamespace(name=name, ref_prefix=ref_prefix, pins=pins)


def port(
    pid: str,
    x: float = 0.0,
    y: float = 0.0,
    dx: float = 0.0,
    dy: float = 1.0,
) -> Port:
    """Build a Port with defaults suitable for trivial test symbols."""
    return Port(pid, Point(x, y), Vector(dx, dy))


def make_symbol(
    label: str | None = None,
    ports: dict[str, Port] | None = None,
) -> Symbol:
    """Minimal Symbol with given ports and label; no drawn elements."""
    return Symbol(elements=[], ports=ports or {}, label=label)


def make_symbol_with_ports(port_ids: tuple[str, ...]) -> Symbol:
    """Symbol with default ports keyed by `port_ids`."""
    return make_symbol(ports={pid: port(pid) for pid in port_ids})


def factory_with_ports(port_ids: tuple[str, ...]) -> Callable[[], Symbol]:
    """Return a zero-arg factory that yields a Symbol with the given ports."""

    def _factory() -> Symbol:
        return make_symbol_with_ports(port_ids)

    return _factory
