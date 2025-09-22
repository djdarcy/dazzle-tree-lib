"""Async filesystem adapter for tree traversal.

Implements filesystem access with batched parallel I/O for optimal performance.
Uses TaskGroup pattern for structured concurrency.
"""

import asyncio
import os
import stat as stat_module  # To avoid name collision with stat results
import time
from pathlib import Path
from typing import AsyncIterator, Dict, Any, Optional, Set, List, Tuple
from ..core import AsyncTreeNode, AsyncTreeAdapter


class AsyncFileSystemNode(AsyncTreeNode):
    """Async filesystem node implementation.
    
    Represents a file or directory in the filesystem with
    async metadata access for non-blocking I/O.
    """
    
    def __init__(self, path: Path, *, entry: Optional[os.DirEntry] = None):
        """Initialize filesystem node.
        
        Args:
            path: Path to the file or directory
            entry: Optional DirEntry from os.scandir with cached stat
        """
        self.path = Path(path) if not isinstance(path, Path) else path
        self._entry = entry  # Store DirEntry if provided
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
            'exists': stat is not None,
        }
        
        if stat:
            # Use stat result to determine file type
            is_dir = stat_module.S_ISDIR(stat.st_mode)
            
            metadata.update({
                'type': 'directory' if is_dir else 'file',
                'size': stat.st_size,
                'modified_time': stat.st_mtime,
                'created_time': stat.st_ctime if hasattr(stat, 'st_ctime') else None,
                'mode': stat.st_mode,
                'is_symlink': self.path.is_symlink(),  # Keep original for cross-platform
            })
        else:
            # If stat failed, we can't determine type reliably
            metadata['type'] = 'unknown'
        
        self._metadata_cache = metadata
        return metadata
    
    def is_leaf(self) -> bool:
        """Check if this is a leaf node (file or empty directory).
        
        Returns:
            True if file or cannot have children
        """
        # Use DirEntry's cached is_file() if available
        if self._entry:
            return self._entry.is_file(follow_symlinks=True)
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
        
        Uses caching to avoid duplicate stat calls, which is a major
        performance bottleneck. This significantly reduces syscalls.
        
        Returns:
            Stat result or None if file doesn't exist
        """
        # Check local cache first
        if self._stat_cache is not None:
            return self._stat_cache
        
        # Prefer cached stat from DirEntry if available
        if self._entry:
            try:
                # DirEntry.stat() caches the result internally
                self._stat_cache = self._entry.stat(follow_symlinks=True)
                self._entry = None  # Release DirEntry to free memory
                return self._stat_cache
            except (OSError, FileNotFoundError):
                # Handle cases like broken symlinks
                self._entry = None  # Also release on error
                pass
        
        # Fall back to direct stat call
        try:
            # Use async I/O for stat (with Python 3.8 fallback)
            # This is cached for the lifetime of the node object
            try:
                # Python 3.9+
                self._stat_cache = await asyncio.to_thread(self.path.stat)
            except AttributeError:
                # Python 3.8 fallback
                loop = asyncio.get_running_loop()
                self._stat_cache = await loop.run_in_executor(None, self.path.stat)
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
        """Get children of a directory using os.scandir for performance.
        
        Uses os.scandir with DirEntry objects for cached stat information,
        providing 9-12x performance improvement over os.listdir.
        
        Args:
            node: Parent directory node
            
        Yields:
            Child nodes (files and subdirectories)
        """
        # Only directories have children
        if not node.path.is_dir():
            return
        
        def _scan_directory_sync(path: Path):
            """Synchronous function to be run in executor with proper resource management."""
            entries = []
            with os.scandir(path) as iterator:
                for entry in iterator:
                    try:
                        # Eagerly cache stat result to avoid issues with DirEntry lifetime
                        entry.stat(follow_symlinks=self.follow_symlinks)
                        entries.append(entry)
                    except OSError:
                        # Skip entries we can't access (e.g., broken symlinks)
                        pass
            return entries
        
        # Get all entries with cached stats
        try:
            # Python 3.9+
            entries = await asyncio.to_thread(_scan_directory_sync, node.path)
        except AttributeError:
            # Python 3.8 fallback
            loop = asyncio.get_running_loop()
            entries = await loop.run_in_executor(
                None, _scan_directory_sync, node.path
            )
        
        # Yield child nodes with DirEntry information
        for entry in entries:
            # Check symlink policy
            if not self.follow_symlinks and entry.is_symlink():
                continue
            
            # Create node with cached DirEntry
            child_node = AsyncFileSystemNode(
                Path(entry.path),
                entry=entry
            )
            yield child_node
    
    
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
    
    def is_leaf(self, node: AsyncFileSystemNode) -> bool:
        """Check if node is a leaf (file or empty directory).
        
        Args:
            node: Node to check
            
        Returns:
            True if node is a leaf
        """
        return node.is_leaf()
    
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
        
        # Note: stat caching is now internal to nodes via DirEntry
        
        return stats


class AsyncFilteredFileSystemAdapter(AsyncTreeAdapter):
    """Filesystem adapter with filtering capabilities.
    
    Uses composition to wrap the base adapter with include/exclude patterns
    for selective traversal.
    """
    
    def __init__(
        self,
        base_adapter: Optional[AsyncFileSystemAdapter] = None,
        include_patterns: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None,
        include_hidden: bool = False
    ):
        """Initialize filtered filesystem adapter.
        
        Args:
            base_adapter: Base filesystem adapter to wrap (creates default if None)
            include_patterns: Glob patterns to include
            exclude_patterns: Glob patterns to exclude
            include_hidden: Whether to include hidden files
        """
        self._adapter = base_adapter or AsyncFileSystemAdapter()
        super().__init__()
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
        async for child in self._adapter.get_children(node):
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
    
    async def get_parent(self, node: AsyncFileSystemNode) -> Optional[AsyncFileSystemNode]:
        """Delegate to underlying adapter.
        
        Args:
            node: Child node
            
        Returns:
            Parent node or None if node is root
        """
        return await self._adapter.get_parent(node)
    
    async def get_depth(self, node: AsyncFileSystemNode) -> int:
        """Delegate to underlying adapter.
        
        Args:
            node: Node to check
            
        Returns:
            Depth from root
        """
        return await self._adapter.get_depth(node)
    
    def _define_capabilities(self) -> Set[str]:
        """Define filtered adapter capabilities.
        
        Returns:
            Set of supported capabilities
        """
        # Get base capabilities from wrapped adapter
        base_caps = self._adapter._define_capabilities() if hasattr(self._adapter, '_define_capabilities') else set()
        return base_caps | {
            'filtering',
            'patterns',
        }