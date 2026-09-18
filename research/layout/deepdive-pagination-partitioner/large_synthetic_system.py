"""A much larger synthetic cabinet system for the round-2 deep dive.

Round 1 used 12 rungs / ~40 components, one voltage domain, three functional
loops. This one is deliberately bigger and messier, to stress-test both
fixes on more than a single hand-picked example:

- **Two independent power domains** ("Line A" 480V 3-phase, "Line B" 240V
  3-phase), each with its own main incomer and its own 24VDC control-supply
  bus. Two domains means two separate instances of every open problem this
  track investigates, not one.
- **10 independent functional control loops** (5 per domain), each a
  motor-power rung + start/stop rung + contactor-coil rung -- 30 rungs.
- **6 field terminal strips.**
- **2 genuinely ambiguous rungs** (one per domain): `estop_master_enable_a`/
  `_b`, structurally IDENTICAL to a loop's `contactor_coil` rung (same
  component shape: an aux contact tag-echoed in, a coil tag-echoed out, one
  terminal) but semantically "gate the main incomer," not "drive this loop's
  motor." See `docs/research/layout-improvement/deepdive-pagination-partitioner.md`
  for why this structural identity is the whole point.
- **A control bus reused by 3+ pages**: each domain's 24VDC bus terminal
  (`X4` / `X103`) is the *first* component of 6 different control rungs
  (5 loop start/stop rungs + 1 e-stop chain) per domain -- with
  `MAX_RUNGS_PER_PAGE = 5` these rungs land on 2-3 different pages per
  domain, so each bus terminal genuinely crosses 3+ pages.
- **One legitimate bare severed-signal net** (`WATCHDOG`): a standalone
  watchdog relay with no terminal of its own, consumed by exactly one other
  rung -- proving `ref()` still has a real, single-pair job once
  terminal-anchored crossings are excluded from ever needing an arrow.

Total: 4 (power) + 30 (loops) + 4 (e-stop pairs) + 6 (terminal strips) +
2 (watchdog) = 46 rungs.
"""

from __future__ import annotations

from netlist import ComponentSpec, RungSpec, SystemNetlist, TagLink

from schematika.electrical.symbols import (
    breaker,
    coil,
    contactor,
    estop_button,
    fuse,
    motor,
    nc_contact,
    no_contact,
    psu,
    thermal_overload,
)

_C = ComponentSpec


def _term(tid: str, poles: int = 1) -> _C:
    return _C(kind="terminal", id_or_prefix=tid, poles=poles)


def _sym(prefix: str, fn, poles: int = 1) -> _C:
    return _C(kind="symbol", id_or_prefix=prefix, symbol_fn=fn, poles=poles)


def _stub(tag: str) -> _C:
    return _C(kind="stub", id_or_prefix=tag, poles=1)


def _power_domain(name: str, incomer_x: int, bus_x: int) -> tuple[RungSpec, RungSpec]:
    """One main incomer + one 24VDC control-supply bus rung for a domain."""
    main = RungSpec(
        key=f"main_incomer_{name}",
        role="power",
        function=f"main_incomer_{name}",
        title=f"Main Incomer -- Line {name.upper()}",
        components=(
            _term(f"X{incomer_x}", 3),
            _sym("F", breaker, 3),
            _sym("Q", contactor, 3),
            _term(f"X{incomer_x + 1}", 3),
        ),
    )
    supply = RungSpec(
        key=f"control_psu_{name}",
        role="power",
        function=f"control_supply_{name}",
        title=f"Control Supply 24V -- Line {name.upper()}",
        components=(
            _term(f"X{bus_x - 1}", 1),
            _sym("F", fuse, 1),
            _sym("U", psu, 1),
            _term(f"X{bus_x}", 1),
        ),
    )
    return main, supply


