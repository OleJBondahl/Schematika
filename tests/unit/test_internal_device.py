from schematika.electrical import InternalDevice


def test_internal_device_creation():
    dev = InternalDevice("Q", "LC1D09", "Contactor 9A")
    assert dev.prefix == "Q"
    assert dev.mpn == "LC1D09"
    assert dev.description == "Contactor 9A"


def test_internal_device_is_frozen():
    dev = InternalDevice("K", "MY2N", "Relay")
    import dataclasses

    assert dataclasses.is_dataclass(dev)
    try:
        dev.prefix = "X"  # type: ignore[invalid-assignment]
        msg = "Should be frozen"
        raise AssertionError(msg)
    except AttributeError:
        pass


def test_internal_device_equality():
    a = InternalDevice("Q", "LC1D09", "Contactor 9A")
    b = InternalDevice("Q", "LC1D09", "Contactor 9A")
    assert a == b
