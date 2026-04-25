"""Module-level helpers extracted from builder.py."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable

    from schematika.electrical.builder_models import BuildResult
    from schematika.electrical.model.core import Port, Symbol, SymbolFactory


def merge_build_results(results: list[BuildResult]) -> BuildResult:
    """Merge a list of :class:`~schematika.electrical.BuildResult` objects into one.

    Circuits are merged in order; the final state comes from the last result.
    Dicts are merged with ``update`` (last writer wins for duplicate keys).

    Args:
        results: Non-empty list of build results to combine.

    Returns:
        New :class:`~schematika.electrical.BuildResult` with all circuits,
        terminals, connections, and device metadata combined.

    Examples:
        >>> from schematika.electrical import (
        ...     CircuitBuilder, create_initial_state, merge_build_results)
        >>> state = create_initial_state()
        >>> r1 = CircuitBuilder(state=state).build()
        >>> r2 = CircuitBuilder(state=r1.state).build()
        >>> merged = merge_build_results([r1, r2])
        >>> merged.used_terminals
        []
    """
    from schematika.electrical.builder_models import BuildResult
    from schematika.electrical.system.system import Circuit, merge_circuits
    from schematika.electrical.utils.utils import merge_terminals

    merged_circuit = Circuit()
    for r in results:
        merged_circuit = merge_circuits(merged_circuit, r.circuit)

    merged_used_terminals: list[Any] = []
    for r in results:
        merged_used_terminals = merge_terminals(merged_used_terminals, r.used_terminals)

    merged_wire_connections: list[tuple[str, str, str, str]] = []
    for r in results:
        merged_wire_connections.extend(r.wire_connections)

    merged_device_registry: dict[str, Any] = {}
    for r in results:
        merged_device_registry.update(r.device_registry)

    merged_bridge_groups = _merge_dict_of_lists(r.bridge_groups for r in results)
    merged_component_map = _merge_dict_of_lists(r.component_map for r in results)
    merged_terminal_pin_map = _merge_dict_of_lists(r.terminal_pin_map for r in results)

    merged_connection_log: list[str] = []
    for r in results:
        merged_connection_log.extend(r.connection_log)

    return BuildResult(
        state=results[-1].state,
        circuit=merged_circuit,
        used_terminals=merged_used_terminals,
        wire_connections=merged_wire_connections,
        device_registry=merged_device_registry,
        bridge_groups=merged_bridge_groups,
        component_map=merged_component_map,
        terminal_pin_map=merged_terminal_pin_map,
        connection_log=merged_connection_log,
    )


def _merge_dict_of_lists(dicts: Iterable[dict]) -> dict:
    """Merge an iterable of dict[str, list] by extending lists per key."""
    merged: dict = {}
    for d in dicts:
        for key, values in d.items():
            merged.setdefault(key, []).extend(values)
    return merged


def _infer_default_pins(
    func: SymbolFactory | None,
) -> list[str] | None:
    """Reads `pins` default from the factory signature; None if missing or empty."""
    if func is None:
        return None
    sig = inspect.signature(func)
    params = sig.parameters

    # Case 1: function has a 'pins' parameter with a non-empty default
    if "pins" in params:
        default = params["pins"].default
        if default is not inspect.Parameter.empty and default:
            return list(default)
        return None

    # Case 2: *_pins parameters (e.g. coil_pins, contact_pins)
    pin_params = [
        (_name, param) for _name, param in params.items() if _name.endswith("_pins")
    ]
    if not pin_params:
        return None
    flat: list[str] = []
    for _name, param in pin_params:
        default = param.default
        if default is None or default is inspect.Parameter.empty:
            continue
        if hasattr(default, "__iter__"):
            flat.extend(default)
    return flat if flat else None


def _distribute_pins(
    func: SymbolFactory | None,
    pins: list[str],
    existing_kwargs: dict[str, Any],
) -> dict[str, Any]:
    """Routes flat pins to `pins=` or distributes across `*_pins` (required first)."""
    if func is None:
        return {}
    sig = inspect.signature(func)
    params = sig.parameters

    # Case 1: Function accepts 'pins' directly
    if "pins" in params and "pins" not in existing_kwargs:
        return {"pins": tuple(pins)}

    # Case 2: Distribute across *_pins parameters
    pin_params = [
        (name, param)
        for name, param in params.items()
        if name.endswith("_pins") and name not in existing_kwargs
    ]
    if not pin_params:
        return {}

    result = {}
    remaining = list(pins)

    # Required params first (non-None default with known length)
    for name, param in pin_params:
        default = param.default
        if default not in (None, inspect.Parameter.empty) and hasattr(
            default, "__len__"
        ):
            take = min(len(default), len(remaining))
            if take > 0:
                result[name] = tuple(remaining[:take])
                remaining = remaining[take:]

    # Optional params (None default) get remaining
    for name, param in pin_params:
        if name not in result and param.default is None and remaining:
            result[name] = tuple(remaining)
            remaining = []

    return result


def _get_absolute_x_offset(
    realized_components: list[dict[str, Any]], comp_idx: int
) -> float:
    """Walk back through place_right chain to compute absolute x offset."""
    rc = realized_components[comp_idx]
    x_offset = rc["spec"].x_offset
    if rc["spec"].placed_right_of is not None:
        x_offset += _get_absolute_x_offset(
            realized_components, rc["spec"].placed_right_of
        )
    return x_offset


def _find_port(
    sym: Symbol, pin_name: str, spec_pins: tuple | list | None = None
) -> Port | None:
    """Direct key lookup; falls back to pin label -> port key via `spec_pins` index."""
    # Direct lookup — covers the common case
    port = sym.ports.get(pin_name)
    if port is not None:
        return port

    # Fallback: map pin label → port key via index
    if spec_pins:
        pins_list = list(spec_pins)
        if pin_name in pins_list:
            pin_idx = pins_list.index(pin_name)
            port_keys = list(sym.ports.keys())
            if pin_idx < len(port_keys):
                return sym.ports[port_keys[pin_idx]]

    return None


def _resolve_pin(
    component_data: dict[str, Any], pole_idx: int, *, is_input: bool
) -> str:
    """Terminals use port IDs `(pole*2)+1/2`; symbols use interleaved or direct pins."""
    spec = component_data["spec"]

    # CASE 1: Terminals
    # Terminals have fixed port IDs regardless of custom pin labels.
    # For a 3-pole terminal: ports "1", "2", "3", "4", "5", "6"
    # Each pole has 2 ports: input (odd) and output (even)
    # Pole 0: ports "1" (input), "2" (output)
    # Pole 1: ports "3" (input), "4" (output)
    # Pole 2: ports "5" (input), "6" (output)
    if spec.kind == "terminal":
        # Calculate port ID based on pole index and side
        port_num = (pole_idx * 2) + (1 if is_input else 2)
        return str(port_num)

    # CASE 2: Symbols
    # Use explicit pins if provided (Mapping label to Port ID)
    if component_data["pins"]:
        # Logic: If provided pins list is large enough to cover
        # distinct In/Out pins per pole
        # e.g. ["A1", "A2"] for 1 pole -> In=A1, Out=A2
        # e.g. ["1", "2", "3", "4"] for 2 pole -> In1=1, Out1=2, In2=3, Out2=4
        if len(component_data["pins"]) == spec.poles * 2:
            idx = (pole_idx * 2) + (0 if is_input else 1)
            if idx < len(component_data["pins"]):
                return component_data["pins"][idx]

        # For symbols with custom named ports
        # (e.g. PSU with ["L", "N", "PE", "24V", "GND"])
        # Or short pins list - use pole_idx directly
        if pole_idx < len(component_data["pins"]):
            return component_data["pins"][pole_idx]

    # Fallback/Heuristic for Symbols without explicit pins
    # Assumes standard 1/2, 3/4 pairing port naming
    base_idx = pole_idx * 2
    offset = 0 if is_input else 1
    return str(base_idx + offset + 1)


def _resolve_registry_pin(component_data: dict[str, Any], pole_idx: int) -> str:
    """For terminals: returns the assigned pin label, not the port ID."""
    spec = component_data["spec"]

    # CASE 1: Terminals — return the physical pin label
    if spec.kind == "terminal":
        if component_data["pins"] and pole_idx < len(component_data["pins"]):
            return component_data["pins"][pole_idx]
        # Fallback: 1-based index
        return str(pole_idx + 1)

    # CASE 2: Symbols — delegate to _resolve_pin for the correct port label
    return _resolve_pin(component_data, pole_idx, is_input=True)
