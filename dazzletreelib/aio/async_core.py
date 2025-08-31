"""Async support for DazzleTreeLib.

Native async/await implementation for tree traversal operations,
enabling non-blocking I/O and parallel tree processing.
"""

import asyncio
from typing import AsyncIterator, Optional, Any, List, Tuple
from pathlib import Path
import os
from datetime import datetime

from ..sync.core.node import TreeNode
from ..sync.core.adapter import TreeAdapter
from ..sync.core.collector import DataCollector


class AsyncFileSystemNode(TreeNode):
    """Async version of FileSystemNode with non-blocking I/O."""
    
    def __init__(self, path: Path):
        """Initialize with a filesystem path."""
        self.path = Path(path)
        self._metadata_cache = None
        self._stat_cache = None
    
    def identifier(self) -> str:
        """Return string representation of path."""
        return str(self.path)
    
    def is_leaf(self) -> bool:
        """Check if this is a leaf node (file or empty directory)."""
        return self.path.is_file()
    
    async def stat_async(self):
        """Get file stats asynchronously."""
        if self._stat_cache is None:
            loop = asyncio.get_event_loop()
            self._stat_cache = await loop.run_in_executor(None, self.path.stat)
        return self._stat_cache
    
    async def metadata_async(self) -> dict:
        """Get metadata asynchronously."""
        if self._metadata_cache is None:
            stat = await self.stat_async()
            self._metadata_cache = {
                'name': self.path.name,
                'path': str(self.path),
                'exists': self.path.exists(),
                'size': stat.st_size if self.path.is_file() else 0,
                'mtime': stat.st_mtime,
                'mtime_dt': datetime.fromtimestamp(stat.st_mtime),
                'ctime': stat.st_ctime,
                'ctime_dt': datetime.fromtimestamp(stat.st_ctime),
                'atime': stat.st_atime,
                'atime_dt': datetime.fromtimestamp(stat.st_atime),
                'mode': stat.st_mode,
                'uid': stat.st_uid,
                'gid': stat.st_gid,
                'is_file': self.path.is_file(),
                'is_dir': self.path.is_dir(),
                'is_link': self.path.is_symlink(),
                'is_mount': self.path.is_mount(),
                'readable': os.access(self.path, os.R_OK),
                'writable': os.access(self.path, os.W_OK),
                'executable': os.access(self.path, os.X_OK),
                'extension': self.path.suffix if self.path.is_file() else None,
            }
        return self._metadata_cache
    
    def metadata(self) -> dict:
        """Sync metadata for compatibility."""
        if self._metadata_cache is None:
            # Force sync load if not cached
            stat = self.path.stat()
            self._metadata_cache = {
                'name': self.path.name,
                'path': str(self.path),
                'exists': self.path.exists(),
                'size': stat.st_size if self.path.is_file() else 0,
                'mtime': stat.st_mtime,
                'mtime_dt': datetime.fromtimestamp(stat.st_mtime),
                'ctime': stat.st_ctime,
                'ctime_dt': datetime.fromtimestamp(stat.st_ctime),
                'atime': stat.st_atime,
                'atime_dt': datetime.fromtimestamp(stat.st_atime),
                'mode': stat.st_mode,
                'uid': stat.st_uid,
                'gid': stat.st_gid,
                'is_file': self.path.is_file(),
                'is_dir': self.path.is_dir(),
                'is_link': self.path.is_symlink(),
                'is_mount': self.path.is_mount(),
                'readable': os.access(self.path, os.R_OK),
                'writable': os.access(self.path, os.W_OK),
                'executable': os.access(self.path, os.X_OK),
                'extension': self.path.suffix if self.path.is_file() else None,
            }
        return self._metadata_cache


