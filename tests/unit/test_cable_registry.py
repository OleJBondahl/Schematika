"""
Tests for CableInstance and CableInstanceRegistry.
"""

import pytest

from schematika.catalog.cables import CableInstance, CableInstanceRegistry

# ---------------------------------------------------------------------------
# CableInstance
# ---------------------------------------------------------------------------


def test_cable_spec_label_property():
    spec = CableInstance(
        tag="W0001",
        spec="4x2.5",
        cable_type="power_ac",
        from_device="PSU",
        to_device="PLC",
    )
    assert spec.label == "4x2.5 (W0001)"


def test_cable_spec_label_format():
    spec = CableInstance(
        tag="W0099",
        spec="CAT7",
        cable_type="ethernet",
        from_device="SW1",
        to_device="PLC",
    )
    assert spec.label == "CAT7 (W0099)"


def test_cable_spec_frozen():
    spec = CableInstance(
        tag="W0001",
        spec="4x2.5",
        cable_type="power_ac",
        from_device="A",
        to_device="B",
    )
    with pytest.raises(AttributeError):
        spec.tag = "W9999"  # ty: ignore[invalid-assignment]


def test_cable_spec_default_description():
    spec = CableInstance(
        tag="W0001",
        spec="2x1.5",
        cable_type="signal",
        from_device="A",
        to_device="B",
    )
    assert spec.description == ""


# ---------------------------------------------------------------------------
# CableInstanceRegistry — register and retrieve
# ---------------------------------------------------------------------------


def test_registry_register_and_get():
    reg = CableInstanceRegistry()
    spec = CableInstance(
        tag="W0001",
        spec="4x2.5",
        cable_type="power_ac",
        from_device="PSU",
        to_device="PLC",
    )
    reg.register(spec)
    assert reg.get("W0001") is spec


def test_registry_duplicate_raises():
    reg = CableInstanceRegistry()
    spec = CableInstance(
        tag="W0001",
        spec="4x2.5",
        cable_type="power_ac",
        from_device="A",
        to_device="B",
    )
    reg.register(spec)
    with pytest.raises(ValueError, match="already registered"):
        reg.register(spec)


def test_registry_get_nonexistent_raises():
    reg = CableInstanceRegistry()
    with pytest.raises(KeyError, match="not found"):
        reg.get("W9999")


# ---------------------------------------------------------------------------
# CableInstanceRegistry — by_device
# ---------------------------------------------------------------------------


def test_registry_by_device():
    reg = CableInstanceRegistry()
    c1 = CableInstance("W01", "4x2.5", "power_ac", "PSU", "PLC")
    c2 = CableInstance("W02", "2x1.5", "signal", "PLC", "HMI")
    c3 = CableInstance("W03", "CAT7", "ethernet", "SW1", "PLC")
    reg.register(c1)
    reg.register(c2)
    reg.register(c3)

    plc_cables = reg.by_device("PLC")
    tags = {c.tag for c in plc_cables}
    assert tags == {"W01", "W02", "W03"}


def test_registry_by_device_as_source_only():
    reg = CableInstanceRegistry()
    c1 = CableInstance("W01", "4x2.5", "power_ac", "PSU", "PLC")
    c2 = CableInstance("W02", "2x1.5", "signal", "PSU", "HMI")
    reg.register(c1)
    reg.register(c2)

    psu_cables = reg.by_device("PSU")
    assert len(psu_cables) == 2


def test_registry_by_device_no_match():
    reg = CableInstanceRegistry()
    c1 = CableInstance("W01", "4x2.5", "power_ac", "PSU", "PLC")
    reg.register(c1)

    assert reg.by_device("GHOST") == []


# ---------------------------------------------------------------------------
# CableInstanceRegistry — dunder methods
# ---------------------------------------------------------------------------


def test_registry_contains():
    reg = CableInstanceRegistry()
    spec = CableInstance("W01", "4x2.5", "power_ac", "A", "B")
    reg.register(spec)
    assert "W01" in reg
    assert "W99" not in reg


def test_registry_len():
    reg = CableInstanceRegistry()
    assert len(reg) == 0
    reg.register(CableInstance("W01", "4x2.5", "power_ac", "A", "B"))
    assert len(reg) == 1
    reg.register(CableInstance("W02", "2x1.5", "signal", "A", "C"))
    assert len(reg) == 2


def test_registry_iter():
    reg = CableInstanceRegistry()
    c1 = CableInstance("W01", "4x2.5", "power_ac", "A", "B")
    c2 = CableInstance("W02", "2x1.5", "signal", "C", "D")
    reg.register(c1)
    reg.register(c2)

    items = list(reg)
    assert len(items) == 2
    assert c1 in items
    assert c2 in items


# ---------------------------------------------------------------------------
# CableInstanceRegistry — cables property
# ---------------------------------------------------------------------------


def test_registry_cables_property():
    reg = CableInstanceRegistry()
    c1 = CableInstance("W01", "4x2.5", "power_ac", "A", "B")
    c2 = CableInstance("W02", "2x1.5", "signal", "C", "D")
    reg.register(c1)
    reg.register(c2)

    cables = reg.cables
    assert isinstance(cables, list)
    assert len(cables) == 2
    assert c1 in cables
    assert c2 in cables


def test_registry_cables_returns_copy():
    reg = CableInstanceRegistry()
    c1 = CableInstance("W01", "4x2.5", "power_ac", "A", "B")
    reg.register(c1)

    cables1 = reg.cables
    cables2 = reg.cables
    assert cables1 is not cables2


def test_registry_empty_cables():
    reg = CableInstanceRegistry()
    assert reg.cables == []


def test_legacy_aliases_resolve():
    from schematika.catalog.cables import CableRegistry, CableSpec

    assert CableRegistry is CableInstanceRegistry
    assert CableSpec is CableInstance


def test_cable_instance_registry_is_catalog_subclass():
    from schematika.catalog import Catalog

    assert issubclass(CableInstanceRegistry, Catalog)
