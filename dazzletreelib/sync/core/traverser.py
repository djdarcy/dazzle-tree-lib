"""Tree traversal strategies for DazzleTreeLib.

Traversers implement different algorithms for walking through trees.
They work with any TreeAdapter, making them universal across tree types.
"""

from abc import ABC, abstractmethod
from typing import Iterator, Optional, Set, Deque, List, Tuple
from collections import deque
from .node import TreeNode
from .adapter import TreeAdapter


class TreeTraverser(ABC):
    """Abstract base class for tree traversal strategies.
    
    Traversers implement the algorithms for walking through trees in
    different orders (breadth-first, depth-first, etc.). They are
    independent of the tree structure, working through the TreeAdapter.
    """
    
    def __init__(self, adapter: TreeAdapter):
        """Initialize traverser with an adapter.
        
        Args:
            adapter: TreeAdapter for navigating the tree
        """
        self.adapter = adapter
    
    @abstractmethod
    def traverse(self, 
                 root: TreeNode,
                 max_depth: Optional[int] = None,
                 min_depth: int = 0) -> Iterator[Tuple[TreeNode, int]]:
        """Traverse the tree starting from root.
        
        Args:
            root: Starting node for traversal
            max_depth: Maximum depth to traverse (None = unlimited)
            min_depth: Minimum depth before yielding nodes
            
        Yields:
            Tuples of (node, depth) where depth is relative to root
        """
        pass
    
    def _should_yield(self, depth: int, min_depth: int, max_depth: Optional[int]) -> bool:
        """Check if a node at given depth should be yielded.
        
        Args:
            depth: Current depth
            min_depth: Minimum depth for yielding
            max_depth: Maximum depth for yielding
            
        Returns:
            True if node should be yielded
        """
        if depth < min_depth:
            return False
        if max_depth is not None and depth > max_depth:
            return False
        return True
    
    def _should_explore(self, depth: int, max_depth: Optional[int]) -> bool:
        """Check if children of node at given depth should be explored.
        
        Args:
            depth: Current depth
            max_depth: Maximum depth limit
            
        Returns:
            True if children should be explored
        """
        if max_depth is None:
            return True
        return depth < max_depth


class BreadthFirstTraverser(TreeTraverser):
    """Breadth-first (level-order) traversal strategy.
    
    Visits all nodes at depth N before visiting nodes at depth N+1.
    Good for finding shortest paths and exploring nearby nodes first.
    """
    
    def traverse(self,
                 root: TreeNode,
                 max_depth: Optional[int] = None,
                 min_depth: int = 0) -> Iterator[Tuple[TreeNode, int]]:
        """Traverse tree breadth-first.
        
        Uses a queue to ensure level-order traversal.
        """
        # Queue stores (node, depth) tuples
        queue: Deque[Tuple[TreeNode, int]] = deque([(root, 0)])
        visited: Set[str] = set()
        
        while queue:
            node, depth = queue.popleft()
            
            # Skip if already visited (handles cycles)
            node_id = node.identifier()
            if node_id in visited:
                continue
            visited.add(node_id)
            
            # Yield if within depth range
            if self._should_yield(depth, min_depth, max_depth):
                yield (node, depth)
            
            # Add children to queue if we should explore deeper
            if self._should_explore(depth, max_depth) and not node.is_leaf():
                for child in self.adapter.get_children(node):
                    queue.append((child, depth + 1))


class DepthFirstPreOrderTraverser(TreeTraverser):
    """Depth-first pre-order traversal strategy.
    
    Visits parent before children. Processes nodes as soon as they're
    discovered. Good for copying trees or prefix notation.
    """
    
    def traverse(self,
                 root: TreeNode,
                 max_depth: Optional[int] = None,
                 min_depth: int = 0) -> Iterator[Tuple[TreeNode, int]]:
        """Traverse tree depth-first, pre-order.
        
        Uses recursion (via generator) for natural depth-first behavior.
        """
        visited: Set[str] = set()
        
        def _traverse_recursive(node: TreeNode, depth: int) -> Iterator[Tuple[TreeNode, int]]:
            # Skip if already visited
            node_id = node.identifier()
            if node_id in visited:
                return
            visited.add(node_id)
            
            # Yield parent first (pre-order)
            if self._should_yield(depth, min_depth, max_depth):
                yield (node, depth)
            
            # Then traverse children
            if self._should_explore(depth, max_depth) and not node.is_leaf():
                for child in self.adapter.get_children(node):
                    yield from _traverse_recursive(child, depth + 1)
        
        yield from _traverse_recursive(root, 0)


