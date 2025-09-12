"""
Cache adapter with completeness tracking for intelligent reuse.

This adapter tracks how deeply each path has been scanned, allowing
efficient cache reuse when shallower scans are requested after deeper ones.
"""

import time
import asyncio
from typing import Any, AsyncIterator, Optional, Tuple, Dict
from pathlib import Path
from collections import OrderedDict
from ..core import AsyncTreeAdapter, CacheKeyMixin


import warnings

# Backward compatibility enum for tests
# TODO: Remove in next major version (2.0.0)
class CacheCompleteness:
    """DEPRECATED: This class is deprecated and will be removed in v2.0.0.
    
    Use integer depths directly with CacheEntry instead:
    - Use depth=1 instead of CacheCompleteness.SHALLOW
    - Use depth=N instead of CacheCompleteness.PARTIAL_N
    - Use depth=CacheEntry.COMPLETE_DEPTH instead of CacheCompleteness.COMPLETE
    
    This class is only kept for backward compatibility with existing code.
    """
    NONE = 0
    SHALLOW = 1
    PARTIAL_2 = 2
    PARTIAL_3 = 3
    PARTIAL_4 = 4
    PARTIAL_5 = 5
    PARTIAL_N = 10
    COMPLETE = 999
    
    def __init__(self, value):
        warnings.warn(
            "CacheCompleteness is deprecated and will be removed in v2.0.0. "
            "Use integer depths directly with CacheEntry instead.",
            DeprecationWarning,
            stacklevel=2
        )
        self.value = value
        self.name = self._get_name(value)
    
    def _get_name(self, value):
        names = {
            0: 'NONE',
            1: 'SHALLOW',
            2: 'PARTIAL_2',
            3: 'PARTIAL_3',
            4: 'PARTIAL_4',
            5: 'PARTIAL_5',
            10: 'PARTIAL_N',
            999: 'COMPLETE',
        }
        return names.get(value, f'PARTIAL_{value}')
    
    def __eq__(self, other):
        if isinstance(other, CacheCompleteness):
            return self.value == other.value
        return self.value == other if isinstance(other, int) else False
    
    def __lt__(self, other):
        if isinstance(other, CacheCompleteness):
            return self.value < other.value
        return self.value < other if isinstance(other, int) else False
    
    def __le__(self, other):
        if isinstance(other, CacheCompleteness):
            return self.value <= other.value
        return self.value <= other if isinstance(other, int) else False
    
    def __gt__(self, other):
        if isinstance(other, CacheCompleteness):
            return self.value > other.value
        return self.value > other if isinstance(other, int) else False
    
    def __ge__(self, other):
        if isinstance(other, CacheCompleteness):
            return self.value >= other.value
        return self.value >= other if isinstance(other, int) else False
    
    def __hash__(self):
        return hash(self.value)
    
    def __repr__(self):
        return f'CacheCompleteness.{self.name}'
    
    @classmethod
    def from_depth(cls, depth):
        """Convert depth to completeness enum."""
        if depth is None or depth >= 999 or depth == -1:
            return cls.COMPLETE
        elif depth == 0:
            return cls.NONE
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
            return cls.PARTIAL_N
    
    def satisfies(self, required):
        """Check if this completeness satisfies a requirement."""
        return self.value >= required.value


# Singleton instances - created as class attributes to avoid deprecation warnings at import
# These will trigger warnings when actually used
CacheCompleteness.NONE = 0
CacheCompleteness.SHALLOW = 1
CacheCompleteness.PARTIAL_2 = 2
CacheCompleteness.PARTIAL_3 = 3
CacheCompleteness.PARTIAL_4 = 4
CacheCompleteness.PARTIAL_5 = 5
CacheCompleteness.PARTIAL_N = 10
CacheCompleteness.COMPLETE = 999


