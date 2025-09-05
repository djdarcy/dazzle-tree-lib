"""Core abstractions for async tree traversal.

This module defines the fundamental interfaces for async tree operations.
All components use async/await patterns for non-blocking I/O.
"""

from .node import AsyncTreeNode
from .adapter import AsyncTreeAdapter, CacheKeyMixin
from .traverser import (
    AsyncTreeTraverser,
    AsyncBreadthFirstTraverser,
    AsyncDepthFirstTraverser,
)
from .collector import (
    AsyncDataCollector,
    AsyncMetadataCollector,
    AsyncPathCollector,
)

__all__ = [
    # Node
    'AsyncTreeNode',
    # Adapter
    'AsyncTreeAdapter',
    'CacheKeyMixin',
    # Traversers
    'AsyncTreeTraverser',
    'AsyncBreadthFirstTraverser', 
    'AsyncDepthFirstTraverser',
    # Collectors
    'AsyncDataCollector',
    'AsyncMetadataCollector',
    'AsyncPathCollector',
]