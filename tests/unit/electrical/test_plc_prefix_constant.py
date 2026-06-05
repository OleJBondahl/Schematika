"""C3a: a single shared PLC_PREFIX constant, no duplication."""

from schematika.electrical.plc_resolver import PLC_PREFIX, _parse_plc_tag


def test_plc_prefix_value() -> None:
    assert PLC_PREFIX == "PLC:"


def test_parse_plc_tag_uses_prefix() -> None:
    assert _parse_plc_tag("PLC:RTD:+R") == ("RTD", "+R")
    assert _parse_plc_tag("PLC:DI") == ("DI", "")


def test_harness_and_report_share_constant() -> None:
    from schematika.electrical import harness, plc_report

    assert harness._PLC_PREFIX == PLC_PREFIX
    assert plc_report._PLC_PREFIX == PLC_PREFIX
