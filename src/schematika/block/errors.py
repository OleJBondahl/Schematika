"""Errors for the schematika.block module."""


class BlockError(ValueError):
    """Base exception for block diagram building and layout errors.

    Inherits from ``ValueError`` for backward-compat with call sites that
    catch ``ValueError``; new code should catch ``BlockError`` explicitly.
    """
