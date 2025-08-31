"""Async filesystem adapter for tree traversal.

Implements filesystem access with batched parallel I/O for optimal performance.
Uses TaskGroup pattern for structured concurrency.
"""

import asyncio
import os
from pathlib import Path
from typing import AsyncIterator, Dict, Any, Optional, Set, List
from ..core import AsyncTreeNode, AsyncTreeAdapter


class AsyncFileSystemNode(AsyncTreeNode):
    """Async filesystem node implementation.
    
    Represents a file or directory in the filesystem with
    async metadata access for non-blocking I/O.
    """
    
    def __init__(self, path: Path):
        """Initialize filesystem node.
        
        Args:
            path: Path to the file or directory
        """
        self.path = Path(path) if not isinstance(path, Path) else path
        self._stat_cache: Optional[os.stat_result] = None
        self._metadata_cache: Optional[Dict[str, Any]] = None
    
    async def identifier(self) -> str:
        """Get unique identifier (absolute path).
        
        Returns:
            Absolute path as string
        """
        return str(self.path.absolute())
    
    async def metadata(self) -> Dict[str, Any]:
        """Get file/directory metadata.
        
        Fetches stat information asynchronously and caches it.
        
        Returns:
            Dictionary with size, mtime, type, etc.
        """
        if self._metadata_cache is not None:
            return self._metadata_cache
        
        # Get stat info asynchronously
        stat = await self._get_stat()
        
        metadata = {
            'path': str(self.path),
            'name': self.path.name,
            'type': 'file' if self.path.is_file() else 'directory',
            'exists': self.path.exists(),
        }
        
        if stat:
            metadata.update({
                'size': stat.st_size,
                'modified_time': stat.st_mtime,
                'created_time': stat.st_ctime if hasattr(stat, 'st_ctime') else None,
                'mode': stat.st_mode,
                'is_symlink': self.path.is_symlink(),
            })
        
        self._metadata_cache = metadata
        return metadata
    
    def is_leaf(self) -> bool:
        """Check if this is a leaf node (file or empty directory).
        
        Returns:
            True if file or cannot have children
        """
        return self.path.is_file() or not self.path.exists()
    
    async def display_name(self) -> str:
        """Get display name for the node.
        
        Returns:
            File/directory name
        """
        return self.path.name or str(self.path)
    
    async def size(self) -> Optional[int]:
        """Get file size in bytes.
        
        Returns:
            Size in bytes or None for directories
        """
        if self.path.is_file():
            stat = await self._get_stat()
            return stat.st_size if stat else None
        return None
    
    async def modified_time(self) -> Optional[float]:
        """Get modification time as Unix timestamp.
        
        Returns:
            Modification time or None
        """
        stat = await self._get_stat()
        return stat.st_mtime if stat else None
    
    async def _get_stat(self) -> Optional[os.stat_result]:
        """Get cached or fresh stat information.
        
        Returns:
            Stat result or None if file doesn't exist
        """
        if self._stat_cache is not None:
            return self._stat_cache
        
        try:
            # Use asyncio.to_thread for async stat
            self._stat_cache = await asyncio.to_thread(self.path.stat)
            return self._stat_cache
        except (OSError, IOError):
            return None
    
    def __repr__(self) -> str:
        """String representation."""
        return f"AsyncFileSystemNode({self.path})"


