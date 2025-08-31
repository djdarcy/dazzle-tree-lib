"""High-level async API for DazzleTreeLib.

This module provides simple, user-friendly async functions for common
tree traversal operations. All functions use the new structured modules.
"""

import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional, AsyncIterator, Set

from .core import (
    AsyncBreadthFirstTraverser,
    AsyncDepthFirstTraverser,
    AsyncMetadataCollector,
    AsyncPathCollector,
)
from .core.collector import (
    AsyncSizeCollector,
    AsyncFilterCollector,
)
from .adapters import (
    AsyncFileSystemNode,
    AsyncFileSystemAdapter,
    AsyncFilteredFileSystemAdapter,
)
from .adapters.fast_filesystem import (
    FastAsyncFileSystemAdapter,
    FastAsyncFileSystemNode,
)


async def traverse_tree_async(
    root: Path,
    strategy: str = 'bfs',
    max_depth: Optional[int] = None,
    max_concurrent: int = 100,
    batch_size: int = 256,
    use_stat_cache: bool = True,
    use_fast_adapter: bool = True
) -> AsyncIterator[AsyncFileSystemNode]:
    """Traverse a filesystem tree asynchronously.
    
    Args:
        root: Root directory to traverse
        strategy: Traversal strategy ('bfs' or 'dfs')
        max_depth: Maximum depth to traverse
        max_concurrent: Maximum concurrent I/O operations
        batch_size: Number of children to process in parallel
        use_stat_cache: Use stat caching for better performance
        use_fast_adapter: Use fast scandir-based adapter (default: True)
        
    Yields:
        AsyncFileSystemNode objects in traversal order
    """
    # Use fast adapter by default for better performance
    if use_fast_adapter:
        adapter = FastAsyncFileSystemAdapter()
        root_node = FastAsyncFileSystemNode(root)
    else:
        adapter = AsyncFileSystemAdapter(
            max_concurrent=max_concurrent,
            batch_size=batch_size,
            use_stat_cache=use_stat_cache
        )
        root_node = AsyncFileSystemNode(root, adapter.stat_cache)
    
    if strategy == 'bfs':
        traverser = AsyncBreadthFirstTraverser()
    elif strategy == 'dfs':
        traverser = AsyncDepthFirstTraverser(pre_order=True)
    elif strategy == 'dfs_post':
        traverser = AsyncDepthFirstTraverser(pre_order=False)
    else:
        raise ValueError(f"Unknown strategy: {strategy}")
    
    async for node in traverser.traverse(root_node, adapter, max_depth):
        yield node


async def collect_metadata_async(
    root: Path,
    max_depth: Optional[int] = None,
    max_concurrent: int = 100
) -> List[Dict[str, Any]]:
    """Collect metadata from all nodes in a tree.
    
    Args:
        root: Root directory
        max_depth: Maximum depth to traverse
        max_concurrent: Maximum concurrent I/O operations
        
    Returns:
        List of metadata dictionaries for all nodes
    """
    collector = AsyncMetadataCollector()
    metadata_list = []
    
    async for node in traverse_tree_async(root, 'bfs', max_depth, max_concurrent):
        metadata = await collector.collect(node)
        metadata_list.append(metadata)
    
    return metadata_list


async def get_tree_paths_async(
    root: Path,
    max_depth: Optional[int] = None,
    max_concurrent: int = 100
) -> List[str]:
    """Get all paths in a tree.
    
    Args:
        root: Root directory
        max_depth: Maximum depth to traverse
        max_concurrent: Maximum concurrent I/O operations
        
    Returns:
        List of path strings
    """
    collector = AsyncPathCollector()
    
    async for node in traverse_tree_async(root, 'bfs', max_depth, max_concurrent):
        depth = 0  # TODO: Calculate actual depth
        await collector.collect(node, depth)
    
    return collector.get_result()


async def calculate_size_async(
    root: Path,
    max_concurrent: int = 100
) -> Dict[str, Any]:
    """Calculate total size of a directory tree.
    
    Args:
        root: Root directory
        max_concurrent: Maximum concurrent I/O operations
        
    Returns:
        Dictionary with size statistics
    """
    collector = AsyncSizeCollector()
    
    async for node in traverse_tree_async(root, 'bfs', None, max_concurrent):
        await collector.collect(node)
    
    return collector.get_result()


async def find_files_async(
    root: Path,
    pattern: str = '*',
    max_depth: Optional[int] = None,
    max_concurrent: int = 100
) -> List[Path]:
    """Find files matching a pattern.
    
    Args:
        root: Root directory to search
        pattern: Glob pattern to match
        max_depth: Maximum depth to search
        max_concurrent: Maximum concurrent I/O operations
        
    Returns:
        List of matching file paths
    """
    root_node = AsyncFileSystemNode(root)
    adapter = AsyncFilteredFileSystemAdapter(
        max_concurrent=max_concurrent,
        include_patterns=[pattern]
    )
    traverser = AsyncBreadthFirstTraverser()
    
    matching_files = []
    async for node in traverser.traverse(root_node, adapter, max_depth):
        if node.path.is_file():
            matching_files.append(node.path)
    
    return matching_files


