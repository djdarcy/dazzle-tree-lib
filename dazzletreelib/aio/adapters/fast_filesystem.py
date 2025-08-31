"""Fast filesystem adapter using os.scandir internally.

This experimental adapter uses os.scandir for maximum performance,
leveraging DirEntry's cached stat information to reduce syscalls.
"""

import asyncio
import os
import stat
from pathlib import Path
from typing import AsyncIterator, Dict, Any, Optional, List, Tuple
from collections import namedtuple

from ..core import AsyncTreeNode, AsyncTreeAdapter
from .filesystem import StatCache


# Lightweight data structure for passing scan results
ScanEntry = namedtuple('ScanEntry', ['path', 'name', 'stat', 'is_dir', 'is_file'])


class FastAsyncFileSystemNode(AsyncTreeNode):
    """Fast filesystem node with pre-cached stat data.
    
    Uses stat data from os.scandir's DirEntry to avoid
    additional stat calls.
    """
    
    def __init__(self, 
                 path: Path, 
                 cached_stat: Optional[os.stat_result] = None,
                 is_dir: Optional[bool] = None,
                 is_file: Optional[bool] = None):
        """Initialize fast filesystem node.
        
        Args:
            path: Path to file or directory
            cached_stat: Pre-cached stat result from scandir
            is_dir: Pre-cached directory flag
            is_file: Pre-cached file flag
        """
        self.path = Path(path) if not isinstance(path, Path) else path
        self._stat_cache = cached_stat
        self._is_dir = is_dir
        self._is_file = is_file
        self._metadata_cache: Optional[Dict[str, Any]] = None
    
    async def identifier(self) -> str:
        """Get unique identifier."""
        return str(self.path.absolute())
    
    async def metadata(self) -> Dict[str, Any]:
        """Get metadata using cached stat."""
        if self._metadata_cache is not None:
            return self._metadata_cache
        
        metadata = {
            'path': str(self.path),
            'name': self.path.name,
            'exists': True,  # We know it exists from scandir
        }
        
        # Use cached type info if available
        if self._is_file is not None:
            metadata['type'] = 'file' if self._is_file else 'directory'
        elif self._is_dir is not None:
            metadata['type'] = 'directory' if self._is_dir else 'file'
        else:
            # Fall back to path check
            metadata['type'] = 'file' if self.path.is_file() else 'directory'
        
        # Use cached stat if available
        if self._stat_cache:
            metadata.update({
                'size': self._stat_cache.st_size,
                'modified_time': self._stat_cache.st_mtime,
                'created_time': getattr(self._stat_cache, 'st_ctime', None),
                'mode': self._stat_cache.st_mode,
            })
        
        self._metadata_cache = metadata
        return metadata
    
    def is_leaf(self) -> bool:
        """Check if leaf node using cached info."""
        if self._is_file is not None:
            return self._is_file
        if self._is_dir is not None:
            return not self._is_dir
        return self.path.is_file() or not self.path.exists()
    
    async def display_name(self) -> str:
        """Get display name."""
        return self.path.name or str(self.path)
    
    async def size(self) -> Optional[int]:
        """Get size from cached stat."""
        if self._is_file or (self._is_file is None and self.path.is_file()):
            if self._stat_cache:
                return self._stat_cache.st_size
            # Fall back to fresh stat if needed
            stat = await self._get_stat()
            return stat.st_size if stat else None
        return None
    
    async def modified_time(self) -> Optional[float]:
        """Get mtime from cached stat."""
        if self._stat_cache:
            return self._stat_cache.st_mtime
        stat = await self._get_stat()
        return stat.st_mtime if stat else None
    
    async def _get_stat(self) -> Optional[os.stat_result]:
        """Get stat, using cache if available."""
        if self._stat_cache is not None:
            return self._stat_cache
        
        try:
            self._stat_cache = await asyncio.to_thread(self.path.stat)
            return self._stat_cache
        except (OSError, IOError):
            return None
    
    def __repr__(self) -> str:
        """String representation."""
        return f"FastAsyncFileSystemNode({self.path})"