def _loop(
    n: int, domain: str, bus_tag: str, motor_x: int, field_x: int
) -> tuple[RungSpec, RungSpec, RungSpec]:
    """One functional loop: motor power + start/stop + contactor coil."""
    fn = f"loop_{n}"
    power = RungSpec(
        key=f"{fn}_power",
        role="power",
        function=fn,
        title=f"Loop {n} Motor Power",
        components=(
            _term(f"X{motor_x}", 3),
            _sym("F", fuse, 3),
            _sym("Q", contactor, 3),
            _sym("FT", thermal_overload, 3),
            _sym("M", motor, 3),
            _term(f"X{motor_x + 1}", 3),
        ),
    )
    start_stop = RungSpec(
        key=f"{fn}_start_stop",
        role="control",
        function=fn,
        title=f"Loop {n} Start/Stop",
        components=(
            _term(bus_tag, 1),  # 24V bus feed -- physical terminal, repeated
            _sym("SB", no_contact, 1),
            _sym("SB", nc_contact, 1),
            _sym("K", coil, 1),
            _term(f"X{field_x}", 1),
        ),
    )
    contactor_coil = RungSpec(
        key=f"{fn}_contactor_coil",
        role="control",
        function=fn,
        title=f"Loop {n} Contactor Coil",
        components=(
            _sym("K", no_contact, 1),  # reuses this loop's K aux contact
            _sym("Q", coil, 1),  # reuses this loop's Q tag from motor power
            _term(f"X{field_x + 1}", 1),
        ),
    )
    del domain  # kept for signature readability at call sites
    return power, start_stop, contactor_coil


def _estop_pair(
    domain: str, bus_tag: str, incomer_function: str, field_x: int
) -> tuple[RungSpec, RungSpec, tuple[TagLink, TagLink]]:
    """The ambiguous rung pair for one domain.

    `estop_master_enable_<domain>` is structurally identical to a loop's
    `contactor_coil` rung (aux-contact-in, coil-out, one terminal) -- see
    module docstring. It is left with `pin_to_function=None` here; callers
    that want the round-2 fix apply it via `apply_role_overrides`.
    """
    chain = RungSpec(
        key=f"estop_chain_{domain}",
        role="control",
        function=f"estop_{domain}",
        title=f"E-Stop Safety Chain -- Line {domain.upper()}",
        components=(
            _term(bus_tag, 1),
            _sym("S", estop_button, 1),
            _sym("S", nc_contact, 1),
            _sym("K", coil, 1),
            _term(f"X{field_x}", 1),
        ),
    )
    master_enable = RungSpec(
        key=f"estop_master_enable_{domain}",
        role="control",
        function=f"estop_{domain}",
        title=f"Main Contactor Enable -- Line {domain.upper()}",
        components=(
            _sym("K", no_contact, 1),  # reuses this domain's e-stop K aux contact
            _sym("Q", coil, 1),  # reuses this domain's main incomer Q tag
            _term(f"X{field_x + 1}", 1),
        ),
    )
    links = (
        TagLink(tag="K", owner_rung=chain.key, user_rung=master_enable.key),
        TagLink(tag="Q", owner_rung=f"main_incomer_{domain}", user_rung=master_enable.key),
    )
    del incomer_function
    return chain, master_enable, links


def _terminal_strip(name: str, tid: str, poles: int) -> RungSpec:
    return RungSpec(
        key=f"term_{name}",
        role="terminal",
        function=f"terminal_{name}",
        title=f"Terminal Strip {tid} ({name})",
        components=(_term(tid, poles),),
    )


def _watchdog_pair() -> tuple[RungSpec, RungSpec, TagLink]:
    """The one legitimate bare severed-signal net: no terminal, single pair."""
    relay = RungSpec(
        key="watchdog_relay",
        role="control",
        function="watchdog",
        title="PLC Watchdog Relay",
        components=(
            _term("X900", 1),
            _sym("Y", no_contact, 1),
            _sym("K", coil, 1),
            _stub("WATCHDOG"),
        ),
    )
    consumer = RungSpec(
        key="watchdog_consumer",
        role="control",
        function="watchdog_consumer",
        title="Watchdog-Gated Permissive",
        components=(
            _stub("WATCHDOG"),
            _sym("K", no_contact, 1),
            _term("X901", 1),
        ),
    )
    link = TagLink(tag="WATCHDOG", owner_rung=relay.key, user_rung=consumer.key)
    return relay, consumer, link


