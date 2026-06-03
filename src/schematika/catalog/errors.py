"""Errors for the schematika.catalog module."""


class CatalogError(ValueError):
    """Base exception for device/cable catalog lookup and validation errors.

    Inherits from ``ValueError`` for backward-compat with call sites that
    catch ``ValueError``; new code should catch ``CatalogError`` explicitly.
    Raised by ``Catalog.add_device`` and ``Catalog.add_cable_instance``
    (and the legacy ``DeviceCatalog.register``) on duplicate tag registration.

    Examples:
        >>> from schematika.catalog import CatalogError
        >>> try:
        ...     raise CatalogError("Device 'TT-101' already registered")
        ... except CatalogError as e:
        ...     str(e)
        "Device 'TT-101' already registered"
    """
