"""
Private cache storage implementation with LRU eviction and memory management.

This module extracts the cache storage logic from CompletenessAwareCacheAdapter
to prepare for the Strategy Pattern while maintaining the exact same behavior.
"""

import time
from typing import Any, Optional, Tuple, Dict
from collections import OrderedDict
from pathlib import Path


class _LruCacheStore:
    """
    Private cache storage with LRU eviction and memory management.

    This class encapsulates all cache storage operations including:
    - Get/put with LRU ordering
    - Memory-based eviction
    - Entry count limits
    - Pattern-based invalidation
    - Statistics tracking

    Supports two modes:
    - Safe mode (enable_protection=True): With limits and eviction
    - Fast mode (enable_protection=False): Unbounded for maximum performance
    """

    def __init__(self,
                 enable_protection: bool = True,
                 max_memory_mb: int = 100,
                 max_entries: int = 10000,
                 max_cache_depth: int = 50,
                 max_path_depth: int = 30):
        """
        Initialize cache storage with optional protection limits.

        Args:
            enable_protection: Enable memory and entry limits
            max_memory_mb: Maximum memory usage in megabytes
            max_entries: Maximum number of cache entries
            max_cache_depth: Maximum depth to cache
            max_path_depth: Maximum path components to cache
        """
        self.enable_protection = enable_protection

        if enable_protection:
            # Safe mode: Use OrderedDict for LRU
            self.cache = OrderedDict()
            self.max_memory = max_memory_mb * 1024 * 1024
            self.max_entries = max_entries
            self.max_cache_depth = max_cache_depth
            self.max_path_depth = max_path_depth
        else:
            # Fast mode: Use plain dict for speed
            self.cache = {}
            self.max_memory = float('inf')
            self.max_entries = float('inf')
            self.max_cache_depth = float('inf')
            self.max_path_depth = float('inf')

        self.current_memory = 0
        self.hits = 0
        self.misses = 0

    def get(self, key: Tuple) -> Optional[Any]:
        """
        Get a cache entry, updating LRU order if needed.

        Args:
            key: Cache key tuple (typically path and depth)

        Returns:
            Cached entry or None if not found
        """
        if key not in self.cache:
            return None

        entry = self.cache[key]

        if self.enable_protection:
            # Update LRU order by moving to end
            self.cache.move_to_end(key)
            # Update access tracking
            if hasattr(entry, 'access_count'):
                entry.access_count += 1
            if hasattr(entry, 'last_access'):
                entry.last_access = time.time()

        return entry

    def put(self, key: Tuple, entry: Any) -> bool:
        """
        Store a cache entry, evicting if needed.

        Args:
            key: Cache key tuple
            entry: Entry to cache

        Returns:
            True if cached, False if rejected (too large, etc.)
        """
        # Check if we should cache this entry
        if not self._should_cache(key, entry):
            return False

        # Get size of new entry
        entry_size = getattr(entry, 'size_estimate', 100)

        # If replacing existing entry, adjust memory
        if key in self.cache:
            old_entry = self.cache[key]
            old_size = getattr(old_entry, 'size_estimate', 100)
            self.current_memory -= old_size

        # Evict if needed (safe mode only)
        if self.enable_protection:
            self._evict_until_fit(entry_size)

        # Add to cache
        self.cache[key] = entry
        self.current_memory += entry_size

        # Ensure we don't exceed entry count
        if self.enable_protection and len(self.cache) > self.max_entries:
            self._evict_oldest()

        return True

    def invalidate(self, pattern: str = None, deep: bool = False) -> int:
        """
        Invalidate cache entries matching a pattern.

        Args:
            pattern: Path pattern to match (None = invalidate all)
            deep: If True, invalidate all descendants

        Returns:
            Number of entries invalidated
        """
        if pattern is None:
            # Invalidate all
            count = len(self.cache)
            self.clear()
            return count

        # Find entries to invalidate
        to_remove = []
        pattern_path = Path(pattern) if pattern else None

        for key in self.cache:
            # Extract path from key (assuming first element is path)
            if isinstance(key, tuple) and len(key) > 0:
                key_path = key[0]
                if isinstance(key_path, str):
                    key_path = Path(key_path)
                elif not isinstance(key_path, Path):
                    key_path = Path(str(key_path))

                # Check if matches pattern
                if self._path_matches(key_path, pattern_path, deep):
                    to_remove.append(key)

        # Remove matched entries
        for key in to_remove:
            entry = self.cache[key]
            entry_size = getattr(entry, 'size_estimate', 100)
            del self.cache[key]
            self.current_memory -= entry_size

        return len(to_remove)

    def clear(self):
        """Clear all cache entries."""
        self.cache.clear()
        self.current_memory = 0

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache metrics
        """
        stats = {
            'entries': len(self.cache),
            'memory_mb': self.current_memory / (1024 * 1024),
        }

        # Calculate hit rate if we have attempts
        total_attempts = self.hits + self.misses
        if total_attempts > 0:
            stats['hit_rate'] = self.hits / total_attempts

        return stats

    def _should_cache(self, key: Tuple, entry: Any) -> bool:
        """
        Check if an entry should be cached based on limits.

        Args:
            key: Cache key
            entry: Entry to check

        Returns:
            True if should cache, False otherwise
        """
        if not self.enable_protection:
            # Fast mode: cache everything
            return True

        # Check entry size (reject if larger than total memory limit)
        entry_size = getattr(entry, 'size_estimate', 100)
        if entry_size > self.max_memory:
            return False

        # Check path depth if key contains path
        if isinstance(key, tuple) and len(key) > 0:
            path = key[0]
            if isinstance(path, (str, Path)):
                path = Path(path) if isinstance(path, str) else path
                if hasattr(path, 'parts') and len(path.parts) > self.max_path_depth:
                    return False

        # Check cache depth
        if hasattr(entry, 'depth') and entry.depth > self.max_cache_depth:
            return False

        return True

    def _evict_until_fit(self, needed_memory: int):
        """
        Evict LRU entries until we have space for new entry.

        Args:
            needed_memory: Memory needed for new entry
        """
        if not self.enable_protection:
            return

        # Calculate how much we need to free
        available = self.max_memory - self.current_memory
        if available >= needed_memory:
            return

        to_free = needed_memory - available
        freed = 0

        # Evict oldest entries (LRU)
        while freed < to_free and len(self.cache) > 0:
            # Get oldest key (first in OrderedDict)
            oldest_key = next(iter(self.cache))
            oldest_entry = self.cache[oldest_key]
            entry_size = getattr(oldest_entry, 'size_estimate', 100)

            # Remove entry
            del self.cache[oldest_key]
            self.current_memory -= entry_size
            freed += entry_size

    def _evict_oldest(self):
        """Evict the oldest entry (for entry count limit)."""
        if len(self.cache) == 0:
            return

        # Get oldest key
        oldest_key = next(iter(self.cache))
        oldest_entry = self.cache[oldest_key]
        entry_size = getattr(oldest_entry, 'size_estimate', 100)

        # Remove entry
        del self.cache[oldest_key]
        self.current_memory -= entry_size

    def _path_matches(self, key_path: Path, pattern_path: Path, deep: bool) -> bool:
        """
        Check if a path matches the invalidation pattern.

        Args:
            key_path: Path from cache key
            pattern_path: Pattern to match against
            deep: If True, match all descendants

        Returns:
            True if matches, False otherwise
        """
        try:
            if deep:
                # Deep: match if key_path is under pattern_path
                return key_path.is_relative_to(pattern_path)
            else:
                # Shallow: exact match
                return key_path == pattern_path
        except (ValueError, TypeError):
            # Handle path comparison errors
            return str(key_path).startswith(str(pattern_path))