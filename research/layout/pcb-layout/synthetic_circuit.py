"""A small duck-typed stand-in for a SKiDL Circuit.

`schematika.pcb.adapter.adapt()` only touches `.parts`, `.nets`, `.NC` and
their nested `.ref` / `.name` / `.pins` / `.num` / `.description` attributes
(SKiDL is duck-typed on purpose — see adapter.py's module docstring), so a
plain `SimpleNamespace` graph exercises the real `pcb.build()` path without
requiring the `skidl` package to be installed in this worktree.

Circuit modeled (a tiny harness fragment):

    J1 (4-pin connector)          J2 (2-pin connector)
      .1 --[+24V]                   .1 --(SIG_F1_OUT, from F1.2)
      .2 --[GND]                    .2 --(SHARED_SIG, 3-pin junction)
      .3 --(SIG_F1)-- F1.1
                       F1.2 --(SIG_F1_OUT)-- J2.1
      .4 --(K1_COIL_IN)-- K1.1
                       K1.2 --(SHARED_SIG)-- J2.2, TP1.1

This exercises all four net kinds the walk algorithm distinguishes
(POWER, CHAIN, LABEL, DROPPED-by-omission) and one cross-block chain
(J1 -> F1 -> J2), which is the case a generic "draw a line between every
two connected pins" layout would render as a page-spanning wire but this
algorithm instead renders as a text cross-reference label on each end.
"""

from types import SimpleNamespace
from typing import Any


def _part(ref: str, template: Any, n_pins: int, description: str | None = None) -> Any:
    return SimpleNamespace(
        ref=ref,
        name=template,
        description=description,
        pins=[SimpleNamespace(num=str(i + 1)) for i in range(n_pins)],
    )


def _net(name: str, pin_specs: list[tuple[Any, str]]) -> Any:
    return SimpleNamespace(
        name=name,
        pins=[SimpleNamespace(part=part, num=pin) for part, pin in pin_specs],
    )


def build_synthetic_circuit() -> Any:
    """Return a duck-typed circuit object shaped like a SKiDL ``Circuit``."""
    j1 = _part("J1", "conn_4p", 4, description="Power + signal in")
    j2 = _part("J2", "conn_2p", 2, description="Signal out")
    f1 = _part("F1", "fuse", 2)
    k1 = _part("K1", "relay_coil", 2)
    tp1 = _part("TP1", "test_point", 1)

    nets = [
        _net("+24V", [(j1, "1")]),
        _net("GND", [(j1, "2")]),
        _net("SIG_F1", [(j1, "3"), (f1, "1")]),
        _net("SIG_F1_OUT", [(f1, "2"), (j2, "1")]),
        _net("K1_COIL_IN", [(j1, "4"), (k1, "1")]),
        _net("SHARED_SIG", [(k1, "2"), (j2, "2"), (tp1, "1")]),
    ]

    nc = SimpleNamespace(pins=[])  # distinct sentinel object; identity-compared
    return SimpleNamespace(parts=[j1, j2, f1, k1, tp1], nets=nets, NC=nc)
