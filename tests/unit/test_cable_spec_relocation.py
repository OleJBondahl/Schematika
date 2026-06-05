"""C0: CableData/ConnectorData live in Layer-1 catalog; old import paths preserved."""

import dataclasses


def test_cable_spec_types_live_in_catalog() -> None:
    from schematika.catalog import CableData, ConnectorData
    from schematika.catalog.cables import CableData as CDModule
    from schematika.catalog.cables import ConnectorData as CnModule

    assert CableData is CDModule
    assert ConnectorData is CnModule


def test_field_devices_shim_reexports_same_objects() -> None:
    from schematika.catalog import CableData as CatalogCable
    from schematika.catalog import ConnectorData as CatalogConn
    from schematika.electrical.field_devices import CableData, ConnectorData

    assert CableData is CatalogCable
    assert ConnectorData is CatalogConn


def test_electrical_public_api_still_exports_cable_spec() -> None:
    from schematika.catalog import CableData as CatalogCable
    from schematika.catalog import ConnectorData as CatalogConn
    from schematika.electrical import CableData, ConnectorData, DeviceCable

    assert CableData is CatalogCable
    assert ConnectorData is CatalogConn
    assert DeviceCable is not None


def test_wire_colour_singular_field_dropped() -> None:
    from schematika.catalog import CableData

    names = {f.name for f in dataclasses.fields(CableData)}
    assert "wire_colour" not in names
    assert "wire_colors" in names
