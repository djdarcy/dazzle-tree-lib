"""Async adapters for various tree structures.

This module contains adapters that bridge specific data sources
(filesystem, databases, APIs) to the generic async tree interface.
"""

from .filesystem import (
    AsyncFileSystemNode,
    AsyncFileSystemAdapter,
    AsyncFilteredFileSystemAdapter,
)

__all__ = [
    'AsyncFileSystemNode',
    'AsyncFileSystemAdapter',
    'AsyncFilteredFileSystemAdapter',
]