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
        # Phase-0
        "CableInstance",
        "CableInstanceRegistry",
        "CableRegistry",
        "CableSpec",
        "Catalog",
        "CatalogDevice",
        "CatalogError",
        "DeviceCatalog",
        "InstrumentSpec",
        "ProcessSpec",
        # Phase-1 errors
        "CatalogLookupError",
        "CatalogValidationError",
        # Phase-1 identifiers
        "CableId",
        "CircuitId",
        "ConnectorId",
        "DeviceTag",
        "NetId",
        "PartId",
        "TagPrefix",
        # Phase-1 refs / specs / data
        "PartRef",
        "PinRef",
        "PartCategory",
        "PartSpec",
        "ConnectorSpec",
        "ConnectorInstance",
        "CableProductSpec",
        "Wire",
        "BOMRow",
        # Phase-1 functions / resolver
        "normalize_net_name",
        "ResolvedCatalog",
        # Phase-2a route primitive
        "Route",
        "route_to_wires",
    }
    assert set(cat.__all__) == expected
    for name in expected:
        assert hasattr(cat, name), name


def test_add_part_returns_partref_and_build_resolves():
    from schematika.catalog.cables import CableProductSpec
    from schematika.catalog.connectors import ConnectorSpec
    from schematika.catalog.identifiers import PartId
    from schematika.catalog.parts import PartSpec
    from schematika.catalog.registry import Catalog

    cat = Catalog()
    ref = cat.add_part(
        PartSpec(part=PartId("p1"), mpn="1", category="device", description="d")
    )
    assert ref.part == "p1"
    assert ref.tag is None
    cat.add_connector(ConnectorSpec(part=PartId("c1"), pincount=2, pins=("1", "2")))
    cat.add_cable_product(CableProductSpec(part=PartId("cp1"), conductor_count=4))
    resolved = cat.build()
    assert resolved.lookup_part(PartId("p1")).mpn == "1"
    assert resolved.lookup_connector(PartId("c1")).pincount == 2
    assert resolved.lookup_cable_product(PartId("cp1")).conductor_count == 4


def test_add_part_duplicate_raises():
    from schematika.catalog.errors import CatalogValidationError
    from schematika.catalog.identifiers import PartId
    from schematika.catalog.parts import PartSpec
    from schematika.catalog.registry import Catalog

    cat = Catalog()
    spec = PartSpec(part=PartId("p1"), mpn="1", category="device", description="d")
    cat.add_part(spec)
    with pytest.raises(CatalogValidationError):
        cat.add_part(spec)


def test_build_is_immutable_snapshot():
    from schematika.catalog.errors import CatalogLookupError
    from schematika.catalog.identifiers import PartId
    from schematika.catalog.parts import PartSpec
    from schematika.catalog.registry import Catalog

    cat = Catalog()
    resolved = cat.build()
    cat.add_part(
        PartSpec(part=PartId("late"), mpn="9", category="device", description="d")
    )
    with pytest.raises(CatalogLookupError):
        resolved.lookup_part(PartId("late"))
