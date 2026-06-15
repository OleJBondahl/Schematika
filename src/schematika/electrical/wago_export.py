"""WAGO PFC IOServer ``<Modules>`` XML export.

Renders the ``<Modules>`` block of a CDP Studio ``WagoPFCIOServer.xml`` from
a PLC rack definition plus the resolved per-channel-pin report rows. Pure —
returns a string, no file I/O. ``Project.export_wago_modules_xml`` is the
imperative-shell wrapper that writes it to disk during ``build()``.

Format reference: spec §2 of
``auxillary_cabinet_v3/docs/superpowers/specs/2026-06-09-wago-xml-export-design.md``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from xml.sax.saxutils import escape

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from schematika.electrical.field_devices import AnalogScaling, FieldDevice
    from schematika.electrical.plc_resolver import PlcRack

_OUTPUT_SIGNAL_TYPES = frozenset({"DO", "RELAY"})
_ANALOG_SIGNAL_TYPES = frozenset({"AI", "4-20mA", "RTD"})
_NAME_ABBREV = {"4-20mA": "AI", "RELAY": "RO"}
_CHANNEL_DESCRIPTION = {
    "analog": "Analog input channel",
    "output": "Digital output channel",
    "input": "Digital input channel",
}


def _attr(value: str) -> str:
    """Escape a string for use inside a double-quoted XML attribute."""
    return escape(value, {'"': "&quot;"})


def _num(value: float) -> str:
    """Format a scaling number without a trailing ``.0`` (``3.6`` stays ``3.6``)."""
    return f"{value:g}"


def _scaling_block(scaling: AnalogScaling) -> list[str]:
    """Operator + two ScalingPoint XML lines for one analog channel."""
    return [
        (
            '      <Operator Interpolation="Linear" '
            'Model="Automation.ScalingOperator&lt;double&gt;" '
            'Name="Scale" Type="double">'
        ),
        (
            f'        <ScalingPoint InValue="{_num(scaling.raw_min)}" '
            f'OutValue="{_num(scaling.eng_min)}" '
            'Model="Automation.ScalingPoint&lt;double&gt;" '
            'Name="ScalingPoint" Type="double"></ScalingPoint>'
        ),
        (
            f'        <ScalingPoint InValue="{_num(scaling.raw_max)}" '
            f'OutValue="{_num(scaling.eng_max)}" '
            'Model="Automation.ScalingPoint&lt;double&gt;" '
            'Name="ScalingPoint1" Type="double"></ScalingPoint>'
        ),
        "      </Operator>",
    ]


def render_wago_modules_xml(
    rack: PlcRack,
    *,
    rows: Sequence[tuple[str, str, str, str, str, str]],
    devices: Sequence[FieldDevice] = (),
    descriptions: Mapping[str, str] | None = None,
) -> str:
    """Render the WAGO PFC IOServer ``<Modules>`` XML block.

    Iterates the rack in order, emitting one ``<Module>`` per card and one
    ``<Channel>`` per physical channel — wired or spare — so the block always
    mirrors the full rack. Wired channels are named
    ``{device-tag}_{function_suffix}`` with hyphens replaced by underscores for
    CDP Studio compatibility (e.g. tag ``PU-01-CX`` + suffix ``StartFb`` →
    ``PU_01_CX_StartFb``; falls back to ``{component}_{pin}`` when no suffix is
    authored); spare channels get a structural placeholder
    ``{designation}_{nr}``. Analog channels on devices
    carrying an :class:`~schematika.electrical.field_devices.AnalogScaling`
    additionally emit a ``Unit`` attribute and a two-point
    ``<Operator>``/``<ScalingPoint>`` scaling block.

    Args:
        rack: Ordered ``(designation, PlcModuleType)`` pairs defining the rack.
        rows: Resolved per-channel-pin report rows ``(designation, mpn,
            pin_label, component_tag, component_pin, terminal_str)`` as
            produced by :func:`generate_plc_report_rows`. Spare rows (empty
            component) may be present or absent; the rack drives iteration.
        devices: Field devices supplying ``function_suffix`` (template pins)
            and ``scaling`` (instances).
        descriptions: Part number → catalog text for the ``Module
            Description`` attribute. Missing part numbers emit ``""``.

    Returns:
        str: The ``<Modules>…</Modules>`` XML fragment, newline-terminated.

    Examples:
        >>> from schematika.electrical import PlcModuleType
        >>> mod = PlcModuleType("750-1405", "DI", 8, ("",))
        >>> xml = render_wago_modules_xml([("DI1", mod)], rows=[])
        >>> xml.startswith("<Modules>")
        True
        >>> xml.count("<Channel")
        8
    """
    descriptions = descriptions or {}

    suffixes: dict[tuple[str, str], str] = {}
    scalings: dict[str, AnalogScaling] = {}
    for dev in devices:
        if dev.scaling is not None:
            scalings[dev.tag] = dev.scaling
        for pin in dev.template.pins:
            if pin.function_suffix:
                suffixes[(dev.tag, pin.device_pin)] = pin.function_suffix

    by_pin = {(r[0], r[2]): r for r in rows}

    lines = ["<Modules>"]
    mpn_counts: dict[str, int] = {}
    for designation, mt in rack:
        idx = mpn_counts.get(mt.mpn, 0)
        mpn_counts[mt.mpn] = idx + 1
        abbrev = _NAME_ABBREV.get(mt.signal_type, mt.signal_type)
        module_name = f"{mt.mpn}_{mt.channels}{abbrev}_{chr(ord('a') + idx)}"
        description = descriptions.get(mt.mpn, "")
        lines.append(
            f'  <Module Model="WagoIOModules.IOModule" '
            f'Name="{_attr(module_name)}" Description="{_attr(description)}">'
        )

        is_output = mt.signal_type in _OUTPUT_SIGNAL_TYPES
        is_analog = mt.signal_type in _ANALOG_SIGNAL_TYPES
        value_type = "short" if is_analog else "bool"
        input_attr = "1" if is_output else "0"
        ch_kind = "analog" if is_analog else ("output" if is_output else "input")
        channel_description = _CHANNEL_DESCRIPTION[ch_kind]

        for ch in range(1, mt.channels + 1):
            nr = ch - 1
            component, comp_pin = "", ""
            for pin_suffix in mt.pins_per_channel:
                label = mt.label_format.format(suffix=pin_suffix, channel=ch)
                row = by_pin.get((designation, label))
                if row is not None and row[3]:
                    component, comp_pin = row[3], row[4]
                    break
            if component:
                raw = f"{component}-{suffixes.get((component, comp_pin), comp_pin)}"
                name = raw.replace("-", "_")
            else:
                name = f"{designation}_{nr}"

            attrs = (
                f'Input="{input_attr}" '
                f'Model="CDPSignalChannel&lt;{value_type}&gt;" '
                f'Name="{_attr(name)}" NetworkConvert="1" Nr="{nr}" '
                f'Type="{value_type}" Value="0" '
                f'Description="{channel_description}"'
            )
            scaling = scalings.get(component) if component and is_analog else None
            if scaling is None:
                lines.append(f"    <Channel {attrs}></Channel>")
            else:
                lines.append(f'    <Channel {attrs} Unit="{_attr(scaling.unit)}">')
                lines.extend(_scaling_block(scaling))
                lines.append("    </Channel>")
        lines.append("  </Module>")
    lines.append("</Modules>")
    return "\n".join(lines) + "\n"
