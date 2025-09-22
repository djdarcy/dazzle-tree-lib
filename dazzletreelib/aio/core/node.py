"""Async tree node abstraction.

Defines the interface for nodes in an async tree structure.
All I/O operations are async to support non-blocking execution.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class AsyncTreeNode(ABC):
    """Abstract base class for async tree nodes.
    
    This defines the minimal interface that any node in an async tree
    must implement. The key difference from sync TreeNode is that
    metadata access is async to allow for lazy loading.
    """
    
    @abstractmethod
    async def identifier(self) -> str:
        """Get unique identifier for this node.
        
        This should be async in case the identifier needs to be
        computed or fetched from an external source.
        
        Returns:
            Unique string identifier for the node
        """
        pass
    
    @abstractmethod
    async def metadata(self) -> Dict[str, Any]:
        """Get metadata for this node.
        
        Metadata might need to be fetched from disk, network, or
        computed on demand, so this is async.
        
        Returns:
            Dictionary of metadata key-value pairs
        """
        pass
    
    @abstractmethod
    def is_leaf(self) -> bool:
        """Check if this node is a leaf (has no children).
        
        This is synchronous because it should be a quick check
        based on already-known information.
        
        Returns:
            True if node has no children, False otherwise
        """
        pass
    
    # Optional methods with default implementations
    
    async def display_name(self) -> str:
        """Get display name for this node.
        
        Default implementation returns the identifier.
        
        Returns:
            Human-readable name for the node
        """
        return await self.identifier()
    
    async def size(self) -> Optional[int]:
        """Get size of this node in bytes.
        
        Returns None if size is not applicable or unknown.
        
        Returns:
            Size in bytes or None
        """
        metadata = await self.metadata()
        return metadata.get('size')
    
    async def modified_time(self) -> Optional[float]:
        """Get modification time as Unix timestamp.
        
        Returns None if modification time is not applicable.
        
        Returns:
            Unix timestamp or None
        """
        metadata = await self.metadata()
        return metadata.get('modified_time')
    
    def __repr__(self) -> str:
        """Synchronous repr for debugging.
        
        Note: This is sync, so it can't show async properties.
        Use display_name() for async string representation.
        """
        return f"{self.__class__.__name__}()"