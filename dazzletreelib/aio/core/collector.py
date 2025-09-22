"""Async data collectors for tree traversal.

Collectors extract and aggregate data from nodes during traversal.
All collectors work with async streams for memory efficiency.
"""

from abc import ABC, abstractmethod
from typing import AsyncIterator, Any, List, Dict, Optional, Set
from pathlib import Path


class AsyncDataCollector(ABC):
    """Abstract base class for async data collectors.
    
    Collectors process nodes during traversal to extract specific
    information. They can maintain state and aggregate data.
    """
    
    def __init__(self):
        """Initialize collector with empty state."""
        self.reset()
    
    @abstractmethod
    async def collect(self, node: Any, depth: int = 0) -> Any:
        """Collect data from a single node.
        
        Args:
            node: Node to collect data from
            depth: Current depth in tree
            
        Returns:
            Collected data (type depends on collector)
        """
        pass
    
    @abstractmethod
    def reset(self):
        """Reset collector state.
        
        Called before starting a new traversal.
        """
        pass
    
    @abstractmethod
    def get_result(self) -> Any:
        """Get final collected result.
        
        Returns:
            Aggregated collection result
        """
        pass
    
    async def process_stream(
        self,
        nodes: AsyncIterator[Any],
        with_depth: bool = False
    ) -> Any:
        """Process an entire stream of nodes.
        
        Args:
            nodes: Async iterator of nodes
            with_depth: If True, nodes are (node, depth) tuples
            
        Returns:
            Final collected result
        """
        self.reset()
        
        async for item in nodes:
            if with_depth:
                node, depth = item
                await self.collect(node, depth)
            else:
                await self.collect(item)
        
        return self.get_result()


class AsyncMetadataCollector(AsyncDataCollector):
    """Collects metadata from all nodes.
    
    Builds a list of metadata dictionaries for each node.
    """
    
    def __init__(self, include_path: bool = True):
        """Initialize metadata collector.
        
        Args:
            include_path: Whether to include node path in metadata
        """
        self.include_path = include_path
        super().__init__()
    
    def reset(self):
        """Reset collected metadata."""
        self.metadata_list: List[Dict[str, Any]] = []
    
    async def collect(self, node: Any, depth: int = 0) -> Dict[str, Any]:
        """Collect metadata from a node.
        
        Args:
            node: Node to collect from
            depth: Current depth
            
        Returns:
            Node metadata dictionary
        """
        metadata = {}
        
        # Get basic metadata
        if hasattr(node, 'metadata'):
            metadata.update(await node.metadata())
        
        # Add identifier
        if hasattr(node, 'identifier'):
            metadata['id'] = await node.identifier()
        
        # Add depth
        metadata['depth'] = depth
        
        # Add display name if available
        if hasattr(node, 'display_name'):
            metadata['name'] = await node.display_name()
        
        self.metadata_list.append(metadata)
        return metadata
    
    def get_result(self) -> List[Dict[str, Any]]:
        """Get collected metadata list.
        
        Returns:
            List of metadata dictionaries
        """
        return self.metadata_list


class AsyncPathCollector(AsyncDataCollector):
    """Collects paths of all nodes.
    
    Builds a list of node paths (identifiers).
    """
    
    def __init__(self, separator: str = '/'):
        """Initialize path collector.
        
        Args:
            separator: Path separator character
        """
        self.separator = separator
        super().__init__()
    
    def reset(self):
        """Reset collected paths."""
        self.paths: List[str] = []
        self.path_stack: List[str] = []
    
    async def collect(self, node: Any, depth: int = 0) -> str:
        """Collect path for a node.
        
        Args:
            node: Node to collect from
            depth: Current depth
            
        Returns:
            Node path string
        """
        # Get node identifier
        if hasattr(node, 'identifier'):
            node_id = await node.identifier()
        else:
            node_id = str(node)
        
        # Manage path stack based on depth
        while len(self.path_stack) > depth:
            self.path_stack.pop()
        
        if depth == 0:
            self.path_stack = [node_id]
        else:
            if len(self.path_stack) == depth:
                self.path_stack.append(node_id)
            else:
                # Fill in missing levels if needed
                while len(self.path_stack) < depth:
                    self.path_stack.append('?')
                self.path_stack.append(node_id)
        
        path = self.separator.join(self.path_stack)
        self.paths.append(path)
        return path
    
    def get_result(self) -> List[str]:
        """Get collected paths.
        
        Returns:
            List of path strings
        """
        return self.paths


class AsyncSizeCollector(AsyncDataCollector):
    """Collects and aggregates sizes from nodes.
    
    Useful for calculating total size of a tree structure.
    """
    
    def reset(self):
        """Reset size counter."""
        self.total_size = 0
        self.file_count = 0
        self.dir_count = 0
    
    async def collect(self, node: Any, depth: int = 0) -> Optional[int]:
        """Collect size from a node.
        
        Args:
            node: Node to collect from
            depth: Current depth
            
        Returns:
            Node size or None
        """
        size = None
        
        # Get size from node
        if hasattr(node, 'size'):
            size = await node.size()
        elif hasattr(node, 'metadata'):
            metadata = await node.metadata()
            size = metadata.get('size')
        
        # Update counters
        if size is not None:
            self.total_size += size
            self.file_count += 1
        else:
            self.dir_count += 1
        
        return size
    
    def get_result(self) -> Dict[str, Any]:
        """Get size statistics.
        
        Returns:
            Dictionary with total_size, file_count, dir_count
        """
        return {
            'total_size': self.total_size,
            'file_count': self.file_count,
            'dir_count': self.dir_count,
            'average_size': self.total_size / self.file_count if self.file_count > 0 else 0
        }


class AsyncFilterCollector(AsyncDataCollector):
    """Collects only nodes matching a filter predicate.
    
    Useful for finding specific nodes in a tree.
    """
    
    def __init__(self, predicate):
        """Initialize filter collector.
        
        Args:
            predicate: Async function that returns True for nodes to collect
        """
        self.predicate = predicate
        super().__init__()
    
    def reset(self):
        """Reset collected nodes."""
        self.matching_nodes: List[Any] = []
    
    async def collect(self, node: Any, depth: int = 0) -> Optional[Any]:
        """Collect node if it matches the filter.
        
        Args:
            node: Node to test
            depth: Current depth
            
        Returns:
            Node if it matches, None otherwise
        """
        # Check if node matches predicate
        if callable(self.predicate):
            if asyncio.iscoroutinefunction(self.predicate):
                matches = await self.predicate(node, depth)
            else:
                matches = self.predicate(node, depth)
        else:
            matches = False
        
        if matches:
            self.matching_nodes.append(node)
            return node
        
        return None
    
    def get_result(self) -> List[Any]:
        """Get nodes that matched the filter.
        
        Returns:
            List of matching nodes
        """
        return self.matching_nodes