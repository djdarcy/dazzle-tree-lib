"""
Post-order (bottom-up) traversal for DazzleTreeLib.

This provides depth-first post-order traversal where children are processed
before their parents, which is needed for folder_datetime_fix's TreeStrategy.
"""

from typing import Any, Optional, AsyncIterator, Tuple, Set
from pathlib import Path
from ..core import AsyncTreeAdapter
from ..adapters.filesystem import AsyncFileSystemNode, AsyncFileSystemAdapter


async def traverse_post_order_with_depth(
    root: Any,
    adapter: Optional[AsyncTreeAdapter] = None,
    max_depth: Optional[int] = None,
    start_depth: int = 0,
    skip_errors: bool = True
) -> AsyncIterator[Tuple[Any, int]]:
    """
    Traverse tree in post-order (children before parents) with depth tracking.
    
    This is useful for operations that need to process leaves first,
    like calculating folder timestamps from their contents.
    
    Args:
        root: Root node to start traversal
        adapter: Tree adapter (defaults to AsyncFileSystemAdapter)
        max_depth: Maximum depth to traverse (None = unlimited)
        start_depth: Starting depth value
        skip_errors: Whether to skip nodes that cause errors
        
    Yields:
        Tuples of (node, depth) in post-order
    """
    if adapter is None:
        if isinstance(root, Path):
            root = AsyncFileSystemNode(root)
        adapter = AsyncFileSystemAdapter()
    
    visited: Set[str] = set()
    
    async def _traverse_post_order(node: Any, depth: int) -> AsyncIterator[Tuple[Any, int]]:
        """Recursive post-order traversal."""
        # Get node identifier for cycle detection
        node_id = str(node.path) if hasattr(node, 'path') else str(node)
        
        # Check for cycles
        if node_id in visited:
            return
        visited.add(node_id)
        
        # Check depth limit
        if max_depth is not None and depth > max_depth:
            return
        
        # First, recursively yield all children
        if not adapter.is_leaf(node):
            try:
                async for child in adapter.get_children(node):
                    async for child_node, child_depth in _traverse_post_order(child, depth + 1):
                        yield child_node, child_depth
            except Exception as e:
                if not skip_errors:
                    raise
                # Skip this node's children on error
        
        # Then yield the node itself (post-order)
        yield node, depth
    
    # Start traversal
    async for node, depth in _traverse_post_order(root, start_depth):
        yield node, depth


async def traverse_tree_bottom_up(
    root: Any,
    adapter: Optional[AsyncTreeAdapter] = None,
    max_depth: Optional[int] = None,
    process_directories_only: bool = False
) -> AsyncIterator[Any]:
    """
    Traverse tree bottom-up (leaves first, root last).
    
    This is a simplified interface for post-order traversal without depth.
    
    Args:
        root: Root node to start traversal
        adapter: Tree adapter (defaults to AsyncFileSystemAdapter)
        max_depth: Maximum depth to traverse
        process_directories_only: Only yield directory nodes
        
    Yields:
        Nodes in bottom-up order
    """
    async for node, depth in traverse_post_order_with_depth(
        root, adapter, max_depth
    ):
        if process_directories_only:
            if hasattr(node, 'path') and node.path.is_dir():
                yield node
        else:
            yield node


async def collect_by_level_bottom_up(
    root: Any,
    adapter: Optional[AsyncTreeAdapter] = None,
    max_depth: Optional[int] = None
) -> AsyncIterator[Tuple[int, list]]:
    """
    Collect nodes by level and yield levels in bottom-up order.
    
    This collects all nodes at each depth level, then yields levels
    starting from the deepest level up to the root.
    
    Args:
        root: Root node to start traversal
        adapter: Tree adapter
        max_depth: Maximum depth to traverse
        
    Yields:
        Tuples of (depth, [nodes at that depth]) from deepest to shallowest
    """
    # Collect all nodes by depth
    levels = {}
    
    async for node, depth in traverse_post_order_with_depth(
        root, adapter, max_depth
    ):
        if depth not in levels:
            levels[depth] = []
        levels[depth].append(node)
    
    # Yield levels from deepest to shallowest
    for depth in sorted(levels.keys(), reverse=True):
        yield depth, levels[depth]


# Convenience function for folder_datetime_fix TreeStrategy
async def process_folders_bottom_up(
    root: Path,
    processor_func,
    max_depth: Optional[int] = None,
    **kwargs
) -> list:
    """
    Process folders in bottom-up order with a given function.
    
    This is specifically designed for folder_datetime_fix's TreeStrategy
    where folders need to be processed from leaves to root so that
    parent timestamps can be calculated from already-processed children.
    
    Args:
        root: Root directory path
        processor_func: Async function to process each folder
        max_depth: Maximum depth to process
        **kwargs: Additional arguments for processor_func
        
    Returns:
        List of results from processor_func
    """
    results = []
    root_node = AsyncFileSystemNode(root)
    adapter = AsyncFileSystemAdapter()
    
    async for node in traverse_tree_bottom_up(
        root_node, 
        adapter, 
        max_depth,
        process_directories_only=True
    ):
        result = await processor_func(node.path, **kwargs)
        if result is not None:
            results.append(result)
    
    return results