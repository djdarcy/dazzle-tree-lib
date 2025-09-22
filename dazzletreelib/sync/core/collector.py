"""Data collection strategies for DazzleTreeLib.

DataCollectors define what information to extract from nodes during traversal.
This allows the same traversal to collect different data based on requirements.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from .node import TreeNode
from .adapter import TreeAdapter


class DataCollector(ABC):
    """Abstract base class for data collection strategies.
    
    DataCollectors determine what information is extracted from each node
    during traversal. This separation allows the same traversal algorithm
    to be used for different purposes (e.g., collecting just names vs.
    full metadata vs. aggregated statistics).
    """
    
    def __init__(self, adapter: TreeAdapter):
        """Initialize collector with an adapter.
        
        Args:
            adapter: TreeAdapter for additional node operations
        """
        self.adapter = adapter
    
    @abstractmethod
    def collect(self, node: TreeNode, depth: int) -> Any:
        """Collect data from a node.
        
        Args:
            node: The node to collect data from
            depth: Current depth in traversal
            
        Returns:
            Collected data (type depends on collector)
        """
        pass
    
    @abstractmethod
    def requires_children(self) -> bool:
        """Check if this collector needs access to child nodes.
        
        Used for optimization - if False, traverser can skip
        checking children for leaf determination.
        
        Returns:
            True if collector needs child information
        """
        pass


class IdentifierCollector(DataCollector):
    """Collects only node identifiers.
    
    Most memory-efficient collector - just returns the node ID string.
    Useful for building path lists or checking existence.
    """
    
    def collect(self, node: TreeNode, depth: int) -> str:
        """Return node identifier."""
        return node.identifier()
    
    def requires_children(self) -> bool:
        """No child access needed."""
        return False


class MetadataCollector(DataCollector):
    """Collects basic metadata from nodes.
    
    Returns the metadata dictionary from each node.
    Useful for getting file stats, timestamps, etc.
    """
    
    def collect(self, node: TreeNode, depth: int) -> Dict[str, Any]:
        """Return node metadata."""
        return node.metadata()
    
    def requires_children(self) -> bool:
        """No child access needed for basic metadata."""
        return False


class FullNodeCollector(DataCollector):
    """Collects complete node objects.
    
    Returns the entire TreeNode object. Useful when you need
    full access to node methods and properties.
    """
    
    def collect(self, node: TreeNode, depth: int) -> TreeNode:
        """Return the node itself."""
        return node
    
    def requires_children(self) -> bool:
        """No child access needed."""
        return False


class ChildCountCollector(DataCollector):
    """Collects nodes with child count information.
    
    Returns a dict with node info and number of immediate children.
    Useful for tree structure analysis.
    """
    
    def collect(self, node: TreeNode, depth: int) -> Dict[str, Any]:
        """Return node info with child count."""
        child_count = 0
        if not node.is_leaf():
            # Count immediate children
            for _ in self.adapter.get_children(node):
                child_count += 1
        
        return {
            'id': node.identifier(),
            'depth': depth,
            'child_count': child_count,
            'is_leaf': node.is_leaf()
        }
    
    def requires_children(self) -> bool:
        """Needs to count children."""
        return True


class PathCollector(DataCollector):
    """Collects full paths from root to each node.
    
    Builds complete path information during traversal.
    Useful for understanding node hierarchy.
    """
    
    def __init__(self, adapter: TreeAdapter):
        super().__init__(adapter)
        self._path_cache: Dict[str, List[str]] = {}
    
    def collect(self, node: TreeNode, depth: int) -> List[str]:
        """Return full path from root to node."""
        node_id = node.identifier()
        
        # Check cache first
        if node_id in self._path_cache:
            return self._path_cache[node_id]
        
        # Build path by walking up to root
        path = [node_id]
        current = node
        
        while True:
            parent = self.adapter.get_parent(current)
            if parent is None:
                break
            path.insert(0, parent.identifier())
            current = parent
        
        # Cache for future use
        self._path_cache[node_id] = path
        return path
    
    def requires_children(self) -> bool:
        """No child access needed."""
        return False


class AggregateCollector(DataCollector):
    """Base class for collectors that aggregate data from subtrees.
    
    Subclasses can implement different aggregation strategies
    (sum, max, min, average, etc.) over node properties.
    """
    
    def __init__(self, adapter: TreeAdapter, property_name: str):
        """Initialize with property to aggregate.
        
        Args:
            adapter: TreeAdapter for tree navigation
            property_name: Name of property to aggregate from metadata
        """
        super().__init__(adapter)
        self.property_name = property_name
        self._cache: Dict[str, Any] = {}
    
    @abstractmethod
    def aggregate(self, values: List[Any]) -> Any:
        """Aggregate multiple values into one.
        
        Args:
            values: List of values to aggregate
            
        Returns:
            Aggregated value
        """
        pass
    
    def collect(self, node: TreeNode, depth: int) -> Dict[str, Any]:
        """Collect aggregated data from node and its subtree."""
        node_id = node.identifier()
        
        # Check cache
        if node_id in self._cache:
            return self._cache[node_id]
        
        # Get node's own value
        metadata = node.metadata()
        node_value = metadata.get(self.property_name, 0)
        
        # Collect values from all descendants
        values = [node_value]
        if not node.is_leaf():
            for child in self.adapter.get_children(node):
                child_result = self.collect(child, depth + 1)
                values.append(child_result['aggregated'])
        
        # Aggregate and cache
        result = {
            'id': node_id,
            'depth': depth,
            'own_value': node_value,
            'aggregated': self.aggregate(values)
        }
        self._cache[node_id] = result
        
        return result
    
    def requires_children(self) -> bool:
        """Needs to traverse children for aggregation."""
        return True


class SumCollector(AggregateCollector):
    """Sums a property across subtrees.
    
    Useful for calculating total sizes, counts, etc.
    """
    
    def aggregate(self, values: List[Any]) -> Any:
        """Sum all values."""
        return sum(v for v in values if v is not None)


class MaxCollector(AggregateCollector):
    """Finds maximum value of a property in subtrees.
    
    Useful for finding latest modification times, largest files, etc.
    """
    
    def aggregate(self, values: List[Any]) -> Any:
        """Return maximum value."""
        valid_values = [v for v in values if v is not None]
        return max(valid_values) if valid_values else None


class CustomCollector(DataCollector):
    """Collector that uses a user-provided function.
    
    Allows custom data collection logic without subclassing.
    """
    
    def __init__(self, adapter: TreeAdapter, collect_func, requires_children_func=None):
        """Initialize with custom collection function.
        
        Args:
            adapter: TreeAdapter for tree navigation
            collect_func: Function(node, depth) -> Any
            requires_children_func: Function() -> bool (default: returns False)
        """
        super().__init__(adapter)
        self.collect_func = collect_func
        self.requires_children_func = requires_children_func or (lambda: False)
    
    def collect(self, node: TreeNode, depth: int) -> Any:
        """Use custom function to collect data."""
        return self.collect_func(node, depth)
    
    def requires_children(self) -> bool:
        """Use custom function to determine if children needed."""
        return self.requires_children_func()