class AsyncFileSystemAdapter(TreeAdapter):
    """Async adapter for filesystem trees."""
    
    def __init__(self, 
                 follow_symlinks: bool = False,
                 max_concurrent: int = 100):
        """Initialize async filesystem adapter.
        
        Args:
            follow_symlinks: Whether to follow symbolic links
            max_concurrent: Maximum concurrent I/O operations
        """
        self.follow_symlinks = follow_symlinks
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def get_children_async(self, node: AsyncFileSystemNode) -> AsyncIterator[AsyncFileSystemNode]:
        """Get child nodes asynchronously."""
        if not node.path.is_dir():
            return
        
        async with self.semaphore:
            loop = asyncio.get_event_loop()
            
            # List directory contents in executor
            def list_dir():
                try:
                    return list(node.path.iterdir())
                except (PermissionError, OSError):
                    return []
            
            children_paths = await loop.run_in_executor(None, list_dir)
            
            for child_path in sorted(children_paths):
                # Skip symlinks if not following
                if child_path.is_symlink() and not self.follow_symlinks:
                    continue
                
                yield AsyncFileSystemNode(child_path)
    
    def get_children(self, node: TreeNode) -> List[TreeNode]:
        """Sync version for compatibility."""
        if not isinstance(node, AsyncFileSystemNode):
            node = AsyncFileSystemNode(Path(node.identifier()))
        
        if not node.path.is_dir():
            return []
        
        children = []
        try:
            for child_path in sorted(node.path.iterdir()):
                if child_path.is_symlink() and not self.follow_symlinks:
                    continue
                children.append(AsyncFileSystemNode(child_path))
        except (PermissionError, OSError):
            pass
        
        return children
    
    def get_parent(self, node: TreeNode) -> Optional[TreeNode]:
        """Get parent node."""
        if not isinstance(node, AsyncFileSystemNode):
            node = AsyncFileSystemNode(Path(node.identifier()))
        
        parent_path = node.path.parent
        if parent_path != node.path:
            return AsyncFileSystemNode(parent_path)
        return None
    
    def get_depth(self, node: TreeNode) -> int:
        """Calculate depth from root."""
        depth = 0
        current = node
        while True:
            parent = self.get_parent(current)
            if parent is None:
                break
            depth += 1
            current = parent
        return depth


class AsyncBreadthFirstTraverser:
    """Async breadth-first traversal."""
    
    def __init__(self, adapter: AsyncFileSystemAdapter):
        self.adapter = adapter
    
    async def traverse_async(self, root: AsyncFileSystemNode, 
                            max_depth: Optional[int] = None) -> AsyncIterator[Tuple[AsyncFileSystemNode, int]]:
        """Traverse tree breadth-first asynchronously."""
        queue = asyncio.Queue()
        await queue.put((root, 0))
        
        while not queue.empty():
            node, depth = await queue.get()
            
            yield node, depth
            
            # Check depth limit
            if max_depth is not None and depth >= max_depth:
                continue
            
            # Add children to queue
            async for child in self.adapter.get_children_async(node):
                await queue.put((child, depth + 1))


class AsyncDepthFirstTraverser:
    """Async depth-first traversal."""
    
    def __init__(self, adapter: AsyncFileSystemAdapter, post_order: bool = False):
        self.adapter = adapter
        self.post_order = post_order
    
    async def traverse_async(self, root: AsyncFileSystemNode,
                            max_depth: Optional[int] = None) -> AsyncIterator[Tuple[AsyncFileSystemNode, int]]:
        """Traverse tree depth-first asynchronously."""
        async def visit(node: AsyncFileSystemNode, depth: int):
            # Pre-order: yield before children
            if not self.post_order:
                yield node, depth
            
            # Visit children if within depth limit
            if max_depth is None or depth < max_depth:
                async for child in self.adapter.get_children_async(node):
                    async for result in visit(child, depth + 1):
                        yield result
            
            # Post-order: yield after children
            if self.post_order:
                yield node, depth
        
        async for result in visit(root, 0):
            yield result


class AsyncDataCollector(DataCollector):
    """Base class for async data collectors."""
    
    def __init__(self, adapter: AsyncFileSystemAdapter):
        self.adapter = adapter
    
    async def collect_async(self, node: AsyncFileSystemNode, depth: int) -> Any:
        """Collect data asynchronously."""
        return node.identifier()
    
    def collect(self, node: TreeNode, depth: int) -> Any:
        """Sync version for compatibility."""
        return node.identifier()
    
    def requires_children(self) -> bool:
        """Whether this collector needs child access."""
        return False


class AsyncMetadataCollector(AsyncDataCollector):
    """Collect metadata asynchronously."""
    
    async def collect_async(self, node: AsyncFileSystemNode, depth: int) -> dict:
        """Collect metadata asynchronously."""
        return await node.metadata_async()
    
    def collect(self, node: TreeNode, depth: int) -> dict:
        """Sync version."""
        if isinstance(node, AsyncFileSystemNode):
            return node.metadata()
        return {}