async def find_directories_async(
    root: Path,
    pattern: str = '*',
    max_depth: Optional[int] = None,
    max_concurrent: int = 100
) -> List[Path]:
    """Find directories matching a pattern.
    
    Args:
        root: Root directory to search
        pattern: Glob pattern to match
        max_depth: Maximum depth to search
        max_concurrent: Maximum concurrent I/O operations
        
    Returns:
        List of matching directory paths
    """
    root_node = AsyncFileSystemNode(root)
    adapter = AsyncFilteredFileSystemAdapter(
        max_concurrent=max_concurrent,
        include_patterns=[pattern]
    )
    traverser = AsyncBreadthFirstTraverser()
    
    matching_dirs = []
    async for node in traverser.traverse(root_node, adapter, max_depth):
        if node.path.is_dir():
            matching_dirs.append(node.path)
    
    return matching_dirs


async def parallel_traverse(
    roots: List[Path],
    max_concurrent_per_tree: int = 100
) -> Dict[Path, List[Dict[str, Any]]]:
    """Traverse multiple trees in parallel.
    
    Args:
        roots: List of root directories
        max_concurrent_per_tree: Concurrent operations per tree
        
    Returns:
        Dictionary mapping each root to its metadata list
    """
    async def traverse_one(root: Path) -> List[Dict[str, Any]]:
        return await collect_metadata_async(root, max_concurrent=max_concurrent_per_tree)
    
    tasks = [traverse_one(root) for root in roots]
    results = await asyncio.gather(*tasks)
    
    return dict(zip(roots, results))


async def get_tree_stats_async(
    root: Path,
    max_concurrent: int = 100
) -> Dict[str, Any]:
    """Get comprehensive statistics about a tree.
    
    Args:
        root: Root directory
        max_concurrent: Maximum concurrent I/O operations
        
    Returns:
        Dictionary with tree statistics
    """
    stats = {
        'root': str(root),
        'total_size': 0,
        'file_count': 0,
        'dir_count': 0,
        'max_depth': 0,
        'extensions': set(),
        'largest_file': None,
        'largest_file_size': 0,
    }
    
    root_node = AsyncFileSystemNode(root)
    adapter = AsyncFileSystemAdapter(max_concurrent=max_concurrent)
    traverser = AsyncBreadthFirstTraverser()
    
    async for node in traverser.traverse(root_node, adapter):
        # Update counts
        if node.path.is_file():
            stats['file_count'] += 1
            
            # Get size
            size = await node.size()
            if size:
                stats['total_size'] += size
                
                # Track largest file
                if size > stats['largest_file_size']:
                    stats['largest_file'] = str(node.path)
                    stats['largest_file_size'] = size
            
            # Track extensions
            if node.path.suffix:
                stats['extensions'].add(node.path.suffix)
        else:
            stats['dir_count'] += 1
        
        # Track depth
        depth = await adapter.get_depth(node)
        stats['max_depth'] = max(stats['max_depth'], depth)
    
    # Convert set to list for JSON serialization
    stats['extensions'] = sorted(list(stats['extensions']))
    
    return stats


async def filter_tree_async(
    root: Path,
    predicate,
    max_depth: Optional[int] = None,
    max_concurrent: int = 100
) -> List[Path]:
    """Filter tree nodes using a custom predicate.
    
    Args:
        root: Root directory
        predicate: Async or sync function that returns True for nodes to include
        max_depth: Maximum depth to traverse
        max_concurrent: Maximum concurrent I/O operations
        
    Returns:
        List of paths that match the predicate
    """
    collector = AsyncFilterCollector(predicate)
    
    async for node in traverse_tree_async(root, 'bfs', max_depth, max_concurrent):
        await collector.collect(node, 0)
    
    # Extract paths from collected nodes
    matching_paths = []
    for node in collector.get_result():
        if hasattr(node, 'path'):
            matching_paths.append(node.path)
        else:
            matching_paths.append(Path(await node.identifier()))
    
    return matching_paths


async def count_nodes_async(
    root: Path,
    max_depth: Optional[int] = None,
    max_concurrent: int = 100
) -> int:
    """Count total nodes in a tree.
    
    Args:
        root: Root directory
        max_depth: Maximum depth to count
        max_concurrent: Maximum concurrent I/O operations
        
    Returns:
        Total number of nodes
    """
    count = 0
    async for _ in traverse_tree_async(root, 'bfs', max_depth, max_concurrent):
        count += 1
    return count


async def get_leaf_nodes_async(
    root: Path,
    max_depth: Optional[int] = None,
    max_concurrent: int = 100
) -> List[Path]:
    """Get all leaf nodes (files and empty directories).
    
    Args:
        root: Root directory
        max_depth: Maximum depth to search
        max_concurrent: Maximum concurrent I/O operations
        
    Returns:
        List of paths to leaf nodes
    """
    leaf_nodes = []
    
    async for node in traverse_tree_async(root, 'bfs', max_depth, max_concurrent):
        if node.is_leaf():
            leaf_nodes.append(node.path)
    
    return leaf_nodes