class DepthFirstPostOrderTraverser(TreeTraverser):
    """Depth-first post-order traversal strategy.
    
    Visits children before parent. Processes nodes after their entire
    subtree has been processed. Good for deletion or calculating
    aggregate values (like folder sizes).
    """
    
    def traverse(self,
                 root: TreeNode,
                 max_depth: Optional[int] = None,
                 min_depth: int = 0) -> Iterator[Tuple[TreeNode, int]]:
        """Traverse tree depth-first, post-order.
        
        Yields parent after all children have been yielded.
        """
        visited: Set[str] = set()
        
        def _traverse_recursive(node: TreeNode, depth: int) -> Iterator[Tuple[TreeNode, int]]:
            # Skip if already visited
            node_id = node.identifier()
            if node_id in visited:
                return
            visited.add(node_id)
            
            # First traverse children
            if self._should_explore(depth, max_depth) and not node.is_leaf():
                for child in self.adapter.get_children(node):
                    yield from _traverse_recursive(child, depth + 1)
            
            # Then yield parent (post-order)
            if self._should_yield(depth, min_depth, max_depth):
                yield (node, depth)
        
        yield from _traverse_recursive(root, 0)


class LevelOrderTraverser(TreeTraverser):
    """Level-order traversal with level grouping.
    
    Similar to breadth-first but yields nodes grouped by level.
    Useful when you need to process all nodes at a depth together.
    """
    
    def traverse(self,
                 root: TreeNode,
                 max_depth: Optional[int] = None,
                 min_depth: int = 0) -> Iterator[Tuple[TreeNode, int]]:
        """Traverse tree level by level.
        
        Note: This still yields individual nodes, but ensures
        complete level processing before moving to next level.
        """
        current_level: List[TreeNode] = [root]
        current_depth = 0
        visited: Set[str] = set()
        
        while current_level and (max_depth is None or current_depth <= max_depth):
            next_level: List[TreeNode] = []
            
            # Process all nodes at current level
            for node in current_level:
                node_id = node.identifier()
                if node_id in visited:
                    continue
                visited.add(node_id)
                
                # Yield if within depth range
                if self._should_yield(current_depth, min_depth, max_depth):
                    yield (node, current_depth)
                
                # Collect children for next level
                if self._should_explore(current_depth, max_depth) and not node.is_leaf():
                    for child in self.adapter.get_children(node):
                        next_level.append(child)
            
            current_level = next_level
            current_depth += 1


# Factory function for creating traversers by name
def create_traverser(strategy: str, adapter: TreeAdapter) -> TreeTraverser:
    """Create a traverser instance by strategy name.
    
    Args:
        strategy: Name of traversal strategy (bfs, dfs_pre, dfs_post, level)
        adapter: TreeAdapter for the tree structure
        
    Returns:
        TreeTraverser instance
        
    Raises:
        ValueError: If strategy name is not recognized
    """
    strategies = {
        'bfs': BreadthFirstTraverser,
        'breadth_first': BreadthFirstTraverser,
        'dfs_pre': DepthFirstPreOrderTraverser,
        'depth_first_pre': DepthFirstPreOrderTraverser,
        'dfs_post': DepthFirstPostOrderTraverser,
        'depth_first_post': DepthFirstPostOrderTraverser,
        'level': LevelOrderTraverser,
        'level_order': LevelOrderTraverser,
    }
    
    strategy_lower = strategy.lower()
    if strategy_lower not in strategies:
        raise ValueError(
            f"Unknown traversal strategy: {strategy}. "
            f"Choose from: {', '.join(strategies.keys())}"
        )
    
    return strategies[strategy_lower](adapter)