class CacheEntry:
    """Entry in the completeness-aware cache with integer depth tracking.
    
    Depth Semantics:
    ---------------
    - depth == -1 (COMPLETE_DEPTH): Complete scan - ALL levels cached, nothing more exists
    - depth >= 0: Partial scan - cached to this depth, more levels may exist below
    
    Examples:
    ---------
    - depth=1: Cached immediate children only (shallow scan)
    - depth=3: Cached 3 levels deep, but more levels may exist beyond
    - depth=-1: Cached entire tree structure, no unexplored nodes remain
    
    The distinction between "partial" and "complete" is critical for cache reuse:
    - A complete scan (depth=-1) can satisfy ANY depth request
    - A partial scan (depth=N) can only satisfy requests for depth <= N
    - Partial scans indicate potential for deeper exploration
    """
    
    # Constants for depth representation
    COMPLETE_DEPTH = -1  # Sentinel value for complete/infinite scan
    MAX_DEPTH = 100      # Safety limit to prevent memory explosion
    
    def __init__(self, data: Any, depth: int = COMPLETE_DEPTH, mtime: Optional[float] = None):
        """
        Initialize cache entry with integer depth.
        
        Args:
            data: The cached data
            depth: How deep this was scanned (-1 for complete, 0-MAX_DEPTH for specific)
            mtime: Modification time for future invalidation support
        """
        # Validate depth
        if depth != self.COMPLETE_DEPTH:
            if depth < 0:
                raise ValueError(f"Invalid depth {depth}: must be >= 0 or {self.COMPLETE_DEPTH}")
            if depth > self.MAX_DEPTH:
                raise ValueError(f"Depth {depth} exceeds maximum {self.MAX_DEPTH}")
        
        self.data = data
        self.depth = depth
        self.mtime = mtime
        self.cached_at = time.time()
        self.access_count = 0
        self.size_estimate = 0  # Bytes estimate for memory management
    
    def satisfies(self, required_depth: int) -> bool:
        """
        Check if this cache entry satisfies a depth requirement.
        
        Args:
            required_depth: Required depth (-1 for complete, >= 0 for specific)
            
        Returns:
            True if this entry has sufficient depth
        """
        # Complete scan satisfies everything
        if self.depth == self.COMPLETE_DEPTH:
            return True
        
        # If complete scan is required, partial doesn't satisfy
        if required_depth == self.COMPLETE_DEPTH:
            return False
        
        # Partial scan satisfies if deep enough
        return self.depth >= required_depth
    
    def is_partial(self) -> bool:
        """
        Check if this is a partial scan (more levels may exist below).
        
        Returns:
            True if this is a partial scan (depth >= 0), False if complete
            
        Example:
            >>> entry = CacheEntry(data=[], depth=3)
            >>> entry.is_partial()
            True
            >>> complete_entry = CacheEntry(data=[], depth=CacheEntry.COMPLETE_DEPTH)
            >>> complete_entry.is_partial()
            False
        """
        return self.depth != self.COMPLETE_DEPTH
    
    def is_complete(self) -> bool:
        """
        Check if this is a complete scan (entire tree cached).
        
        Returns:
            True if this is a complete scan (depth == -1), False if partial
            
        Example:
            >>> entry = CacheEntry(data=[], depth=3)
            >>> entry.is_complete()
            False
            >>> complete_entry = CacheEntry(data=[], depth=CacheEntry.COMPLETE_DEPTH)
            >>> complete_entry.is_complete()
            True
        """
        return self.depth == self.COMPLETE_DEPTH
    
    @classmethod
    def set_max_depth(cls, max_depth: int):
        """
        Configure the maximum allowed depth.
        
        Args:
            max_depth: New maximum depth limit
        """
        if max_depth < 1:
            raise ValueError(f"Maximum depth must be positive, got {max_depth}")
        cls.MAX_DEPTH = max_depth


