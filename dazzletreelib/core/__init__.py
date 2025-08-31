"""Core abstractions for TreeLib.

This module contains the fundamental abstract base classes that define
the TreeLib architecture.
"""

from .node import TreeNode
from .adapter import TreeAdapter
from .traverser import TreeTraverser
from .collector import DataCollector

__all__ = [
    "TreeNode",
    "TreeAdapter",
    "TreeTraverser", 
    "DataCollector",
]