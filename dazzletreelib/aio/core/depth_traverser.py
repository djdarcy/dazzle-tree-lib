"""Depth-aware tree traversal for async operations.

This module provides traversers that expose depth information
during traversal, enabling efficient depth-based operations.
"""

import asyncio
from collections import deque
from typing import AsyncIterator, Any, Optional, Set, Tuple
from .traverser import AsyncTreeTraverser
from ..config import DepthConfig


class AsyncDepthTrackingTraverser(AsyncTreeTraverser):
    """Base class for traversers that track and expose depth information.
    
    This traverser yields (node, depth) tuples instead of just nodes,
    allowing consumers to access depth information with O(1) complexity
    during traversal.
    """
    
    async def traverse_with_depth(
        self,
        root: Any,
        adapter: Any,
        start_depth: int = 0,
        max_depth: Optional[int] = None
    ) -> AsyncIterator[Tuple[Any, int]]:
        """Traverse tree yielding (node, depth) tuples.
        
        Args:
            root: Starting node
            adapter: Tree adapter for navigating structure
            start_depth: Initial depth value (default 0)
            max_depth: Maximum depth to traverse
            
        Yields:
            Tuples of (node, depth) in traversal order
        """
        raise NotImplementedError("Subclasses must implement traverse_with_depth")


class AsyncBreadthFirstDepthTraverser(AsyncDepthTrackingTraverser):
    """Breadth-first traversal with depth tracking.
    
    Visits all nodes at depth N before visiting nodes at depth N+1,
    yielding (node, depth) tuples for efficient depth-based operations.
    """
    
    async def traverse_with_depth(
        self,
        root: Any,
        adapter: Any,
        start_depth: int = 0,
        max_depth: Optional[int] = None
    ) -> AsyncIterator[Tuple[Any, int]]:
        """Traverse tree breadth-first with depth information.
        
        Uses a queue to process nodes level by level, tracking depth
        as traversal progresses. Each yielded item is a (node, depth) tuple.
        """
        if max_depth is not None:
            self.depth_config.max_depth = max_depth
        
        # Queue stores (node, depth) tuples
        queue = deque([(root, start_depth)])
        visited: Set[str] = set()
        
        while queue:
            node, depth = queue.popleft()
            
            # Check if already visited (for graphs with cycles)
            node_id = await node.identifier() if hasattr(node, 'identifier') else str(node)
            if node_id in visited:
                continue
            visited.add(node_id)
            
            # Yield (node, depth) tuple if depth is in range
            if self.should_yield(depth):
                yield (node, depth)
            
            # Explore children if within depth limit
            if self.should_explore(depth) and not (hasattr(node, 'is_leaf') and node.is_leaf()):
                # Fetch children asynchronously
                async for child in adapter.get_children(node):
                    if await adapter.is_valid(child):
                        queue.append((child, depth + 1))
    
    # Override base traverse to delegate to traverse_with_depth
    async def traverse(
        self,
        root: Any,
        adapter: Any,
        max_depth: Optional[int] = None
    ) -> AsyncIterator[Any]:
        """Standard traverse that yields only nodes (for compatibility)."""
        async for node, _ in self.traverse_with_depth(root, adapter, 0, max_depth):
            yield node


