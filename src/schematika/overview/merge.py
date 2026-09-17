"""Combine multiple OverviewInput snapshots into one.

A consumer whose build is split across independent Projects (e.g. a PCB Project
and a harness Project, built by two separate generator invocations) has no
single Project to call ``overview_input()`` on. ``merge_inputs`` lets each
Project (or hand-built OverviewInput) contribute its own snapshot, unioned here
before rendering.
"""

from __future__ import annotations

from schematika.overview.inputs import OverviewInput

_DEFAULT_TITLE = "System Overview"


def merge_inputs(*inputs: OverviewInput) -> OverviewInput:
    """Union N OverviewInput snapshots into one.

    Wires are de-duplicated by unordered pin-id pair (first occurrence wins,
    matching Project.overview_input()'s own dedup rule). pcb_nets/fuse_links/
    relay_contacts are concatenated as-is (each entry already carries a unique
    board-qualified id, so cross-input duplicates are not expected). relay_pins
    dicts are merged key-by-key; a later input's entry for the same relay id
    overwrites an earlier one. title is the first non-default title found,
    else the default.

    Returns:
        One merged OverviewInput carrying the union of every input's wires,
        tags, pcb_nets, fuse_links, relay_contacts, and relay_pins.

    Examples:
        >>> from schematika.overview.inputs import OverviewInput, OverviewWire
        >>> a = OverviewInput(wires=(OverviewWire(a="A..1", b="B..1", label=None),),
        ...                   field_device_tags=frozenset(), terminal_tags=frozenset())
        >>> b = OverviewInput(wires=(), field_device_tags=frozenset(),
        ...                   terminal_tags=frozenset(), title="Juicebox")
        >>> merge_inputs(a, b).title
        'Juicebox'
    """
    seen: set[frozenset[str]] = set()
    wires: list = []
    field_device_tags: set[str] = set()
    terminal_tags: set[str] = set()
    pcb_nets: list = []
    fuse_links: list = []
    relay_contacts: list = []
    relay_pins: dict = {}
    title = _DEFAULT_TITLE

    for inp in inputs:
        for w in inp.wires:
            key = frozenset((w.a, w.b))
            if key not in seen:
                seen.add(key)
                wires.append(w)
        field_device_tags |= inp.field_device_tags
        terminal_tags |= inp.terminal_tags
        pcb_nets.extend(inp.pcb_nets)
        fuse_links.extend(inp.fuse_links)
        relay_contacts.extend(inp.relay_contacts)
        relay_pins.update(inp.relay_pins)
        if title == _DEFAULT_TITLE and inp.title != _DEFAULT_TITLE:
            title = inp.title

    return OverviewInput(
        wires=tuple(wires),
        field_device_tags=frozenset(field_device_tags),
        terminal_tags=frozenset(terminal_tags),
        title=title,
        pcb_nets=tuple(pcb_nets),
        fuse_links=tuple(fuse_links),
        relay_contacts=tuple(relay_contacts),
        relay_pins=relay_pins,
    )
