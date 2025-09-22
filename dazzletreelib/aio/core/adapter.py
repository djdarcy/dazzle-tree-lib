"""Async tree adapter abstraction.

Defines how to adapt different data sources into the async tree interface.
Key feature: Uses AsyncIterator for streaming child nodes.
"""

import asyncio
import threading
from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional, Set, Any, Tuple


class CacheKeyMixin:
    """Mixin providing standardized cache key generation for tree adapters.
    
    This mixin ensures cache keys are unique across different adapter types
    and instances, preventing cache collision when adapters are stacked.
    
    Features:
    - Unique class identification using module + class name
    - Thread-safe instance numbering for deterministic keys
    - Standardized key prefix generation
    """
    
    def __init_subclass__(cls, **kwargs):
        """Initialize class-level attributes when subclass is created."""
        super().__init_subclass__(**kwargs)
        # Create unique class identifier using full module path
        cls._class_id = f"{cls.__module__}.{cls.__name__}"
        # Initialize instance counter for this class
        cls._instance_counter = 0
        cls._counter_lock = threading.Lock()
    
    def __init__(self, *args, **kwargs):
        """Initialize instance-level cache key attributes."""
        super().__init__(*args, **kwargs)
        # Assign unique instance number in thread-safe manner
        with self.__class__._counter_lock:
            self.__class__._instance_counter += 1
            self._instance_number = self.__class__._instance_counter
    
    def _get_cache_key_prefix(self) -> Tuple[str, int]:
        """Get standardized cache key prefix for this adapter instance.
        
        Returns:
            Tuple of (class_identifier, instance_number)
        """
        return (self._class_id, self._instance_number)


class AsyncTreeAdapter(ABC):
    """Abstract base class for async tree adapters.
    
    Adapters bridge between the generic tree traversal logic and
    specific tree implementations. The async version uses AsyncIterator
    for streaming children, enabling memory-efficient traversal of
    large trees.
    """
    
    def __init__(self, max_concurrent: int = 100):
        """Initialize adapter with concurrency control.
        
        Args:
            max_concurrent: Maximum concurrent I/O operations
        """
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self._capabilities = self._define_capabilities()
    
    @abstractmethod
    async def get_children(self, node: Any) -> AsyncIterator[Any]:
        """Get children of a node as an async stream.
        
        This is the key difference from sync: returns AsyncIterator
        instead of List, allowing for streaming and parallel I/O.
        
        Args:
            node: Parent node
            
        Yields:
            Child nodes one at a time
        """
        pass
    
    @abstractmethod
    async def get_parent(self, node: Any) -> Optional[Any]:
        """Get parent of a node.
        
        Args:
            node: Child node
            
        Returns:
            Parent node or None if node is root
        """
        pass
    
    @abstractmethod
    async def get_depth(self, node: Any) -> int:
        """Get depth of node in tree.
        
        Root node has depth 0.
        
        Args:
            node: Node to check
            
        Returns:
            Depth level (0 for root)
        """
        pass
    
    # Optional methods with default implementations
    
    async def is_valid(self, node: Any) -> bool:
        """Check if node is valid for traversal.
        
        Can be used to filter out invalid/deleted nodes.
        
        Args:
            node: Node to validate
            
        Returns:
            True if node should be traversed
        """
        return True
    
    def supports_capability(self, capability: str) -> bool:
        """Check if adapter supports a specific capability.
        
        Args:
            capability: Capability name
            
        Returns:
            True if capability is supported
        """
        return capability in self._capabilities
    
    def _define_capabilities(self) -> Set[str]:
        """Define adapter capabilities.
        
        Override in subclasses to declare supported features.
        
        Returns:
            Set of capability names
        """
        return {
            'get_children',
            'get_parent', 
            'get_depth',
            'streaming',  # Async adapters always support streaming
        }
    
    async def get_stats(self) -> dict:
        """Get adapter statistics.
        
        Returns:
            Dictionary of statistics (I/O count, cache hits, etc.)
        """
        return {
            'max_concurrent': self.max_concurrent,
            'available_permits': self.semaphore._value if hasattr(self.semaphore, '_value') else None,
        }
    
    async def close(self):
        """Clean up adapter resources.
        
        Override if adapter needs cleanup (close connections, etc.)
        """
        pass
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()