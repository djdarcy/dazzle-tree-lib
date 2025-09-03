"""
Cache completeness tracking adapter for DazzleTreeLib.

This adapter tracks how thoroughly each folder has been scanned,
enabling intelligent cache reuse like folder_datetime_fix's SmartStreamingCache.
"""

from typing import Optional, Any, Dict, AsyncIterator, Tuple
from enum import IntEnum
from pathlib import Path
from collections import OrderedDict
import asyncio
from ..core import AsyncTreeAdapter


class CacheCompleteness(IntEnum):
    """
    Enum representing how completely a folder has been scanned.
    
    Values are ordered so higher values satisfy lower requirements.
    """
    NONE = 0         # Not scanned at all
    SHALLOW = 1      # Only immediate children scanned
    PARTIAL_2 = 2    # Scanned to depth 2
    PARTIAL_3 = 3    # Scanned to depth 3
    PARTIAL_4 = 4    # Scanned to depth 4
    PARTIAL_5 = 5    # Scanned to depth 5
    COMPLETE = 999   # Fully recursive scan
    
    @classmethod
    def from_depth(cls, depth: Optional[int]) -> 'CacheCompleteness':
        """
        Convert a depth value to completeness level.
        
        Args:
            depth: Maximum depth scanned (None = complete)
            
        Returns:
            Corresponding completeness level
        """
        if depth is None:
            return cls.COMPLETE
        elif depth == 1:
            return cls.SHALLOW
        elif depth == 2:
            return cls.PARTIAL_2
        elif depth == 3:
            return cls.PARTIAL_3
        elif depth == 4:
            return cls.PARTIAL_4
        elif depth == 5:
            return cls.PARTIAL_5
        else:
            # For depth > 5, return COMPLETE
            return cls.COMPLETE
    
    def satisfies(self, required: 'CacheCompleteness') -> bool:
        """
        Check if this completeness level satisfies a requirement.
        
        Args:
            required: The required completeness level
            
        Returns:
            True if this level meets or exceeds the requirement
        """
        return self >= required


class CacheEntry:
    """Entry in the completeness-aware cache."""
    
    def __init__(self, data: Any, completeness: CacheCompleteness):
        """
        Initialize cache entry.
        
        Args:
            data: The cached data
            completeness: How completely this was scanned
        """
        self.data = data
        self.completeness = completeness
        self.access_count = 0
        self.size_estimate = 0  # Bytes estimate for memory management
    
    def satisfies_depth(self, depth: Optional[int]) -> bool:
        """
        Check if this cache entry satisfies a depth requirement.
        
        Args:
            depth: Required depth (None = complete)
            
        Returns:
            True if this entry has sufficient completeness
        """
        required = CacheCompleteness.from_depth(depth)
        return self.completeness.satisfies(required)


