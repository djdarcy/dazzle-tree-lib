"""Asynchronous implementation of DazzleTreeLib.

This package contains native async/await implementations for non-blocking
tree traversal operations. All components support concurrent I/O operations.
"""

# Import from async_core for now - will be refactored into proper modules
from .async_core import (
    AsyncFileSystemNode,
    AsyncFileSystemAdapter,
    AsyncBreadthFirstTraverser,
    AsyncDepthFirstTraverser,
    AsyncDataCollector,
    AsyncMetadataCollector,
    AsyncExecutionPlan,
    # High-level async API
    traverse_tree_async,
    collect_metadata_async,
    parallel_traverse,
    find_files_async,
    calculate_size_async,
)

__all__ = [
    # Nodes
    'AsyncFileSystemNode',
    # Adapters
    'AsyncFileSystemAdapter',
    # Traversers
    'AsyncBreadthFirstTraverser',
    'AsyncDepthFirstTraverser',
    # Collectors
    'AsyncDataCollector',
    'AsyncMetadataCollector',
    # Planning
    'AsyncExecutionPlan',
    # High-level API
    'traverse_tree_async',
    'collect_metadata_async',
    'parallel_traverse',
    'find_files_async',
    'calculate_size_async',
]