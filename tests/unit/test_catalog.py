import pytest

from schematika.catalog import (
    CatalogDevice,
    DeviceCatalog,
    InstrumentSpec,
    ProcessSpec,
)
from schematika.catalog.device import ElectricalSpec


def test_register_and_get():
    catalog = DeviceCatalog()
    device = CatalogDevice(tag="TT-101", description="CW temp transmitter")
    catalog.register(device)
    assert catalog.get("TT-101") is device


def test_duplicate_raises():
    catalog = DeviceCatalog()
    device = CatalogDevice(tag="TT-101", description="test")
    catalog.register(device)
    with pytest.raises(ValueError, match="already registered"):
        catalog.register(device)


def test_get_missing_raises():
    catalog = DeviceCatalog()
    with pytest.raises(KeyError):
        catalog.get("NONEXISTENT")


def test_contains():
    catalog = DeviceCatalog()
    catalog.register(CatalogDevice(tag="TT-101", description="test"))
    assert "TT-101" in catalog
    assert "XX-999" not in catalog


def test_len():
    catalog = DeviceCatalog()
    assert len(catalog) == 0
    catalog.register(CatalogDevice(tag="TT-101", description="test"))
    assert len(catalog) == 1


def test_instruments_filter():
    catalog = DeviceCatalog()
    catalog.register(
        CatalogDevice(
            tag="TT-101",
            description="temp",
            process=ProcessSpec(instrument=InstrumentSpec("TT", "101")),
        )
    )
    catalog.register(CatalogDevice(tag="CB-001", description="breaker"))
    assert len(catalog.instruments()) == 1


def test_electrical_filter():
    catalog = DeviceCatalog()
    catalog.register(
        CatalogDevice(
            tag="TT-101",
            description="temp",
            electrical=ElectricalSpec(terminal="X100"),
        )
    )
    catalog.register(CatalogDevice(tag="T-001", description="tank"))
    assert len(catalog.electrical_devices()) == 1


def test_cross_referenced():
    catalog = DeviceCatalog()
    catalog.register(
        CatalogDevice(
            tag="TT-101",
            description="temp",
            process=ProcessSpec(instrument=InstrumentSpec("TT", "101")),
            electrical=ElectricalSpec(terminal="X100"),
        )
    )
    catalog.register(
        CatalogDevice(
            tag="T-001",
            description="tank",
            process=ProcessSpec(instrument=InstrumentSpec("TE", "001")),
        )
    )
    xref = catalog.cross_referenced()
    assert len(xref) == 1
    assert xref[0].tag == "TT-101"


def test_cross_reference_table():
    catalog = DeviceCatalog()
    catalog.register(
        CatalogDevice(
            tag="TT-101",
            description="CW temp",
            process=ProcessSpec(
                instrument=InstrumentSpec("TT", "101", "field"),
                service="Cooling water supply",
            ),
            electrical=ElectricalSpec(terminal="X100", signal_type="4-20mA"),
        )
    )
    table = catalog.generate_cross_reference_table()
    assert len(table) == 1
    assert table[0]["tag"] == "TT-101"
    assert table[0]["electrical_terminal"] == "X100"
    assert table[0]["service"] == "Cooling water supply"


def test_instrument_spec_tag():
    spec = InstrumentSpec("TT", "101")
    assert spec.tag == "TT-101"
    assert spec.first_letter == "T"


def test_devices_property():
    catalog = DeviceCatalog()
    d1 = CatalogDevice(tag="TT-101", description="a")
    d2 = CatalogDevice(tag="PT-201", description="b")
    catalog.register(d1)
    catalog.register(d2)
    assert {d.tag for d in catalog.devices} == {"TT-101", "PT-201"}


def test_iter():
    catalog = DeviceCatalog()
    catalog.register(CatalogDevice(tag="TT-101", description="a"))
    catalog.register(CatalogDevice(tag="PT-201", description="b"))
    tags = [d.tag for d in catalog]
    assert set(tags) == {"TT-101", "PT-201"}


# ---------------------------------------------------------------------------
# Integration: PIDBuilder with catalog
# ---------------------------------------------------------------------------


def test_pid_builder_with_catalog():
    from schematika.pid.builder import PIDBuilder
    from schematika.pid.symbols import centrifugal_pump

    catalog = DeviceCatalog()
    catalog.register(
        CatalogDevice(
            tag="TT-101",
            description="CW temp",
            process=ProcessSpec(instrument=InstrumentSpec("TT", "101", "field")),
        )
    )

    builder = PIDBuilder()
    builder.add_equipment("pump", centrifugal_pump, "P", x=50, y=50)
    builder.add_instrument_from_catalog(
        "tt101",
        catalog,
        "TT-101",
        on_equipment="pump",
        on_port="outlet",
    )
    result = builder.build()
    assert "tt101" in result.instrument_map


def test_pid_builder_catalog_no_process_spec_raises():
    from schematika.pid.builder import PIDBuilder
    from schematika.pid.symbols import centrifugal_pump

    catalog = DeviceCatalog()
    catalog.register(CatalogDevice(tag="CB-001", description="breaker"))

    builder = PIDBuilder()
    builder.add_equipment("pump", centrifugal_pump, "P", x=50, y=50)
    with pytest.raises(ValueError, match="no ProcessSpec"):
        builder.add_instrument_from_catalog(
            "cb1", catalog, "CB-001", on_equipment="pump"
        )


def test_pid_builder_catalog_missing_tag_raises():
    from schematika.pid.builder import PIDBuilder
    from schematika.pid.symbols import centrifugal_pump

    catalog = DeviceCatalog()

    builder = PIDBuilder()
    builder.add_equipment("pump", centrifugal_pump, "P", x=50, y=50)
    with pytest.raises(KeyError):
        builder.add_instrument_from_catalog(
            "xx", catalog, "NONEXISTENT", on_equipment="pump"
        )
