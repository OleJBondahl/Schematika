"""Errors for the schematika.catalog module."""


class CatalogError(ValueError):
    """Base exception for device/cable catalog lookup and validation errors.

    Inherits from ``ValueError`` for backward-compat with call sites that
    catch ``ValueError``; new code should catch ``CatalogError`` explicitly.
    """
