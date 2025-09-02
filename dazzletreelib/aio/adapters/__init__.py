"""Async adapters for various tree structures.

This module contains adapters that bridge specific data sources
(filesystem, databases, APIs) to the generic async tree interface.
"""

from .filesystem import (
    AsyncFileSystemNode,
    AsyncFileSystemAdapter,
    AsyncFilteredFileSystemAdapter,
)
from .timestamp_adapter import TimestampCalculationAdapter
from .cache_completeness_adapter import (
    CacheCompleteness,
    CompletenessAwareCacheAdapter,
)
from .depth_tracking_adapter import DepthTrackingAdapter

__all__ = [
    'AsyncFileSystemNode',
    'AsyncFileSystemAdapter',
    'AsyncFilteredFileSystemAdapter',
    'TimestampCalculationAdapter',
    'CacheCompleteness',
    'CompletenessAwareCacheAdapter',
    'DepthTrackingAdapter',
]