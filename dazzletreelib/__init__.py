"""DazzleTreeLib - Universal Tree Traversal Library.

DazzleTreeLib provides a generic, extensible framework for traversing and operating on
any tree structure - filesystem, XML, JSON, databases, or custom data structures.
"""

__version__ = "0.1.0"

# Core abstractions
from .core.node import TreeNode
from .core.adapter import TreeAdapter
from .core.traverser import TreeTraverser
from .core.collector import DataCollector

# Configuration and planning
from .config import (
    TraversalConfig,
    DataRequirement,
    TraversalStrategy,
    CacheCompleteness,
)
from .planning import ExecutionPlan, CapabilityMismatchError

# High-level API
from .api import traverse_tree, collect_tree_data, count_nodes, find_nodes

# Common adapters
from .adapters.filesystem import FileSystemAdapter, FileSystemNode

__all__ = [
    # Version
    "__version__",
    
    # Core abstractions
    "TreeNode",
    "TreeAdapter", 
    "TreeTraverser",
    "DataCollector",
    
    # Configuration
    "TraversalConfig",
    "DataRequirement",
    "TraversalStrategy",
    "CacheCompleteness",
    
    # Planning
    "ExecutionPlan",
    "CapabilityMismatchError",
    
    # High-level API
    "traverse_tree",
    "collect_tree_data",
    "count_nodes",
    "find_nodes",
    
    # Filesystem adapter
    "FileSystemAdapter",
    "FileSystemNode",
]