class CompletenessAwareCacheAdapter(CacheKeyMixin, AsyncTreeAdapter):
    """
    Caching adapter that tracks scan depth for intelligent reuse.
    
    This enables optimizations where:
    - Complete scans can satisfy any request
    - Deep scans can satisfy shallower requests  
    - Deeper requests trigger cache upgrades
    
    Uses integer depth tracking instead of enums for unlimited scalability.
    """
    
    def __init__(self, base_adapter: AsyncTreeAdapter, 
                 max_memory_mb: int = 100,
                 max_depth: int = 100,
                 max_entries: int = 10000,
                 max_cache_depth: int = 50,
                 max_path_depth: int = 30,
                 max_tracked_nodes: int = 10000,
                 validation_ttl_seconds: float = 5.0):
        """
        Initialize the cache adapter with memory management limits.
        
        Args:
            base_adapter: The underlying adapter to wrap
            max_memory_mb: Maximum cache size in megabytes
            max_depth: Maximum allowed scan depth (for CacheEntry.MAX_DEPTH)
            max_entries: Maximum number of cache entries (primary OOM defense)
            max_cache_depth: Maximum depth to cache (don't cache deeper)
            max_path_depth: Maximum path components to cache
            max_tracked_nodes: Maximum nodes to track in node_completeness
            validation_ttl_seconds: Time to trust cached mtime without revalidation
                                   (0=always validate, -1=never validate)
        """
        super().__init__()  # Initialize parent classes (CacheKeyMixin, AsyncTreeAdapter)
        self.base_adapter = base_adapter
        self.cache: OrderedDict[Tuple, CacheEntry] = OrderedDict()
        self.max_memory = max_memory_mb * 1024 * 1024
        self.current_memory = 0
        
        # New memory management limits
        self.max_entries = max_entries
        self.max_cache_depth = max_cache_depth
        self.max_path_depth = max_path_depth
        self.max_tracked_nodes = max_tracked_nodes
        self.validation_ttl_seconds = validation_ttl_seconds
        
        # Configure maximum depth
        CacheEntry.MAX_DEPTH = max_depth
        
        # Statistics
        self.hits = 0
        self.misses = 0
        self.upgrades = 0
        
        # Node tracking - separate from cache, tracks ALL visited nodes
        # Convert to OrderedDict for bounded LRU tracking
        self.node_completeness = OrderedDict()  # Path → depth mapping
        self.track_nodes = True  # Can be disabled to save memory
        self._depth_context = None  # Depth context for operations
    
    async def get_children(self, node: Any) -> AsyncIterator[Any]:
        """
        Get children with caching.
        
        Uses the cache when available, otherwise fetches and caches.
        """
        # Get path from node
        path = node.path if hasattr(node, 'path') else str(node)
        if not isinstance(path, Path):
            path = Path(path) if isinstance(path, str) else path
        
        # Use depth context if set, otherwise default to 1 (shallow)
        depth = self._depth_context if self._depth_context is not None else 1
        cache_key = self._get_cache_key(path, depth)
        
        # Track this node being visited if enabled (bounded)
        if self.track_nodes:
            self._track_node_visit(str(path), depth)
        
        # Check if we have this in cache
        if cache_key in self.cache:
            entry = self.cache[cache_key]
            
            # Validate cache entry freshness if mtime is available
            # Note: We check mtime first (if available), then TTL as a secondary optimization
            if entry.mtime is not None and hasattr(node, 'metadata'):
                # Only do the expensive metadata call if TTL says we should (or if no TTL set)
                should_check_mtime = self._should_validate_mtime(entry)
                if should_check_mtime:
                    try:
                        # Get current mtime from node metadata
                        metadata = await node.metadata()
                        current_mtime = metadata.get('modified_time')
                        
                        if current_mtime is not None:
                            # Check if file has been modified (with tolerance for float comparison)
                            if abs(entry.mtime - current_mtime) > 0.001:
                                # Stale entry - invalidate and continue to fetch fresh
                                del self.cache[cache_key]
                                self.current_memory -= entry.size_estimate
                                # Fall through to fetch fresh data
                            else:
                                # Fresh cache hit - mtime validated
                                self.hits += 1
                                entry.access_count += 1
                                self.cache.move_to_end(cache_key)
                                
                                # Yield cached children
                                if isinstance(entry.data, list):
                                    for child in entry.data:
                                        yield child
                                return
                        else:
                            # Can't get current mtime, use cache optimistically
                            self.hits += 1
                            entry.access_count += 1
                            self.cache.move_to_end(cache_key)
                            
                            if isinstance(entry.data, list):
                                for child in entry.data:
                                    yield child
                            return
                    except Exception:
                        # Error getting metadata, use cache optimistically
                        self.hits += 1
                        entry.access_count += 1
                        self.cache.move_to_end(cache_key)
                        
                        if isinstance(entry.data, list):
                            for child in entry.data:
                                yield child
                        return
                else:
                    # TTL says skip validation, use cache directly
                    self.hits += 1
                    entry.access_count += 1
                    self.cache.move_to_end(cache_key)
                    
                    if isinstance(entry.data, list):
                        for child in entry.data:
                            yield child
                    return
            else:
                # No mtime validation possible, use cache as-is
                self.hits += 1
                entry.access_count += 1
                self.cache.move_to_end(cache_key)
                
                # Yield cached children
                if isinstance(entry.data, list):
                    for child in entry.data:
                        yield child
                return
        
        # Check if we have a deeper scan that satisfies this request
        for existing_key, entry in self.cache.items():
            if self._same_path(existing_key, cache_key):
                if entry.satisfies(depth):
                    # Validate freshness if mtime is available
                    is_fresh = True
                    if entry.mtime is not None and hasattr(node, 'metadata'):
                        try:
                            metadata = await node.metadata()
                            current_mtime = metadata.get('modified_time')
                            if current_mtime is not None and abs(entry.mtime - current_mtime) > 0.001:
                                # Stale entry - invalidate
                                del self.cache[existing_key]
                                self.current_memory -= entry.size_estimate
                                is_fresh = False
                        except Exception:
                            pass  # Can't validate, assume fresh
                    
                    if is_fresh:
                        self.hits += 1
                        entry.access_count += 1
                        self.cache.move_to_end(existing_key)
                        # Yield cached children
                        if isinstance(entry.data, list):
                            for child in entry.data:
                                yield child
                        return
        
        # Not in cache - get from base adapter and cache the result
        self.misses += 1
        children = []
        async for child in self.base_adapter.get_children(node):
            children.append(child)
            # Track child nodes if enabled (bounded)
            if self.track_nodes and hasattr(child, 'path'):
                self._track_node_visit(str(child.path), 0)  # Depth 0 for unvisited child
            yield child
        
        # Get mtime if available for cache invalidation
        mtime = None
        if hasattr(node, 'metadata'):
            try:
                metadata = await node.metadata()
                mtime = metadata.get('modified_time')
            except Exception:
                pass  # No mtime available
        
        # Cache the result with mtime
        self._add_to_cache(cache_key, children, depth, mtime)
    
    async def get_parent(self, node: Any) -> Optional[Any]:
        """Pass through to base adapter."""
        return await self.base_adapter.get_parent(node) if hasattr(self.base_adapter, 'get_parent') else None
    
    async def get_depth(self, node: Any) -> int:
        """Pass through to base adapter."""
        return await self.base_adapter.get_depth(node) if hasattr(self.base_adapter, 'get_depth') else 0
    
    def set_depth_context(self, depth: Optional[int]):
        """
        Set depth context for subsequent operations.
        
        Args:
            depth: Depth to use for caching
            
        Returns:
            self for method chaining
        """
        self._depth_context = depth
        return self
    
    async def get_children_at_depth(self, path: Path, depth: int = CacheEntry.COMPLETE_DEPTH) -> Tuple[Any, bool]:
        """
        Get children with specific depth requirement.
        
        Args:
            path: Path to scan
            depth: Required scan depth (-1 for complete)
            
        Returns:
            Tuple of (result, was_cached)
        """
        cache_key = self._get_cache_key(path, depth)
        
        # Check if we have a sufficient cache entry
        if cache_key in self.cache:
            entry = self.cache[cache_key]
            if entry.satisfies(depth):
                self.hits += 1
                entry.access_count += 1
                # Move to end for LRU
                self.cache.move_to_end(cache_key)
                return entry.data, True
        
        # Check if a deeper scan exists that satisfies this request
        for existing_key, entry in self.cache.items():
            if self._same_path(existing_key, cache_key) and entry.satisfies(depth):
                self.hits += 1
                entry.access_count += 1
                return entry.data, True
        
        # Cache miss - need to scan
        self.misses += 1
        result = await self._scan_path(path, depth)
        
        # Store in cache
        self._add_to_cache(cache_key, result, depth)
        
        return result, False
    
    async def _scan_path(self, path: Path, depth: int) -> Any:
        """
        Perform actual scan of path to specified depth.
        
        Args:
            path: Path to scan
            depth: Scan depth (-1 for complete)
            
        Returns:
            Scan results
        """
        # This would implement actual scanning logic
        # For now, just a placeholder
        return {"path": str(path), "depth": depth, "data": []}
    
    def _should_cache(self, path: Path, depth: int) -> bool:
        """
        Determine if an entry should be cached based on limits.
        
        Args:
            path: Path to check
            depth: Depth of the scan
            
        Returns:
            True if entry should be cached
        """
        # Check if caching is disabled (max_entries == 0)
        if self.max_entries == 0:
            return False
        
        # Check entry count limit (primary defense)
        if self.max_entries > 0 and len(self.cache) >= self.max_entries:
            return False
        
        # Check depth limit
        if self.max_cache_depth > 0 and depth > self.max_cache_depth:
            return False
        
        # Check path component limit
        if self.max_path_depth > 0 and len(path.parts) > self.max_path_depth:
            return False
        
        return True
    
    def _track_node_visit(self, path_str: str, depth: int):
        """
        Track a node visit with bounded LRU eviction.
        
        Args:
            path_str: String representation of path
            depth: Depth of the visit
        """
        if path_str in self.node_completeness:
            # Update existing entry and move to end (most recent)
            existing_depth = self.node_completeness[path_str]
            self.node_completeness[path_str] = max(existing_depth, depth)
            self.node_completeness.move_to_end(path_str)
        else:
            # Add new entry, evicting oldest if at limit
            if len(self.node_completeness) >= self.max_tracked_nodes:
                # Remove oldest (first) entry
                self.node_completeness.popitem(last=False)
            self.node_completeness[path_str] = depth
    
    def _should_validate_mtime(self, entry: 'CacheEntry') -> bool:
        """
        Determine if mtime validation should be performed.
        
        Args:
            entry: Cache entry to check
            
        Returns:
            True if mtime should be validated
        """
        # Never validate if TTL is negative
        if self.validation_ttl_seconds < 0:
            return False
        
        # Always validate if TTL is 0
        if self.validation_ttl_seconds == 0:
            return True
        
        # Check if entry has cached_at timestamp
        if not hasattr(entry, 'cached_at'):
            entry.cached_at = time.time()
            return True
        
        # Validate if TTL has expired
        return (time.time() - entry.cached_at) > self.validation_ttl_seconds
    
    def _add_to_cache(self, key: Tuple, data: Any, depth: int, mtime: Optional[float] = None):
        """
        Add entry to cache with memory management.
        
        Args:
            key: Cache key
            data: Data to cache
            depth: Scan depth
            mtime: Modification time for cache invalidation
        """
        # Extract path from key for checking limits
        # Key format: (class_id, instance_num, key_type, path, depth)
        path = Path(key[3]) if len(key) > 3 else Path("/")
        
        # Check if we should cache this entry
        if not self._should_cache(path, depth):
            return  # Don't cache
        
        entry = CacheEntry(data, depth, mtime)
        
        # Add timestamp for TTL validation
        entry.cached_at = time.time()
        
        # Improved memory estimation
        entry.size_estimate = self._estimate_entry_size(key, data)
        
        # Enforce max_entries limit (primary defense)
        while self.max_entries > 0 and len(self.cache) >= self.max_entries and self.cache:
            self._evict_lru()
        
        # Evict if necessary for memory limit
        while self.current_memory + entry.size_estimate > self.max_memory and self.cache:
            self._evict_lru()
        
        self.cache[key] = entry
        self.current_memory += entry.size_estimate
    
    def _estimate_entry_size(self, key: Tuple, data: Any) -> int:
        """
        Estimate memory usage of a cache entry.
        
        Args:
            key: Cache key tuple
            data: Cached data
            
        Returns:
            Estimated size in bytes
        """
        # Python object overhead estimates (64-bit)
        OBJECT_OVERHEAD = 56  # Base object overhead
        DICT_ENTRY_OVERHEAD = 200  # OrderedDict entry overhead
        
        # Key size (5-tuple with path string)
        key_size = OBJECT_OVERHEAD + 5 * 8  # Tuple with 5 pointers
        if len(key) > 3:
            key_size += len(str(key[3])) * 2  # Path string
        
        # Data size estimation
        data_size = OBJECT_OVERHEAD
        if isinstance(data, list):
            # List of children
            data_size += len(data) * 8  # Pointers to items
            # Sample first 10 items for size estimation
            sample_size = 0
            for item in data[:10]:
                sample_size += OBJECT_OVERHEAD + len(str(item)) * 2
            if data:
                avg_item_size = sample_size / min(len(data), 10)
                data_size += int(avg_item_size * len(data))
        else:
            # Fallback for other types
            data_size += len(str(data)) * 2
        
        return DICT_ENTRY_OVERHEAD + key_size + data_size
    
    def _evict_lru(self):
        """Evict least recently used cache entry."""
        if self.cache:
            key, entry = self.cache.popitem(last=False)
            self.current_memory -= entry.size_estimate
    
    def _same_path(self, key1: Tuple, key2: Tuple) -> bool:
        """
        Check if two cache keys refer to the same path.
        
        Args:
            key1: First cache key
            key2: Second cache key
            
        Returns:
            True if same path
        """
        # Keys are (class_id, instance_num, key_type, path, depth)
        # Same path if first 4 elements match
        return key1[:4] == key2[:4]
    
    def upgrade_cache_entry(self, path: Path, new_data: Any, new_depth: int):
        """
        Upgrade an existing cache entry with deeper scan.
        
        Args:
            path: Path that was scanned
            new_data: New scan data
            new_depth: New scan depth
        """
        cache_key = self._get_cache_key(path, new_depth)
        
        # Find and update existing entry
        for key in list(self.cache.keys()):
            if self._same_path(key, cache_key):
                old_entry = self.cache[key]
                if new_depth == CacheEntry.COMPLETE_DEPTH or \
                   (old_entry.depth != CacheEntry.COMPLETE_DEPTH and new_depth > old_entry.depth):
                    # Remove old entry
                    del self.cache[key]
                    self.current_memory -= old_entry.size_estimate
                    # Add new entry
                    self._add_to_cache(cache_key, new_data, new_depth)
                    self.upgrades += 1
                    break
    
    def clear_cache(self):
        """Clear all cache entries."""
        self.cache.clear()
        self.current_memory = 0
        # Don't reset stats - keep for analysis
    
    def _get_cache_key(self, path: Path, depth: int) -> Tuple[str, int, str, str, int]:
        """
        Generate cache key for completeness data.
        
        Returns tuple-based hierarchical key to prevent cache collision
        when adapters are stacked.
        
        Args:
            path: Path being cached
            depth: Scan depth (-1 for complete, >= 0 for specific)
            
        Returns:
            Tuple of (class_id, instance_num, key_type, path, depth)
        """
        return (*self._get_cache_key_prefix(), "completeness", str(path), depth)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary of cache statistics
        """
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.hits / (self.hits + self.misses) if (self.hits + self.misses) > 0 else 0,
            "upgrades": self.upgrades,
            "entries": len(self.cache),
            "memory_bytes": self.current_memory,
            "memory_mb": self.current_memory / (1024 * 1024)
        }