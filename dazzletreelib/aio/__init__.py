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
    TimestampCalculationAdapter,
    CompletenessAwareCacheAdapter,
    CacheCompleteness,
    DepthTrackingAdapter,
)

# Post-order traversal
from .traversal.post_order import (
    traverse_post_order_with_depth,
    traverse_tree_bottom_up,
    collect_by_level_bottom_up,
    process_folders_bottom_up,
)

# Planning and orchestration
from .planning import AsyncExecutionPlan

# High-level API
from .api import (
    traverse_tree_async,
    traverse_with_depth,
    traverse_tree_by_level,
    filter_by_depth,
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
    'TimestampCalculationAdapter',
    'CompletenessAwareCacheAdapter',
    'CacheCompleteness',
    'DepthTrackingAdapter',
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
    'traverse_with_depth',
    'traverse_tree_by_level',
    'filter_by_depth',
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
    # Post-order traversal
    'traverse_post_order_with_depth',
    'traverse_tree_bottom_up',
    'collect_by_level_bottom_up',
    'process_folders_bottom_up',
]