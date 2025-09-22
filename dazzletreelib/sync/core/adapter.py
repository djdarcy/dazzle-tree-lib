"""TreeAdapter abstraction for DazzleTreeLib.

The TreeAdapter is the KEY innovation that makes DazzleTreeLib universal.
It provides the navigation logic for specific tree structures, decoupling
the node representation from the traversal mechanism.
"""

from abc import ABC, abstractmethod
from typing import Iterator, Optional, AsyncIterator
from .node import TreeNode


class TreeAdapter(ABC):
    """Abstract adapter for navigating specific types of tree structures.
    
    The TreeAdapter pattern is what makes DazzleTreeLib work with ANY tree
    structure. While TreeNode is just a data container, the adapter knows
    HOW to navigate the specific tree type.
    
    This separation allows:
    - The same node type to be traversed differently
    - Different node types to be traversed uniformly
    - Tree-specific optimizations without changing the core library
    - Support for both sync and async operations
    """
    
    @abstractmethod
    def get_children(self, node: TreeNode) -> Iterator[TreeNode]:
        """Get an iterator of child nodes for the given node.
        
        This method should be lazy when possible - return an iterator
        that yields children on demand rather than materializing all
        children at once.
        
        Args:
            node: The parent node
            
        Returns:
            Iterator yielding child TreeNode instances
            
        Example:
            for child in adapter.get_children(parent_node):
                process(child)
        """
        pass
    
    @abstractmethod
    def get_parent(self, node: TreeNode) -> Optional[TreeNode]:
        """Get the parent node of the given node.
        
        Args:
            node: The child node
            
        Returns:
            Parent TreeNode or None if node is root
        """
        pass
    
    def get_depth(self, node: TreeNode) -> int:
        """Calculate the depth of a node in the tree.
        
        Default implementation walks up to root.
        Adapters can override for more efficient implementations.
        
        Args:
            node: The node to get depth for
            
        Returns:
            Depth where root = 0
        """
        depth = 0
        current = node
        while True:
            parent = self.get_parent(current)
            if parent is None:
                break
            depth += 1
            current = parent
        return depth
    
    def get_siblings(self, node: TreeNode) -> Iterator[TreeNode]:
        """Get siblings of the given node (excluding the node itself).
        
        Default implementation uses parent's children.
        
        Args:
            node: The node to get siblings for
            
        Returns:
            Iterator yielding sibling TreeNode instances
        """
        parent = self.get_parent(node)
        if parent is None:
            return iter([])  # Root has no siblings
        
        node_id = node.identifier()
        for child in self.get_children(parent):
            if child.identifier() != node_id:
                yield child
    
    # Capability flags - adapters declare what they support
    
    def supports_full_data(self) -> bool:
        """Check if adapter can provide complete node data.
        
        Some adapters might only provide metadata without full content.
        
        Returns:
            True if full data access is supported
        """
        return True
    
    def supports_async(self) -> bool:
        """Check if adapter supports async operations.
        
        Returns:
            True if async methods are implemented
        """
        return False
    
    def supports_random_access(self) -> bool:
        """Check if adapter supports jumping to arbitrary nodes.
        
        Some tree structures (like streaming XML) only support
        sequential access.
        
        Returns:
            True if random access is supported
        """
        return True
    
    def supports_modification(self) -> bool:
        """Check if adapter supports modifying the tree structure.
        
        Returns:
            True if tree modification is supported
        """
        return False
    
    def estimated_size(self, node: TreeNode) -> Optional[int]:
        """Estimate the number of nodes in the subtree.
        
        Used for memory management and progress reporting.
        Return None if estimation is not possible.
        
        Args:
            node: Root of subtree to estimate
            
        Returns:
            Estimated node count or None
        """
        return None
    
    # Async methods - only required if supports_async() returns True
    
    async def get_children_async(self, node: TreeNode) -> AsyncIterator[TreeNode]:
        """Async version of get_children.
        
        Default implementation wraps the sync version.
        Override for true async I/O operations.
        
        Args:
            node: The parent node
            
        Returns:
            Async iterator yielding child TreeNode instances
        """
        for child in self.get_children(node):
            yield child
    
    async def get_parent_async(self, node: TreeNode) -> Optional[TreeNode]:
        """Async version of get_parent.
        
        Args:
            node: The child node
            
        Returns:
            Parent TreeNode or None if node is root
        """
        return self.get_parent(node)
    
    # Tree modification methods - only required if supports_modification() returns True
    
    def add_child(self, parent: TreeNode, child: TreeNode) -> None:
        """Add a child node to a parent.
        
        Args:
            parent: The parent node
            child: The child node to add
            
        Raises:
            NotImplementedError: If modification not supported
        """
        raise NotImplementedError(f"{self.__class__.__name__} does not support modification")
    
    def remove_child(self, parent: TreeNode, child: TreeNode) -> None:
        """Remove a child node from a parent.
        
        Args:
            parent: The parent node
            child: The child node to remove
            
        Raises:
            NotImplementedError: If modification not supported
        """
        raise NotImplementedError(f"{self.__class__.__name__} does not support modification")
    
    def move_node(self, node: TreeNode, new_parent: TreeNode) -> None:
        """Move a node to a new parent.
        
        Args:
            node: The node to move
            new_parent: The new parent node
            
        Raises:
            NotImplementedError: If modification not supported
        """
        raise NotImplementedError(f"{self.__class__.__name__} does not support modification")