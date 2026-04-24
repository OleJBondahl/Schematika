"""Errors for the schematika.cable module."""


class CableError(ValueError):
    """Base exception for cable building and catalog errors.

    Inherits from ``ValueError`` for backward-compat with call sites that
    catch ``ValueError``; new code should catch ``CableError`` explicitly.
    """