class AsyncDepthFirstDepthTraverser(AsyncDepthTrackingTraverser):
    """Depth-first traversal with depth tracking.
    
    Explores as far as possible along each branch before backtracking,
    yielding (node, depth) tuples for efficient depth-based operations.
    """
    
    def __init__(
        self,
        depth_config: Optional[DepthConfig] = None,
        pre_order: bool = True
    ):
        """Initialize depth-first traverser with depth tracking.
        
        Args:
            depth_config: Configuration for depth-based filtering
            pre_order: If True, yield parent before children (pre-order).
                      If False, yield children before parent (post-order).
        """
        super().__init__(depth_config)
        self.pre_order = pre_order
    
    async def traverse_with_depth(
        self,
        root: Any,
        adapter: Any,
        start_depth: int = 0,
        max_depth: Optional[int] = None
    ) -> AsyncIterator[Tuple[Any, int]]:
        """Traverse tree depth-first with depth information.
        
        Uses recursion (via async generator) to explore branches deeply,
        tracking depth as traversal progresses. Each yielded item is a
        (node, depth) tuple.
        """
        if max_depth is not None:
            self.depth_config.max_depth = max_depth
        
        visited: Set[str] = set()
        
        async def _traverse_recursive(node: Any, depth: int):
            """Recursive helper for depth-first traversal."""
            # Check if already visited
            node_id = await node.identifier() if hasattr(node, 'identifier') else str(node)
            if node_id in visited:
                return
            visited.add(node_id)
            
            # Pre-order: yield before children
            if self.pre_order and self.should_yield(depth):
                yield (node, depth)
            
            # Explore children if within depth limit
            if self.should_explore(depth) and not (hasattr(node, 'is_leaf') and node.is_leaf()):
                async for child in adapter.get_children(node):
                    if await adapter.is_valid(child):
                        async for item in _traverse_recursive(child, depth + 1):
                            yield item
            
            # Post-order: yield after children
            if not self.pre_order and self.should_yield(depth):
                yield (node, depth)
        
        # Start traversal from root
        async for item in _traverse_recursive(root, start_depth):
            yield item
    
    # Override base traverse to delegate to traverse_with_depth
    async def traverse(
        self,
        root: Any,
        adapter: Any,
        max_depth: Optional[int] = None
    ) -> AsyncIterator[Any]:
        """Standard traverse that yields only nodes (for compatibility)."""
        async for node, _ in self.traverse_with_depth(root, adapter, 0, max_depth):
            yield node


class AsyncLevelOrderDepthTraverser(AsyncBreadthFirstDepthTraverser):
    """Level-order traversal that groups nodes by depth.
    
    This is a specialized BFS traverser that can optionally
    yield all nodes at a given depth together as a batch.
    """
    
    async def traverse_by_level(
        self,
        root: Any,
        adapter: Any,
        start_depth: int = 0,
        max_depth: Optional[int] = None
    ) -> AsyncIterator[Tuple[int, list]]:
        """Traverse tree yielding all nodes at each depth as a batch.
        
        Args:
            root: Starting node
            adapter: Tree adapter for navigating structure
            start_depth: Initial depth value
            max_depth: Maximum depth to traverse
            
        Yields:
            Tuples of (depth, [nodes at that depth])
        """
        if max_depth is not None:
            self.depth_config.max_depth = max_depth
        
        current_depth = start_depth
        current_level = [root]
        visited: Set[str] = set()
        
        while current_level and (max_depth is None or current_depth <= max_depth):
            # Yield current level if within range
            if self.should_yield(current_depth):
                yield (current_depth, current_level)
            
            # Prepare next level
            next_level = []
            
            # Process all nodes at current level
            for node in current_level:
                node_id = await node.identifier() if hasattr(node, 'identifier') else str(node)
                if node_id in visited:
                    continue
                visited.add(node_id)
                
                # Get children for next level
                if self.should_explore(current_depth) and not (hasattr(node, 'is_leaf') and node.is_leaf()):
                    async for child in adapter.get_children(node):
                        if await adapter.is_valid(child):
                            next_level.append(child)
            
            current_level = next_level
            current_depth += 1


# Convenience function for creating depth traversers
def create_depth_traverser(
    strategy: str = 'bfs',
    depth_config: Optional[DepthConfig] = None,
    **kwargs
) -> AsyncDepthTrackingTraverser:
    """Create a depth-tracking traverser with the specified strategy.
    
    Args:
        strategy: Traversal strategy ('bfs', 'dfs', 'dfs_post', 'level')
        depth_config: Optional depth configuration
        **kwargs: Additional arguments for specific traverser types
        
    Returns:
        An appropriate depth-tracking traverser instance
        
    Raises:
        ValueError: If strategy is unknown
    """
    if strategy == 'bfs':
        return AsyncBreadthFirstDepthTraverser(depth_config)
    elif strategy == 'dfs':
        return AsyncDepthFirstDepthTraverser(depth_config, pre_order=True)
    elif strategy == 'dfs_post':
        return AsyncDepthFirstDepthTraverser(depth_config, pre_order=False)
    elif strategy == 'level':
        return AsyncLevelOrderDepthTraverser(depth_config)
    else:
        raise ValueError(f"Unknown traversal strategy: {strategy}")