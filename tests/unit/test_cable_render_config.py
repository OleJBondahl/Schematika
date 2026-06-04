"""Tests for CableRenderConfig."""

from schematika.cable.render_config import CableRenderConfig
from schematika.catalog.identifiers import ConnectorId


def test_default_show_pincount_empty():
    assert CableRenderConfig().show_pincount == frozenset()


def test_show_pincount_membership():
    cfg = CableRenderConfig(show_pincount=frozenset({ConnectorId("J1")}))
    assert ConnectorId("J1") in cfg.show_pincount
    assert ConnectorId("J2") not in cfg.show_pincount