def build_large_system(*, apply_role_overrides: bool = False) -> SystemNetlist:
    """Return the round-2 synthetic system.

    Args:
        apply_role_overrides: When `True`, pins `estop_master_enable_a`/`_b`
            to their domain's main-incomer function group via
            `RungSpec.pin_to_function` -- the round-2 fix for the ambiguous
            "rung is control-role but power-role in intent" case. When
            `False`, reproduces round 1's unpatched behaviour (the rung
            stays with its own `estop_<domain>` function group) so the two
            partitions can be diffed.
    """
    rungs: list[RungSpec] = []
    tag_links: list[TagLink] = []

    main_a, supply_a = _power_domain("a", incomer_x=1, bus_x=4)
    main_b, supply_b = _power_domain("b", incomer_x=100, bus_x=103)
    rungs += [main_a, supply_a, main_b, supply_b]

    watchdog_relay, watchdog_consumer, watchdog_link = _watchdog_pair()
    # Declared here (right after the power domains, well before any loop's
    # control rungs) so its function group is the *first* control-bucket
    # group `_pack_groups` sees -- landing it on an early control page,
    # deliberately far from `watchdog_consumer` (declared at the very end,
    # after every loop and e-stop rung). This is what actually forces the
    # two sides of `WATCHDOG` onto different pages, so this system exercises
    # a genuine cross-page severed-signal arrow pair, not just a same-page
    # one (see `partitioner.py`'s same-page `continue` for why a same-page
    # stub pair renders with no arrow at all).
    rungs.append(watchdog_relay)
    tag_links.append(watchdog_link)

    field_x = 200
    motor_x = 300
    # Each domain's 24VDC bus terminal is declared as the owner of an
    # explicit TagLink to every rung that repeats it -- see module docstring
    # and `classify_link`: because both sides are `kind="terminal"`, every
    # one of these classifies as `terminal_crossing`, never an arrow, no
    # matter how many pages the 6 user rungs land on. Round 1 modeled this
    # same bus but only declared a TagLink for *one* of the three reuses
    # (treating it, inconsistently, as a severed wire) -- this is the round-2
    # fix actually exercised on a bus with 3+ distinct page destinations,
    # not just asserted to work.
    bus_supply_rung = {"a": "control_psu_a", "b": "control_psu_b"}
    bus_users: dict[str, list[str]] = {"a": [], "b": []}
    for domain, bus_tag in (("a", "X4"), ("b", "X103")):
        loop_numbers = range(1, 6) if domain == "a" else range(6, 11)
        for n in loop_numbers:
            power, start_stop, contactor_coil = _loop(
                n, domain, bus_tag, motor_x=motor_x, field_x=field_x
            )
            rungs += [power, start_stop, contactor_coil]
            tag_links += [
                TagLink(tag="Q", owner_rung=power.key, user_rung=contactor_coil.key),
                TagLink(
                    tag="K", owner_rung=start_stop.key, user_rung=contactor_coil.key
                ),
            ]
            bus_users[domain].append(start_stop.key)
            motor_x += 2
            field_x += 2

    for domain, bus_tag in (("a", "X4"), ("b", "X103")):
        chain, master_enable, links = _estop_pair(
            domain, bus_tag, f"main_incomer_{domain}", field_x=field_x
        )
        if apply_role_overrides:
            master_enable = RungSpec(
                key=master_enable.key,
                role=master_enable.role,
                function=master_enable.function,
                title=master_enable.title,
                components=master_enable.components,
                pin_to_function=f"main_incomer_{domain}",
            )
        rungs += [chain, master_enable]
        tag_links += list(links)
        bus_users[domain].append(chain.key)
        field_x += 2

    for domain, bus_tag in (("a", "X4"), ("b", "X103")):
        owner = bus_supply_rung[domain]
        for user in bus_users[domain]:
            tag_links.append(TagLink(tag=bus_tag, owner_rung=owner, user_rung=user))

    strips = [
        ("X20_field_io_a", "X20", 4),
        ("X21_field_io_a", "X21", 4),
        ("X22_field_io_a", "X22", 4),
        ("X23_field_io_b", "X23", 4),
        ("X24_field_io_b", "X24", 4),
        ("X25_field_io_b", "X25", 4),
    ]
    rungs += [_terminal_strip(name, tid, poles) for name, tid, poles in strips]

    rungs.append(watchdog_consumer)

    return SystemNetlist(rungs=tuple(rungs), tag_links=tuple(tag_links))
