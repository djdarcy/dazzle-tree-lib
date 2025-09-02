"""
Depth tracking adapter for O(1) depth calculation.

This adapter maintains depth information during traversal,
eliminating the need to recalculate depth by counting ancestors.
"""

from typing import Optional, Any, Dict
from pathlib import Path
from ..core import AsyncTreeAdapter


class DepthTrackingAdapter(AsyncTreeAdapter):
    """
    Adapter that tracks depth during traversal for O(1) depth queries.
    
    Instead of counting ancestors (O(depth)), this adapter maintains
    a depth map during traversal, providing instant depth lookups.
    """
    
    def __init__(self, base_adapter: AsyncTreeAdapter):
        """
        Initialize depth tracking adapter.
        
        Args:
            base_adapter: The underlying adapter to wrap
        """
        self.base_adapter = base_adapter
        self.depth_map: Dict[str, int] = {}
        self.current_root = None
    
    async def get_children(self, node: Any):
        """Get children and track their depth."""
        # Ensure we have depth for parent
        node_id = self._get_node_id(node)
        if node_id not in self.depth_map:
            # This is a root node
            self.depth_map[node_id] = 0
            self.current_root = node_id
        
        parent_depth = self.depth_map[node_id]
        
        # Get children and assign depths
        async for child in self.base_adapter.get_children(node):
            child_id = self._get_node_id(child)
            self.depth_map[child_id] = parent_depth + 1
            yield child
    
    async def get_parent(self, node: Any) -> Optional[Any]:
        """Pass through to base adapter."""
        return await self.base_adapter.get_parent(node)
    
    async def get_depth(self, node: Any) -> int:
        """
        Get depth with O(1) lookup from cache.
        
        Args:
            node: Node to check
            
        Returns:
            Depth (0 for root)
        """
        node_id = self._get_node_id(node)
        
        # Return cached depth if available
        if node_id in self.depth_map:
            return self.depth_map[node_id]
        
        # Fall back to base adapter if not in cache
        # This can happen if node wasn't reached via traversal
        return await self.base_adapter.get_depth(node)
    
    def is_leaf(self, node: Any) -> bool:
        """Pass through to base adapter."""
        return self.base_adapter.is_leaf(node)
    
    def _get_node_id(self, node: Any) -> str:
        """
        Get unique identifier for a node.
        
        Args:
            node: Node to identify
            
        Returns:
            Unique string identifier
        """
        if hasattr(node, 'path'):
            return str(node.path.absolute())
        elif hasattr(node, 'identifier'):
            return node.identifier()
        else:
            return str(id(node))
    
    def reset_depth_tracking(self):
        """Clear depth cache for new traversal."""
        self.depth_map.clear()
        self.current_root = None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get adapter statistics."""
        return {
            'nodes_tracked': len(self.depth_map),
            'current_root': self.current_root
        }