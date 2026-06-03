import pytest

from schematika.catalog import (
    Catalog,
    CatalogDevice,
    DeviceCatalog,
    InstrumentSpec,
    ProcessSpec,
)
from schematika.catalog.cables import CableInstance, CableInstanceRegistry
from schematika.catalog.errors import CatalogError


def _device(tag: str) -> CatalogDevice:
    proc = ProcessSpec(instrument=InstrumentSpec(letters="TT", number="101"))
    return CatalogDevice(tag=tag, description="Temp transmitter", process=proc)


def test_add_and_get_device():
    cat = Catalog()
    cat.add_device(_device("TT-101"))
    assert cat.get_device("TT-101").description == "Temp transmitter"


def test_add_duplicate_device_raises():
    cat = Catalog()
    cat.add_device(_device("TT-101"))
    with pytest.raises(CatalogError):
        cat.add_device(_device("TT-101"))


def test_get_missing_device_raises():
    cat = Catalog()
    with pytest.raises(KeyError):
        cat.get_device("NOPE")


def test_instruments_filter():
    cat = Catalog()
    cat.add_device(_device("TT-101"))
    assert [d.tag for d in cat.instruments()] == ["TT-101"]


def test_add_and_get_cable_instance():
    cat = Catalog()
    cable = CableInstance(
        tag="W0001",
        spec="4x2.5",
        cable_type="power_ac",
        from_device="M1",
        to_device="X1",
    )
    cat.add_cable_instance(cable)
    assert cat.get_cable_instance("W0001").label == "4x2.5 (W0001)"
    assert [c.tag for c in cat.by_device("M1")] == ["W0001"]


def test_add_duplicate_cable_instance_raises():
    cat = Catalog()
    cable = CableInstance(
        tag="W0001",
        spec="4x2.5",
        cable_type="power_ac",
        from_device="M1",
        to_device="X1",
    )
    cat.add_cable_instance(cable)
    with pytest.raises(CatalogError):
        cat.add_cable_instance(cable)


def test_get_missing_cable_instance_raises():
    cat = Catalog()
    with pytest.raises(KeyError):
        cat.get_cable_instance("NOPE")


def test_device_and_cable_namespaces_are_independent():
    shared_tag = "SHARED-01"
    device = _device(shared_tag)
    cable = CableInstance(
        tag=shared_tag,
        spec="4x2.5",
        cable_type="power_ac",
        from_device="M1",
        to_device="X1",
    )

    cat = Catalog()
    cat.add_device(device)
    cat.add_cable_instance(cable)
    assert cat.get_device(shared_tag) is device
    assert cat.get_cable_instance(shared_tag) is cable

    dev_cat = DeviceCatalog()
    dev_cat.add_device(_device("TT-200"))
    dev_cat.add_cable_instance(
        CableInstance(
            tag="W0001",
            spec="4x2.5",
            cable_type="power_ac",
            from_device="A",
            to_device="B",
        )
    )
    assert len(dev_cat) == 1

    cable_reg = CableInstanceRegistry()
    cable_reg.add_device(_device("TT-300"))
    cable_reg.add_cable_instance(
        CableInstance(
            tag="W0002",
            spec="4x2.5",
            cable_type="power_ac",
            from_device="A",
            to_device="B",
        )
    )
    assert len(cable_reg) == 1


def test_public_surface_exports():
    import schematika.catalog as cat

    expected = {
        "Catalog",
        "CableInstance",
        "CableInstanceRegistry",
        "CatalogDevice",
        "CatalogError",
        "DeviceCatalog",
        "InstrumentSpec",
        "ProcessSpec",
        # legacy aliases still re-exported
        "CableSpec",
        "CableRegistry",
    }
    assert set(cat.__all__) == expected
    for name in expected:
        assert hasattr(cat, name), name
