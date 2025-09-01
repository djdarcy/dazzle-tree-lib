"""
Caching adapter implementations for DazzleTreeLib.

Provides transparent caching layer that can wrap any tree adapter,
with special optimizations for filesystem-based trees.
"""

import asyncio
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any, AsyncIterator
from cachetools import TTLCache

from ..core import AsyncTreeAdapter, AsyncTreeNode


class CachingTreeAdapter(AsyncTreeAdapter):
    """
    Optional caching layer for any tree adapter.
    
    Provides significant performance improvement for repeated traversals
    by caching the immediate children of each node. Uses Future-based
    locking to prevent duplicate concurrent scans of the same path.
    
    Example:
        base_adapter = AsyncFileSystemAdapter()
        cached_adapter = CachingTreeAdapter(base_adapter, max_size=50000)
        
        async for node in traverse_tree_async(path, adapter=cached_adapter):
            process(node)
    """
    
    def __init__(
        self,
        base_adapter: AsyncTreeAdapter,
        max_size: int = 10000,
        ttl: float = 300.0  # 5 minutes
    ):
        """
        Initialize caching adapter.
        
        Args:
            base_adapter: The underlying tree adapter to wrap
            max_size: Maximum number of entries in cache
            ttl: Time-to-live for cache entries in seconds
        """
        super().__init__()
        self._adapter = base_adapter
        self._cache = TTLCache(maxsize=max_size, ttl=ttl)
        self._scans_in_progress: Dict[Any, asyncio.Future] = {}
        
        # Statistics
        self.cache_hits = 0
        self.cache_misses = 0
        self.concurrent_waits = 0
    
    async def get_children(self, node: AsyncTreeNode) -> AsyncIterator[AsyncTreeNode]:
        """
        Get children with caching and async coordination.
        
        This method:
        1. Checks if another task is already scanning this path
        2. Checks the cache for existing results
        3. Performs the scan if needed
        4. Shares results with all waiting tasks
        """
        # Use node's path as cache key
        cache_key = self._get_cache_key(node)
        
        # 1. Check if scan already in progress
        if cache_key in self._scans_in_progress:
            # Wait for existing scan to complete
            self.concurrent_waits += 1
            try:
                children = await self._scans_in_progress[cache_key]
                for child in children:
                    yield child
                return
            except Exception:
                # If the original scan failed, we'll try again
                pass
        
        # 2. Check cache
        cached_result = self._check_cache(cache_key)
        if cached_result is not None:
            self.cache_hits += 1
            for child in cached_result:
                yield child
            return
        
        # 3. Cache miss - need to scan
        self.cache_misses += 1
        
        # Create future for this scan
        future = asyncio.Future()
        self._scans_in_progress[cache_key] = future
        
        try:
            # 4. Perform actual scan - collect all children first
            children = []
            async for child in self._adapter.get_children(node):
                children.append(child)
            
            # 5. Cache the result
            self._update_cache(cache_key, children)
            
            # 6. Complete the future
            future.set_result(children)
            
            # Yield the children
            for child in children:
                yield child
            
        except Exception as e:
            future.set_exception(e)
            raise
        finally:
            # 7. Remove from in-progress
            if cache_key in self._scans_in_progress:
                del self._scans_in_progress[cache_key]
    
    def _get_cache_key(self, node: AsyncTreeNode) -> Any:
        """
        Generate cache key for a node.
        
        Default implementation uses the node's path if available,
        otherwise uses the node itself.
        """
        if hasattr(node, 'path'):
            return node.path
        return node
    
    def _check_cache(self, cache_key: Any) -> Optional[List[AsyncTreeNode]]:
        """
        Check cache for existing results.
        
        Returns None if not found or invalid.
        """
        if cache_key in self._cache:
            return self._cache[cache_key]
        return None
    
    def _update_cache(self, cache_key: Any, children: List[AsyncTreeNode]) -> None:
        """
        Update cache with new results.
        """
        self._cache[cache_key] = children
    
    async def get_parent(self, node: AsyncTreeNode) -> Optional[AsyncTreeNode]:
        """
        Delegate to underlying adapter.
        """
        return await self._adapter.get_parent(node)
    
    async def get_depth(self, node: AsyncTreeNode) -> int:
        """
        Delegate to underlying adapter.
        """
        return await self._adapter.get_depth(node)
    
    def get_cache_stats(self) -> dict:
        """
        Get cache statistics for monitoring and debugging.
        """
        total_requests = self.cache_hits + self.cache_misses
        hit_rate = self.cache_hits / total_requests if total_requests > 0 else 0
        
        return {
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'hit_rate': hit_rate,
            'concurrent_waits': self.concurrent_waits,
            'cache_size': len(self._cache),
            'max_size': self._cache.maxsize,
            'ttl': self._cache.ttl
        }
    
    def clear_cache(self) -> None:
        """
        Clear all cached entries.
        """
        self._cache.clear()
        self.cache_hits = 0
        self.cache_misses = 0
        self.concurrent_waits = 0


class FilesystemCachingAdapter(CachingTreeAdapter):
    """
    Filesystem-specific caching adapter with mtime-based invalidation.
    
    This adapter extends the basic caching with filesystem-specific
    optimizations, using modification time (mtime) to detect changes
    and invalidate stale cache entries.
    """
    
    def __init__(
        self,
        base_adapter: AsyncTreeAdapter,
        max_size: int = 10000,
        ttl: float = 300.0
    ):
        """
        Initialize filesystem caching adapter.
        
        Args:
            base_adapter: The underlying filesystem adapter
            max_size: Maximum number of entries in cache
            ttl: Time-to-live for cache entries (fallback when mtime unavailable)
        """
        super().__init__(base_adapter, max_size, ttl)
        # Cache stores tuples of (children, mtime)
        self._mtime_cache: Dict[Path, Tuple[List[AsyncTreeNode], float]] = {}
    
    def _check_cache(self, cache_key: Any) -> Optional[List[AsyncTreeNode]]:
        """
        Check cache with mtime-based invalidation.
        
        For filesystem nodes, validates that the directory hasn't been
        modified since the cache entry was created.
        """
        # First try mtime-based cache for Path objects
        if isinstance(cache_key, Path) and cache_key in self._mtime_cache:
            children, cached_mtime = self._mtime_cache[cache_key]
            try:
                # Check if directory has been modified
                current_mtime = cache_key.stat().st_mtime
                if current_mtime == cached_mtime:
                    return children  # Cache hit with valid mtime
            except (OSError, IOError):
                # If we can't stat the path, invalidate the cache
                del self._mtime_cache[cache_key]
        
        # Fall back to TTL-based cache
        return super()._check_cache(cache_key)
    
    def _update_cache(self, cache_key: Any, children: List[AsyncTreeNode]) -> None:
        """
        Update cache with mtime tracking for filesystem paths.
        """
        # Store in mtime cache if it's a Path
        if isinstance(cache_key, Path):
            try:
                mtime = cache_key.stat().st_mtime
                self._mtime_cache[cache_key] = (children, mtime)
            except (OSError, IOError):
                # If we can't get mtime, fall back to TTL cache
                pass
        
        # Always update TTL cache as fallback
        super()._update_cache(cache_key, children)
    
    def clear_cache(self) -> None:
        """
        Clear all cached entries including mtime cache.
        """
        super().clear_cache()
        self._mtime_cache.clear()
    
    def get_cache_stats(self) -> dict:
        """
        Get extended cache statistics including mtime cache.
        """
        stats = super().get_cache_stats()
        stats['mtime_cache_size'] = len(self._mtime_cache)
        return stats