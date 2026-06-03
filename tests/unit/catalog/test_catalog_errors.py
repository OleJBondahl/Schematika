"""Tests for the Phase-1 catalog error subclasses."""

import pytest

from schematika.catalog.errors import (
    CatalogError,
    CatalogLookupError,
    CatalogValidationError,
)


def test_lookup_error_is_catalog_error():
    assert issubclass(CatalogLookupError, CatalogError)


def test_validation_error_is_catalog_error():
    assert issubclass(CatalogValidationError, CatalogError)


def test_subclasses_are_distinct():
    assert CatalogLookupError is not CatalogValidationError


def test_lookup_error_raisable():
    msg = "missing"
    with pytest.raises(CatalogError):
        raise CatalogLookupError(msg)