class FastAsyncFileSystemAdapter(AsyncTreeAdapter):
    """Fast filesystem adapter using os.scandir.
    
    This adapter uses os.scandir internally which provides
    cached stat information via DirEntry objects, significantly
    reducing the number of syscalls needed.
    """
    
    def __init__(self,
                 max_concurrent: int = 100,
                 batch_size: int = 256,
                 follow_symlinks: bool = False):
        """Initialize fast filesystem adapter.
        
        Args:
            max_concurrent: Maximum concurrent I/O operations
            batch_size: Number of children to process in parallel
            follow_symlinks: Whether to follow symbolic links
        """
        super().__init__(max_concurrent)
        self.batch_size = batch_size
        self.follow_symlinks = follow_symlinks
    
    async def get_children(
        self,
        node: FastAsyncFileSystemNode
    ) -> AsyncIterator[FastAsyncFileSystemNode]:
        """Get children using os.scandir for performance.
        
        Uses os.scandir which provides cached stat information,
        significantly reducing syscalls compared to iterdir().
        
        Args:
            node: Parent directory node
            
        Yields:
            Child nodes with pre-cached stat data
        """
        if not node.path.is_dir():
            return
        
        # Use os.scandir in a thread for async operation
        entries = await self._scan_directory(node.path)
        
        # Process entries in batches
        for i in range(0, len(entries), self.batch_size):
            batch = entries[i:i + self.batch_size]
            
            # Create nodes with cached data
            for entry in batch:
                # Skip symlinks if not following
                if not self.follow_symlinks and stat.S_ISLNK(entry.stat.st_mode):
                    continue
                
                # Create node with pre-cached stat data
                child = FastAsyncFileSystemNode(
                    path=Path(entry.path),
                    cached_stat=entry.stat,
                    is_dir=entry.is_dir,
                    is_file=entry.is_file
                )
                yield child
    
    async def _scan_directory(self, path: Path) -> List[ScanEntry]:
        """Scan directory using os.scandir for cached stats.
        
        Args:
            path: Directory to scan
            
        Returns:
            List of ScanEntry with cached stat data
        """
        def scan():
            results = []
            try:
                with os.scandir(path) as entries:
                    for entry in entries:
                        try:
                            # DirEntry provides cached stat!
                            stat = entry.stat(follow_symlinks=self.follow_symlinks)
                            results.append(ScanEntry(
                                path=entry.path,
                                name=entry.name,
                                stat=stat,
                                is_dir=entry.is_dir(follow_symlinks=self.follow_symlinks),
                                is_file=entry.is_file(follow_symlinks=self.follow_symlinks)
                            ))
                        except (OSError, PermissionError):
                            # Skip inaccessible entries
                            pass
            except (OSError, PermissionError):
                # Can't read directory
                pass
            return results
        
        # Run in thread for async
        return await asyncio.to_thread(scan)
    
    async def get_parent(
        self,
        node: FastAsyncFileSystemNode
    ) -> Optional[FastAsyncFileSystemNode]:
        """Get parent directory."""
        parent_path = node.path.parent
        
        if parent_path == node.path:
            return None
        
        # Parent won't have cached stat, but that's okay
        return FastAsyncFileSystemNode(parent_path)
    
    async def get_depth(self, node: FastAsyncFileSystemNode) -> int:
        """Get depth from root."""
        depth = 0
        current = node.path
        
        while current.parent != current:
            depth += 1
            current = current.parent
        
        return depth


async def fast_traverse_tree(
    root: Path,
    max_depth: Optional[int] = None,
    follow_symlinks: bool = False
) -> AsyncIterator[FastAsyncFileSystemNode]:
    """Fast tree traversal using os.scandir.
    
    This function provides the fastest possible filesystem
    traversal by using os.scandir's cached stat information.
    
    Args:
        root: Root directory to traverse
        max_depth: Maximum depth to traverse
        follow_symlinks: Whether to follow symbolic links
        
    Yields:
        FastAsyncFileSystemNode objects with cached stats
    """
    from ..core import AsyncBreadthFirstTraverser
    
    root_node = FastAsyncFileSystemNode(root)
    adapter = FastAsyncFileSystemAdapter(follow_symlinks=follow_symlinks)
    traverser = AsyncBreadthFirstTraverser()
    
    async for node in traverser.traverse(root_node, adapter, max_depth):
        yield node