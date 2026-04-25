"""Centralised ``@pure`` marker for functions the fp_purity_gate checks.

This is intentionally a **no-op** decorator. Use it on functions that
the fp_purity_gate should recognise as pure-by-contract, but whose
bodies fall outside what ``deal.pure`` can verify at runtime — e.g.
functions that:

* emit ``warnings.warn`` (a benign observation, not a state write);
* accept a caller-supplied ``Callable`` whose side-effects are the
  caller's problem, not the function's;
* mutate a caller-passed mutable parameter on purpose (an explicit
  accumulator-style contract).

For Group A (genuinely pure) functions use ``@deal.pure`` directly and
get real runtime enforcement. The fp_purity_gate accepts both markers.
"""

from __future__ import annotations

from collections.abc import Callable


def pure[F: Callable](fn: F) -> F:
    """No-op marker — see module docstring."""
    return fn
