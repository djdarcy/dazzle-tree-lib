"""TreeNode abstraction for TreeLib.

The TreeNode is intentionally kept simple - it's primarily a data container.
Navigation logic is delegated to the TreeAdapter, which is the key to making
TreeLib work with any tree structure.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class TreeNode(ABC):
    """Abstract base class for nodes in any tree structure.
    
    This class defines the minimal interface that all tree nodes must implement.
    The design philosophy is to keep this as simple as possible - it's a data
    container, not a navigation mechanism.
    
    Navigation logic (how to get children, parents, etc.) is handled by the
    TreeAdapter, allowing the same node type to be traversed in different ways.
    """
    
    @abstractmethod
    def identifier(self) -> str:
        """Return a unique identifier for this node.
        
        This identifier must be:
        - Unique within the tree
        - Stable across multiple traversals
        - Suitable for use as a cache key
        
        Examples:
        - Filesystem: absolute path ("/home/user/file.txt")
        - XML: XPath expression ("//root/element[@id='123']")
        - Database: composite primary key ("table:users:id:42")
        
        Returns:
            str: Unique, stable identifier for this node
        """
        pass
    
    @abstractmethod
    def is_leaf(self) -> bool:
        """Check if this node is a leaf (has no children).
        
        This is used for optimization - leaf nodes don't need to be
        traversed deeper.
        
        Returns:
            bool: True if this node has no children, False otherwise
        """
        pass
    
    @abstractmethod
    def metadata(self) -> Dict[str, Any]:
        """Return basic metadata about this node.
        
        Metadata should be lightweight information that can be gathered
        without expensive operations. Heavy data should be accessed through
        specialized methods.
        
        Common metadata fields:
        - name: Display name of the node
        - type: Node type (file, directory, element, etc.)
        - size: Size in bytes (if applicable)
        - created: Creation timestamp (if available)
        - modified: Modification timestamp (if available)
        
        Returns:
            Dict[str, Any]: Metadata dictionary
        """
        pass
    
    def __str__(self) -> str:
        """String representation defaults to identifier."""
        return self.identifier()
    
    def __repr__(self) -> str:
        """Detailed representation for debugging."""
        return f"{self.__class__.__name__}(id={self.identifier()!r})"
    
    def __eq__(self, other: object) -> bool:
        """Nodes are equal if they have the same identifier."""
        if not isinstance(other, TreeNode):
            return NotImplemented
        return self.identifier() == other.identifier()
    
    def __hash__(self) -> int:
        """Hash based on identifier for use in sets and dicts."""
        return hash(self.identifier())