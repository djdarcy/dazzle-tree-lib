"""Tree adapters for specific tree structures.

Adapters implement the TreeAdapter interface for different tree types,
enabling DazzleTreeLib to work with any tree structure.
"""

from .filesystem import FileSystemAdapter, FileSystemNode, FilteredFileSystemAdapter

__all__ = [
    "FileSystemAdapter",
    "FileSystemNode",
    "FilteredFileSystemAdapter",
]