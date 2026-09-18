"""Design sketch: a schemdraw-style relative-placement cursor layered on
Schematika's REAL CircuitBuilder (not schemdraw's own element/symbol classes).

Status: research prototype for the llm-dsl-pipeline spike
(docs/research/layout-improvement/llm-dsl-pipeline.md). Not wired into
src/schematika. Not proposed for production as written -- see the "verdict"
section of the design doc for why.

Design summary
--------------
schemdraw's ``d += elm.Resistor().right()`` works by mutating an implicit
"drawing cursor" (current position + heading) on every element add. This
module reproduces that shape using Schematika's own symbol factories and its
*existing* relative-placement primitives (``PlacementOptions.relative_to`` +
``position`` on ``CircuitBuilder``, ``ComponentRef``/``PortRef`` for named
anchors) rather than schemdraw's coordinate/anchor model, which uses
different symbols and a different port convention.

The important discovery this sketch exists to demonstrate: CircuitBuilder
*already* has relative placement built in (``relative_to=ref``,
``position="above"/"below"/"left"/"right"``, ``spacing=...``). This Cursor
class adds essentially nothing new -- it is a thin renaming layer that
hides the same PlacementOptions/SymbolConfig calls behind ``.right()``/
``.down()`` method names, at the cost of introducing *new* implicit state
(the cursor's "current position and heading") that CircuitBuilder's
explicit ``relative_to=<named ref>`` calls do not have.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from schematika.core.geometry import Point
from schematika.core.options import (
    PlacementOptions,
    SymbolConfig,
    TerminalConfig,
)
from schematika.electrical.builder import CircuitBuilder
from schematika.electrical.builder_models import ComponentRef, PortRef
from schematika.electrical.model.core import SymbolFactory

Direction = Literal["above", "below", "left", "right"]


@dataclass
class Cursor:
    """Tracks an implicit "current anchor + heading" and emits CircuitBuilder calls.

    This is the shape an LLM would be asked to generate instead of direct
    CircuitBuilder calls. Every method returns ``self`` for chaining, mirroring
    schemdraw's ``d += elm.R().right()`` fluent style.

    Attributes:
        builder: The CircuitBuilder being driven. Owned by the caller.
    """

    builder: CircuitBuilder
    _last: ComponentRef | PortRef | None = None
    _heading: Direction = "below"

    def down(
        self,
        factory: SymbolFactory,
        /,
        *,
        tag: str,
        spacing: float | None = None,
        **factory_kwargs: object,
    ) -> Cursor:
        """Place a symbol below the cursor's current anchor."""
        return self._place_symbol(factory, tag=tag, heading="below", spacing=spacing, **factory_kwargs)

    def right(
        self,
        factory: SymbolFactory,
        /,
        *,
        tag: str,
        spacing: float | None = None,
        **factory_kwargs: object,
    ) -> Cursor:
        """Place a symbol to the right of the cursor's current anchor."""
        return self._place_symbol(factory, tag=tag, heading="right", spacing=spacing, **factory_kwargs)

    def terminal(self, tm_id: str, /, *, poles: int = 1) -> Cursor:
        """Place a terminal in the cursor's current heading from the current anchor."""
        placement = (
            PlacementOptions(relative_to=self._last, position=self._heading)
            if self._last is not None
            else None
        )
        ref = self.builder.add_terminal(
            tm_id, config=TerminalConfig(poles=poles), placement=placement
        )
        self._last = ref
        return self

    def at(self, ref: ComponentRef | PortRef, /, *, heading: Direction = "right") -> Cursor:
        """Jump the cursor to an existing named anchor (for parallel branches).

        This is the DSL's answer to schemdraw's ``.at(other_element.end)``.
        Note it requires the caller to already hold ``ref`` -- i.e. to have
        kept a Python variable around from an earlier chain call. An LLM
        generating a long script has to track this the same way it would
        have to track a raw coordinate: get it wrong and the branch silently
        attaches to the wrong pin.
        """
        self._last = ref
        self._heading = heading
        return self

    def last_ref(self) -> ComponentRef | PortRef | None:
        """Return the cursor's current anchor, e.g. to save it for later `.at()`."""
        return self._last

    def _place_symbol(
        self,
        factory: SymbolFactory,
        /,
        *,
        tag: str,
        heading: Direction,
        spacing: float | None,
        **factory_kwargs: object,
    ) -> Cursor:
        placement = (
            PlacementOptions(relative_to=self._last, position=heading, spacing=spacing)
            if self._last is not None
            else None
        )
        ref = self.builder.add_symbol(
            factory,
            config=SymbolConfig(
                tag_prefix=tag, factory_kwargs=factory_kwargs or None
            ),
            placement=placement,
        )
        self._last = ref
        self._heading = heading
        return self


def start_cursor(builder: CircuitBuilder, /, *, origin: Point | None = None) -> Cursor:
    """Create a Cursor over `builder`, optionally setting its layout origin.

    `origin` is the one absolute Point a chain still needs -- exactly like
    schemdraw's `d = schemdraw.Drawing()` implicit (0, 0) start, or
    CircuitBuilder's own `set_layout(x=..., y=...)` today.
    """
    if origin is not None:
        builder.set_layout(origin)
    return Cursor(builder=builder)
