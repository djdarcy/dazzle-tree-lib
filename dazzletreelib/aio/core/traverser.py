"""Async tree traversal strategies.

Implements various traversal patterns using async/await.
All traversers yield nodes as AsyncIterators for streaming.
"""

import asyncio
from abc import ABC, abstractmethod
from collections import deque
from typing import AsyncIterator, Any, Optional, Set
from ..config import DepthConfig


class AsyncTreeTraverser(ABC):
    """Abstract base class for async tree traversers.
    
    Traversers implement different strategies for walking through
    a tree structure. All async traversers stream nodes using
    AsyncIterator for memory efficiency.
    """
    
    def __init__(self, depth_config: Optional[DepthConfig] = None):
        """Initialize traverser with optional depth configuration.
        
        Args:
            depth_config: Configuration for depth-based filtering
        """
        self.depth_config = depth_config or DepthConfig()
    
    @abstractmethod
    async def traverse(
        self,
        root: Any,
        adapter: Any,
        max_depth: Optional[int] = None
    ) -> AsyncIterator[Any]:
        """Traverse tree starting from root.
        
        Args:
            root: Starting node
            adapter: Tree adapter for navigating structure
            max_depth: Maximum depth to traverse (overrides config)
            
        Yields:
            Nodes in traversal order
        """
        pass
    
    def should_yield(self, depth: int) -> bool:
        """Check if nodes at this depth should be yielded.
        
        Args:
            depth: Current depth
            
        Returns:
            True if node should be yielded
        """
        return self.depth_config.should_yield(depth)
    
    def should_explore(self, depth: int) -> bool:
        """Check if children at this depth should be explored.
        
        Args:
            depth: Current depth
            
        Returns:
            True if children should be explored
        """
        return self.depth_config.should_explore(depth)


class AsyncBreadthFirstTraverser(AsyncTreeTraverser):
    """Async breadth-first (level-order) traversal.
    
    Visits all nodes at depth N before visiting nodes at depth N+1.
    Good for finding shortest paths and exploring tree level by level.
    """
    
    async def traverse(
        self,
        root: Any,
        adapter: Any,
        max_depth: Optional[int] = None
    ) -> AsyncIterator[Any]:
        """Traverse tree breadth-first with streaming.
        
        Uses a queue to process nodes level by level.
        Children are fetched asynchronously and in parallel.
        """
        if max_depth is not None:
            self.depth_config.max_depth = max_depth
        
        # Queue stores (node, depth) tuples
        queue = deque([(root, 0)])
        visited: Set[str] = set()
        
        while queue:
            node, depth = queue.popleft()
            
            # Check if already visited (for graphs with cycles)
            node_id = await node.identifier() if hasattr(node, 'identifier') else str(node)
            if node_id in visited:
                continue
            visited.add(node_id)
            
            # Yield if depth is in range
            if self.should_yield(depth):
                yield node
            
            # Explore children if within depth limit
            if self.should_explore(depth) and not (hasattr(node, 'is_leaf') and node.is_leaf()):
                # Fetch children asynchronously
                async for child in adapter.get_children(node):
                    if await adapter.is_valid(child):
                        queue.append((child, depth + 1))


class AsyncDepthFirstTraverser(AsyncTreeTraverser):
    """Async depth-first traversal.
    
    Explores as far as possible along each branch before backtracking.
    Memory efficient for deep trees.
    """
    
    def __init__(
        self,
        depth_config: Optional[DepthConfig] = None,
        pre_order: bool = True
    ):
        """Initialize depth-first traverser.
        
        Args:
            depth_config: Configuration for depth-based filtering
            pre_order: If True, yield parent before children (pre-order).
                      If False, yield children before parent (post-order).
        """
        super().__init__(depth_config)
        self.pre_order = pre_order
    
    async def traverse(
        self,
        root: Any,
        adapter: Any,
        max_depth: Optional[int] = None
    ) -> AsyncIterator[Any]:
        """Traverse tree depth-first with streaming.
        
        Uses recursion with async generators for elegant streaming.
        """
        if max_depth is not None:
            self.depth_config.max_depth = max_depth
        
        visited: Set[str] = set()
        
        async def dfs(node: Any, depth: int) -> AsyncIterator[Any]:
            """Recursive depth-first search."""
            # Check if already visited
            node_id = await node.identifier() if hasattr(node, 'identifier') else str(node)
            if node_id in visited:
                return
            visited.add(node_id)
            
            # Pre-order: yield before children
            if self.pre_order and self.should_yield(depth):
                yield node
            
            # Explore children if within depth limit
            if self.should_explore(depth) and not (hasattr(node, 'is_leaf') and node.is_leaf()):
                async for child in adapter.get_children(node):
                    if await adapter.is_valid(child):
                        async for descendant in dfs(child, depth + 1):
                            yield descendant
            
            # Post-order: yield after children
            if not self.pre_order and self.should_yield(depth):
                yield node
        
        async for node in dfs(root, 0):
            yield node


class AsyncParallelBreadthFirstTraverser(AsyncTreeTraverser):
    """Async breadth-first traversal with parallel child fetching.
    
    Fetches all children at each level in parallel for maximum speed.
    Best for I/O-bound operations where parallelism helps.
    """
    
    async def traverse(
        self,
        root: Any,
        adapter: Any,
        max_depth: Optional[int] = None
    ) -> AsyncIterator[Any]:
        """Traverse tree with parallel child fetching at each level."""
        if max_depth is not None:
            self.depth_config.max_depth = max_depth
        
        current_level = [root]
        current_depth = 0
        visited: Set[str] = set()
        
        while current_level:
            # Yield all nodes at current level
            for node in current_level:
                node_id = await node.identifier() if hasattr(node, 'identifier') else str(node)
                if node_id not in visited:
                    visited.add(node_id)
                    if self.should_yield(current_depth):
                        yield node
            
            # Check if we should explore next level
            if not self.should_explore(current_depth):
                break
            
            # Fetch all children in parallel
            next_level = []
            
            async def fetch_children(node):
                """Fetch children of a single node."""
                if hasattr(node, 'is_leaf') and node.is_leaf():
                    return []
                children = []
                async for child in adapter.get_children(node):
                    if await adapter.is_valid(child):
                        children.append(child)
                return children
            
            # Create tasks for all nodes at current level
            tasks = [fetch_children(node) for node in current_level 
                    if not (hasattr(node, 'is_leaf') and node.is_leaf())]
            
            if tasks:
                # Wait for all children to be fetched
                children_lists = await asyncio.gather(*tasks)
                
                # Flatten the list of lists
                for children in children_lists:
                    next_level.extend(children)
            
            current_level = next_level
            current_depth += 1