class AsyncExecutionPlan:
    """Async execution plan for tree traversal."""
    
    def __init__(self, traversal_strategy: str = 'bfs',
                 data_collector: Optional[AsyncDataCollector] = None,
                 max_depth: Optional[int] = None,
                 max_concurrent: int = 100):
        """Initialize async execution plan.
        
        Args:
            traversal_strategy: 'bfs' or 'dfs' or 'dfs_post'
            data_collector: Collector for data extraction
            max_depth: Maximum traversal depth
            max_concurrent: Maximum concurrent operations
        """
        self.adapter = AsyncFileSystemAdapter(max_concurrent=max_concurrent)
        self.max_depth = max_depth
        
        # Select traverser
        if traversal_strategy == 'bfs':
            self.traverser = AsyncBreadthFirstTraverser(self.adapter)
        elif traversal_strategy == 'dfs':
            self.traverser = AsyncDepthFirstTraverser(self.adapter, post_order=False)
        elif traversal_strategy == 'dfs_post':
            self.traverser = AsyncDepthFirstTraverser(self.adapter, post_order=True)
        else:
            raise ValueError(f"Unknown strategy: {traversal_strategy}")
        
        # Select collector
        self.collector = data_collector or AsyncMetadataCollector(self.adapter)
    
    async def execute_async(self, root: Path) -> AsyncIterator[Tuple[AsyncFileSystemNode, Any]]:
        """Execute traversal plan asynchronously."""
        root_node = AsyncFileSystemNode(root)
        
        async for node, depth in self.traverser.traverse_async(root_node, self.max_depth):
            data = await self.collector.collect_async(node, depth)
            yield node, data


# High-level async API functions

async def traverse_tree_async(root: Path, 
                             strategy: str = 'bfs',
                             max_depth: Optional[int] = None,
                             max_concurrent: int = 100) -> AsyncIterator[Tuple[AsyncFileSystemNode, str]]:
    """Traverse tree asynchronously.
    
    Args:
        root: Root path to traverse
        strategy: Traversal strategy ('bfs', 'dfs', 'dfs_post')
        max_depth: Maximum depth to traverse
        max_concurrent: Maximum concurrent I/O operations
        
    Yields:
        Tuples of (node, identifier)
    """
    plan = AsyncExecutionPlan(
        traversal_strategy=strategy,
        data_collector=AsyncDataCollector(AsyncFileSystemAdapter()),
        max_depth=max_depth,
        max_concurrent=max_concurrent
    )
    
    async for node, data in plan.execute_async(root):
        yield node, data


async def collect_metadata_async(root: Path,
                                strategy: str = 'bfs',
                                max_depth: Optional[int] = None,
                                max_concurrent: int = 100) -> AsyncIterator[Tuple[AsyncFileSystemNode, dict]]:
    """Collect metadata for all nodes asynchronously.
    
    Args:
        root: Root path to traverse
        strategy: Traversal strategy
        max_depth: Maximum depth
        max_concurrent: Maximum concurrent operations
        
    Yields:
        Tuples of (node, metadata_dict)
    """
    plan = AsyncExecutionPlan(
        traversal_strategy=strategy,
        data_collector=AsyncMetadataCollector(AsyncFileSystemAdapter()),
        max_depth=max_depth,
        max_concurrent=max_concurrent
    )
    
    async for node, metadata in plan.execute_async(root):
        yield node, metadata


async def parallel_traverse(roots: List[Path],
                           strategy: str = 'bfs',
                           max_depth: Optional[int] = None) -> AsyncIterator[Tuple[Path, List[Tuple]]]:
    """Traverse multiple trees in parallel.
    
    Args:
        roots: List of root paths
        strategy: Traversal strategy
        max_depth: Maximum depth
        
    Yields:
        Tuples of (root_path, results_list)
    """
    async def traverse_one(root):
        results = []
        async for node, data in traverse_tree_async(root, strategy, max_depth):
            results.append((node, data))
        return root, results
    
    tasks = [traverse_one(root) for root in roots]
    
    for coro in asyncio.as_completed(tasks):
        root, results = await coro
        yield root, results


async def find_files_async(root: Path,
                          pattern: str = '*',
                          max_concurrent: int = 100) -> List[Path]:
    """Find files matching pattern asynchronously.
    
    Args:
        root: Root path to search
        pattern: Glob pattern to match
        max_concurrent: Maximum concurrent operations
        
    Returns:
        List of matching file paths
    """
    from fnmatch import fnmatch
    
    matching_files = []
    
    async for node, metadata in collect_metadata_async(root, max_concurrent=max_concurrent):
        if metadata.get('is_file') and fnmatch(node.path.name, pattern):
            matching_files.append(node.path)
    
    return matching_files


async def calculate_size_async(root: Path, max_concurrent: int = 100) -> int:
    """Calculate total size of directory tree asynchronously.
    
    Args:
        root: Root directory
        max_concurrent: Maximum concurrent operations
        
    Returns:
        Total size in bytes
    """
    total_size = 0
    
    async for node, metadata in collect_metadata_async(root, max_concurrent=max_concurrent):
        if metadata.get('is_file'):
            total_size += metadata.get('size', 0)
    
    return total_size