import pytest

from schematika.catalog import Catalog, CatalogDevice, InstrumentSpec, ProcessSpec
from schematika.catalog.cables import CableInstance
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
