"""
Caching layer for DazzleTreeLib - Optional performance optimization.

This module provides opt-in caching capabilities for tree traversal operations,
offering significant speedup (10x+) for warm runs while maintaining the simplicity
of the core library.
"""

from .adapter import CachingTreeAdapter, FilesystemCachingAdapter

__all__ = [
    'CachingTreeAdapter',
    'FilesystemCachingAdapter',
]