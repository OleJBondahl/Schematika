"""A synthetic cabinet system large enough that manual pagination would be
tedious: main power distribution, three independent control functions
(two conveyors + an e-stop safety chain), and two field terminal strips.

12 rungs, ~40 components. A human drafter would naturally reach for 3-4
sheets: one power sheet, one or two control sheets grouped by function, and
a terminal sheet -- exactly the split this spike asks the partitioner to
find automatically.
"""

from __future__ import annotations

from netlist import ComponentSpec, RungSpec, SystemNetlist, TagLink

from schematika.electrical.symbols import (
    breaker,
    coil,
    contactor,
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


def build_synthetic_system() -> SystemNetlist:
    """Return the synthetic system netlist described in the module docstring."""
    rungs = (
        # -- Power distribution -------------------------------------------------
        RungSpec(
            key="main_incomer",
            role="power",
            function="main_incomer",
            title="Main Incomer",
            components=(
                _term("X1", 3),
                _sym("F", breaker, 3),
                _sym("Q", contactor, 3),
                _term("X2", 3),
            ),
        ),
        RungSpec(
            key="control_psu",
            role="power",
            function="control_supply",
            title="Control Supply (24V)",
            components=(
                _term("X3", 1),
                _sym("F", fuse, 1),
                _sym("U", psu, 1),
                _term("X4", 1),
            ),
        ),
        RungSpec(
            key="motor_1_power",
            role="power",
            function="motor_1_power",
            title="Motor 1 Power",
            components=(
                _term("X5", 3),
                _sym("F", fuse, 3),
                _sym("Q", contactor, 3),
                _sym("FT", thermal_overload, 3),
                _sym("M", motor, 3),
                _term("X6", 3),
            ),
        ),
        RungSpec(
            key="motor_2_power",
            role="power",
            function="motor_2_power",
            title="Motor 2 Power",
            components=(
                _term("X7", 3),
                _sym("F", fuse, 3),
                _sym("Q", contactor, 3),
                _sym("FT", thermal_overload, 3),
                _sym("M", motor, 3),
                _term("X8", 3),
            ),
        ),
        # -- Control / logic, grouped by function --------------------------------
        RungSpec(
            key="conv1_start_stop",
            role="control",
            function="conveyor_1",
            title="Conveyor 1 Start/Stop",
            components=(
                _term("X4", 1),  # 24V bus feed, repeated terminal (no arrow needed)
                _sym("SB", no_contact, 1),
                _sym("SB", nc_contact, 1),
                _sym("K", coil, 1),
                _term("X9", 1),
            ),
        ),
        RungSpec(
            key="conv1_contactor_coil",
            role="control",
            function="conveyor_1",
            title="Conveyor 1 Contactor Coil",
            components=(
                _sym("K", no_contact, 1),  # reuses K1 aux contact
                _sym("Q", coil, 1),  # reuses Q2 tag from motor_1_power
                _term("X10", 1),
            ),
        ),
        RungSpec(
            key="conv2_start_stop",
            role="control",
            function="conveyor_2",
            title="Conveyor 2 Start/Stop",
            components=(
                _term("X4", 1),  # 24V bus feed, repeated terminal (no arrow needed)
                _sym("SB", no_contact, 1),
                _sym("SB", nc_contact, 1),
                _sym("K", coil, 1),
                _term("X11", 1),
            ),
        ),
        RungSpec(
            key="conv2_contactor_coil",
            role="control",
            function="conveyor_2",
            title="Conveyor 2 Contactor Coil",
            components=(
                _sym("K", no_contact, 1),  # reuses K2 aux contact
                _sym("Q", coil, 1),  # reuses Q3 tag from motor_2_power
                _term("X12", 1),
            ),
        ),
        RungSpec(
            key="estop_chain",
            role="control",
            function="estop",
            title="E-Stop Safety Chain",
            components=(
                _term("X4", 1),  # 24V bus feed -- genuine severed wire, see below
                _sym("S", nc_contact, 1),
                _sym("S", nc_contact, 1),
                _sym("K", coil, 1),
                _term("X13", 1),
            ),
        ),
        RungSpec(
            key="estop_master_enable",
            role="control",
            function="estop",
            title="Main Contactor Enable",
            components=(
                _sym("K", no_contact, 1),  # reuses K0 aux contact (safety relay)
                _sym("Q", coil, 1),  # reuses Q1 tag from main_incomer
                _term("X14", 1),
            ),
        ),
        # -- Terminal strips ------------------------------------------------------
        RungSpec(
            key="term_X20",
            role="terminal",
            function="terminal_X20",
            title="Terminal Strip X20 (Conveyor 1 field I/O)",
            components=(_term("X20", 4),),
        ),
        RungSpec(
            key="term_X21",
            role="terminal",
            function="terminal_X21",
            title="Terminal Strip X21 (Conveyor 2 / E-Stop field I/O)",
            components=(_term("X21", 4),),
        ),
    )

    tag_links = (
        # Case A -- severed wire: the 24V bus is genuinely truncated at the
        # estop chain's rung boundary (no shared terminal reuse elsewhere on
        # that specific link). Crosses pages -> gets an off-page arrow pair.
        TagLink(
            tag="X4",
            owner_rung="control_psu",
            owner_boundary="end",
            user_rung="estop_chain",
            user_boundary="start",
        ),
        # Case B -- tag echoes (contactor coil <-> main contacts, relay aux
        # <-> its own coil). Both sides are fully self-terminated rungs;
        # Schematika's existing reuse_tags resolves these regardless of page.
        # No arrow, ever -- only a build-order constraint (owner before user).
        TagLink(tag="Q", owner_rung="main_incomer", user_rung="estop_master_enable"),
        TagLink(tag="Q", owner_rung="motor_1_power", user_rung="conv1_contactor_coil"),
        TagLink(tag="Q", owner_rung="motor_2_power", user_rung="conv2_contactor_coil"),
        TagLink(tag="K", owner_rung="conv1_start_stop", user_rung="conv1_contactor_coil"),
        TagLink(tag="K", owner_rung="conv2_start_stop", user_rung="conv2_contactor_coil"),
        TagLink(tag="K", owner_rung="estop_chain", user_rung="estop_master_enable"),
    )

    return SystemNetlist(rungs=rungs, tag_links=tag_links)
