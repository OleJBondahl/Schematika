"""Scratch debug: dump actual port-id keys the contactor symbol ends up
with when built through CircuitBuilder, vs. the pin names in
wire_connections, to explain a real mismatch found while building the ELK
converter. Not part of the deliverable prototype."""

from run_layout import build_dol_starter

result = build_dol_starter()
for elem in result.circuit.elements:
    if hasattr(elem, "label") and hasattr(elem, "ports"):
        print(elem.label, [(k, p.id) for k, p in elem.ports.items()])

print("--- wire_connections touching Q1 ---")
for c in result.wire_connections:
    if "Q1" in c:
        print(c)