class AsyncFileSystemAdapter(AsyncTreeAdapter):
    """Async filesystem adapter with batched parallel I/O.
    
    Implements the TaskGroup pattern for efficient parallel
    child fetching as recommended in our design discussion.
    """
    
    def __init__(
        self,
        max_concurrent: int = 100,
        batch_size: int = 256,
        follow_symlinks: bool = False
    ):
        """Initialize filesystem adapter.
        
        Args:
            max_concurrent: Maximum concurrent I/O operations
            batch_size: Number of children to process in parallel per batch
            follow_symlinks: Whether to follow symbolic links
        """
        super().__init__(max_concurrent)
        self.batch_size = batch_size
        self.follow_symlinks = follow_symlinks
        self._root_cache: Dict[str, AsyncFileSystemNode] = {}
    
    async def get_children(
        self,
        node: AsyncFileSystemNode
    ) -> AsyncIterator[AsyncFileSystemNode]:
        """Get children of a directory with batched parallel I/O.
        
        Uses TaskGroup for structured concurrency as per our design.
        Processes children in batches to balance parallelism and memory.
        
        Args:
            node: Parent directory node
            
        Yields:
            Child nodes (files and subdirectories)
        """
        # Only directories have children
        if not node.path.is_dir():
            return
        
        try:
            # List directory contents asynchronously
            paths = await asyncio.to_thread(os.listdir, node.path)
        except (OSError, PermissionError):
            # Can't read directory - no children to yield
            return
        
        # Process in batches for memory efficiency
        for i in range(0, len(paths), self.batch_size):
            batch_paths = paths[i:i + self.batch_size]
            
            # Use TaskGroup for parallel child creation
            try:
                async with asyncio.TaskGroup() as tg:
                    tasks = [
                        tg.create_task(self._create_child_node(node.path / name))
                        for name in batch_paths
                    ]
                
                # TaskGroup completed successfully, yield results
                for task in tasks:
                    child_node = task.result()
                    if child_node is not None:
                        yield child_node
                        
            except* (OSError, PermissionError) as eg:
                # Handle partial failures - some children couldn't be accessed
                # Log or ignore based on configuration
                for task in tasks:
                    if not task.cancelled() and task.exception() is None:
                        child_node = task.result()
                        if child_node is not None:
                            yield child_node
    
    async def _create_child_node(
        self,
        path: Path
    ) -> Optional[AsyncFileSystemNode]:
        """Create a child node with concurrency control.
        
        Args:
            path: Path to the child
            
        Returns:
            AsyncFileSystemNode or None if invalid
        """
        async with self.semaphore:
            try:
                # Check if path exists and is valid
                if not await asyncio.to_thread(path.exists):
                    return None
                
                # Check symlink policy
                if not self.follow_symlinks and path.is_symlink():
                    return None
                
                return AsyncFileSystemNode(path)
                
            except (OSError, PermissionError):
                # File might have been deleted or inaccessible
                return None
    
    async def get_parent(
        self,
        node: AsyncFileSystemNode
    ) -> Optional[AsyncFileSystemNode]:
        """Get parent directory of a node.
        
        Args:
            node: Child node
            
        Returns:
            Parent node or None if node is root
        """
        parent_path = node.path.parent
        
        # Check if we're at root
        if parent_path == node.path:
            return None
        
        return AsyncFileSystemNode(parent_path)
    
    async def get_depth(self, node: AsyncFileSystemNode) -> int:
        """Get depth of node from root.
        
        Args:
            node: Node to check
            
        Returns:
            Depth (0 for root)
        """
        # Count parents until we reach root
        depth = 0
        current = node.path
        
        # Find the root we're measuring from
        root_path = self._find_root_path(node)
        
        while current != root_path and current.parent != current:
            depth += 1
            current = current.parent
        
        return depth
    
    def _find_root_path(self, node: AsyncFileSystemNode) -> Path:
        """Find the root path for depth calculation.
        
        Args:
            node: Current node
            
        Returns:
            Root path
        """
        # If we have cached roots, use the matching one
        node_str = str(node.path)
        for root_str in self._root_cache:
            if node_str.startswith(root_str):
                return Path(root_str)
        
        # Otherwise, assume filesystem root
        return node.path.anchor if hasattr(node.path, 'anchor') else Path('/')
    
    def _define_capabilities(self) -> Set[str]:
        """Define filesystem adapter capabilities.
        
        Returns:
            Set of supported capabilities
        """
        return super()._define_capabilities() | {
            'stat',
            'size',
            'mtime',
            'symlinks',
            'batched_io',
        }
    
    async def get_stats(self) -> dict:
        """Get adapter statistics.
        
        Returns:
            Statistics dictionary
        """
        stats = await super().get_stats()
        stats.update({
            'batch_size': self.batch_size,
            'follow_symlinks': self.follow_symlinks,
            'cached_roots': len(self._root_cache),
        })
        return stats


class AsyncFilteredFileSystemAdapter(AsyncFileSystemAdapter):
    """Filesystem adapter with filtering capabilities.
    
    Extends the base adapter with include/exclude patterns
    for selective traversal.
    """
    
    def __init__(
        self,
        max_concurrent: int = 100,
        batch_size: int = 256,
        follow_symlinks: bool = False,
        include_patterns: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None,
        include_hidden: bool = False
    ):
        """Initialize filtered filesystem adapter.
        
        Args:
            max_concurrent: Maximum concurrent I/O operations
            batch_size: Number of children to process in parallel
            follow_symlinks: Whether to follow symbolic links
            include_patterns: Glob patterns to include
            exclude_patterns: Glob patterns to exclude
            include_hidden: Whether to include hidden files
        """
        super().__init__(max_concurrent, batch_size, follow_symlinks)
        self.include_patterns = include_patterns or []
        self.exclude_patterns = exclude_patterns or []
        self.include_hidden = include_hidden
    
    async def get_children(
        self,
        node: AsyncFileSystemNode
    ) -> AsyncIterator[AsyncFileSystemNode]:
        """Get filtered children of a directory.
        
        Args:
            node: Parent directory node
            
        Yields:
            Filtered child nodes
        """
        async for child in super().get_children(node):
            if await self._should_include(child):
                yield child
    
    async def _should_include(self, node: AsyncFileSystemNode) -> bool:
        """Check if node passes filters.
        
        Args:
            node: Node to check
            
        Returns:
            True if node should be included
        """
        name = node.path.name
        
        # Check hidden files
        if not self.include_hidden and name.startswith('.'):
            return False
        
        # Check exclude patterns first (exclusion takes precedence)
        for pattern in self.exclude_patterns:
            if node.path.match(pattern):
                return False
        
        # Check include patterns (if any specified)
        if self.include_patterns:
            for pattern in self.include_patterns:
                if node.path.match(pattern):
                    return True
            return False  # Didn't match any include pattern
        
        # No include patterns means include by default
        return True
    
    def _define_capabilities(self) -> Set[str]:
        """Define filtered adapter capabilities.
        
        Returns:
            Set of supported capabilities
        """
        return super()._define_capabilities() | {
            'filtering',
            'patterns',
        }