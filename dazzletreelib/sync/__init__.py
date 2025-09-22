"""Synchronous implementation of DazzleTreeLib.

This package contains the original synchronous tree traversal implementation.
All components here operate in a blocking, synchronous manner.
"""

# Core components
from .core.node import TreeNode
from .core.adapter import TreeAdapter
from .core.traverser import (
    TreeTraverser,
    BreadthFirstTraverser,
    DepthFirstPreOrderTraverser,
    DepthFirstPostOrderTraverser,
    LevelOrderTraverser
)
from .core.collector import (
    DataCollector,
    IdentifierCollector,
    MetadataCollector,
    PathCollector,
    FullNodeCollector,
    ChildCountCollector,
    AggregateCollector,
    SumCollector,
    MaxCollector,
    CustomCollector
)

# Adapters
from .adapters.filesystem import (
    FileSystemAdapter,
    FilteredFileSystemAdapter,
    FileSystemNode
)

# Configuration and planning
from .config import (
    TraversalConfig,
    TraversalStrategy,
    DataRequirement,
    CacheStrategy,
    CacheCompleteness,
    FilterConfig,
    DepthConfig,
    PerformanceConfig
)
from .planning import ExecutionPlan, CapabilityMismatchError

# High-level API
from .api import (
    traverse_tree,
    collect_tree_data,
    count_nodes,
    find_nodes,
    get_tree_paths,
    get_leaf_nodes,
    get_tree_stats
)

__all__ = [
    # Core
    'TreeNode',
    'TreeAdapter',
    'TreeTraverser',
    'BreadthFirstTraverser',
    'DepthFirstPreOrderTraverser',
    'DepthFirstPostOrderTraverser',
    'LevelOrderTraverser',
    'DataCollector',
    'IdentifierCollector',
    'MetadataCollector',
    'PathCollector',
    'FullNodeCollector',
    'ChildCountCollector',
    'AggregateCollector',
    'SumCollector',
    'MaxCollector',
    'CustomCollector',
    # Adapters
    'FileSystemAdapter',
    'FilteredFileSystemAdapter',
    'FileSystemNode',
    # Config
    'TraversalConfig',
    'TraversalStrategy',
    'DataRequirement',
    'CacheStrategy',
    'CacheCompleteness',
    'FilterConfig',
    'DepthConfig',
    'PerformanceConfig',
    'ExecutionPlan',
    'CapabilityMismatchError',
    # API
    'traverse_tree',
    'collect_tree_data',
    'count_nodes',
    'find_nodes',
    'get_tree_paths',
    'get_leaf_nodes',
    'get_tree_stats',
]