class CompletenessAwareCacheAdapter(AsyncTreeAdapter):
    """
    Caching adapter that tracks scan completeness for intelligent reuse.
    
    This enables folder_datetime_fix's optimization where:
    - Complete scans can satisfy any request
    - Partial scans can satisfy shallower requests
    - Deeper requests trigger cache upgrades
    """
    
    def __init__(self, base_adapter: AsyncTreeAdapter, max_memory_mb: int = 100):
        """
        Initialize cache adapter.
        
        Args:
            base_adapter: The underlying adapter to wrap
            max_memory_mb: Maximum cache size in megabytes
        """
        self.base_adapter = base_adapter
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self.max_memory = max_memory_mb * 1024 * 1024
        self.current_memory = 0
        self.stats = {
            'hits': 0,
            'misses': 0,
            'upgrades': 0,
            'evictions': 0
        }
        self._depth_context = None  # Optional depth context for caching
        
        # Hybrid approach: Track node completeness separately
        self.node_completeness = {}  # Path → depth mapping for all visited nodes
        self.track_nodes = True  # Can be disabled to save memory
    
    def set_depth_context(self, depth: Optional[int]):
        """
        Optionally set depth context for caching operations.
        
        Args:
            depth: The depth level for cache completeness tracking
            
        Returns:
            self for method chaining
        """
        self._depth_context = depth
        return self
    
    async def get_children(self, node: Any):
        """Get children with completeness-aware caching."""
        # Define function to compute children if not cached
        async def compute_children():
            children = []
            async for child in self.base_adapter.get_children(node):
                children.append(child)
                # Track child nodes if enabled
                if self.track_nodes and hasattr(child, 'path'):
                    child_path_str = str(child.path)
                    # Record that this child was discovered at current depth + 1
                    if child_path_str not in self.node_completeness:
                        self.node_completeness[child_path_str] = 0  # Will be set properly below
            return children
        
        # Determine cache key and depth
        path = node.path if hasattr(node, 'path') else str(node)
        if not isinstance(path, Path):
            path = Path(path) if isinstance(path, str) else path
        
        # Use depth context if set, otherwise default to SHALLOW (depth=1)
        depth = self._depth_context if self._depth_context is not None else 1
        
        # Track this node being visited if enabled
        if self.track_nodes:
            path_str = str(path)
            # Update node completeness - use max of existing and current depth
            existing_depth = self.node_completeness.get(path_str, 0)
            self.node_completeness[path_str] = max(existing_depth, depth)
        
        # Use existing cache infrastructure
        children_list, was_cached = await self.get_or_compute(
            path,
            compute_children,
            depth
        )
        
        # Yield children from cache
        for child in children_list:
            yield child
    
    async def get_parent(self, node: Any) -> Optional[Any]:
        """Pass through to base adapter."""
        return await self.base_adapter.get_parent(node)
    
    async def get_depth(self, node: Any) -> int:
        """Pass through to base adapter."""
        return await self.base_adapter.get_depth(node)
    
    def is_leaf(self, node: Any) -> bool:
        """Pass through to base adapter."""
        return self.base_adapter.is_leaf(node)
    
    async def get_or_compute(
        self, 
        path: Path, 
        compute_func, 
        depth: Optional[int] = None
    ) -> Tuple[Any, bool]:
        """
        Get from cache or compute with completeness tracking.
        
        Args:
            path: Path to cache
            compute_func: Async function to compute if not cached
            depth: Depth requirement for this request
            
        Returns:
            Tuple of (result, was_cached)
        """
        cache_key = str(path)
        
        # Check if we have a sufficient cache entry
        if cache_key in self.cache:
            entry = self.cache[cache_key]
            
            if entry.satisfies_depth(depth):
                # Cache hit!
                self.stats['hits'] += 1
                entry.access_count += 1
                
                # Move to end for LRU
                self.cache.move_to_end(cache_key)
                
                return entry.data, True
            else:
                # Cache entry exists but insufficient depth
                self.stats['upgrades'] += 1
                # Fall through to recompute
        else:
            self.stats['misses'] += 1
        
        # Compute the result
        result = await compute_func()
        
        # Store in cache with completeness
        completeness = CacheCompleteness.from_depth(depth)
        entry = CacheEntry(result, completeness)
        
        # Estimate memory usage (rough)
        entry.size_estimate = len(str(result)) * 2  # Rough estimate
        
        # Add to cache with LRU eviction if needed
        self._add_to_cache(cache_key, entry)
        
        return result, False
    
    def _add_to_cache(self, key: str, entry: CacheEntry):
        """
        Add entry to cache with LRU eviction if needed.
        
        Args:
            key: Cache key
            entry: Cache entry to add
        """
        # Remove old entry if exists
        if key in self.cache:
            old_entry = self.cache[key]
            self.current_memory -= old_entry.size_estimate
            del self.cache[key]
        
        # Evict LRU entries if needed
        while self.current_memory + entry.size_estimate > self.max_memory and self.cache:
            # Remove least recently used
            lru_key, lru_entry = self.cache.popitem(last=False)
            self.current_memory -= lru_entry.size_estimate
            self.stats['evictions'] += 1
        
        # Add new entry
        self.cache[key] = entry
        self.current_memory += entry.size_estimate
    
    def upgrade_cache(self, path: Path, new_data: Any, new_depth: Optional[int]):
        """
        Upgrade an existing cache entry to higher completeness.
        
        Args:
            path: Path to upgrade
            new_data: New data with higher completeness
            new_depth: New depth level
        """
        cache_key = str(path)
        new_completeness = CacheCompleteness.from_depth(new_depth)
        
        if cache_key in self.cache:
            old_entry = self.cache[cache_key]
            
            # Only upgrade if new is more complete
            if new_completeness > old_entry.completeness:
                entry = CacheEntry(new_data, new_completeness)
                entry.access_count = old_entry.access_count
                self._add_to_cache(cache_key, entry)
        else:
            # New entry
            entry = CacheEntry(new_data, new_completeness)
            self._add_to_cache(cache_key, entry)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.stats['hits'] + self.stats['misses']
        hit_rate = self.stats['hits'] / total_requests if total_requests > 0 else 0
        
        return {
            **self.stats,
            'entries': len(self.cache),
            'memory_mb': self.current_memory / (1024 * 1024),
            'hit_rate': hit_rate
        }
    
    def clear_cache(self):
        """Clear all cache entries."""
        self.cache.clear()
        self.current_memory = 0
        # Don't reset stats - keep for analysis