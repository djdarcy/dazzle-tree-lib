"""Asynchronous implementation of DazzleTreeLib.

This package contains native async/await implementations for non-blocking
tree traversal operations. All components support concurrent I/O operations.
"""

# Core abstractions
from .core import (
    AsyncTreeNode,
    AsyncTreeAdapter,
    AsyncTreeTraverser,
    AsyncBreadthFirstTraverser,
    AsyncDepthFirstTraverser,
    AsyncDataCollector,
    AsyncMetadataCollector,
    AsyncPathCollector,
)

# Adapters
from .adapters import (
    AsyncFileSystemNode,
    AsyncFileSystemAdapter,
    AsyncFilteredFileSystemAdapter,
)

# Planning and orchestration
from .planning import AsyncExecutionPlan

# High-level API
from .api import (
    traverse_tree_async,
    collect_metadata_async,
    get_tree_paths_async,
    calculate_size_async,
    find_files_async,
    find_directories_async,
    parallel_traverse,
    get_tree_stats_async,
    filter_tree_async,
    count_nodes_async,
    get_leaf_nodes_async,
)

# Configuration (re-exported from _common)
from .config import (
    TraversalConfig,
    TraversalStrategy,
    DataRequirement,
)

__all__ = [
    # Core abstractions
    'AsyncTreeNode',
    'AsyncTreeAdapter',
    'AsyncTreeTraverser',
    # Nodes
    'AsyncFileSystemNode',
    # Adapters
    'AsyncFileSystemAdapter',
    'AsyncFilteredFileSystemAdapter',
    # Traversers
    'AsyncBreadthFirstTraverser',
    'AsyncDepthFirstTraverser',
    # Collectors
    'AsyncDataCollector',
    'AsyncMetadataCollector',
    'AsyncPathCollector',
    # Planning
    'AsyncExecutionPlan',
    # Configuration
    'TraversalConfig',
    'TraversalStrategy',
    'DataRequirement',
    # High-level API
    'traverse_tree_async',
    'collect_metadata_async',
    'get_tree_paths_async',
    'calculate_size_async',
    'find_files_async',
    'find_directories_async',
    'parallel_traverse',
    'get_tree_stats_async',
    'filter_tree_async',
    'count_nodes_async',
    'get_leaf_nodes_async',
]