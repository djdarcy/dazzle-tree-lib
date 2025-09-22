"""
Tests for _LruCacheStore - the extracted cache storage implementation.

This test suite ensures the cache store correctly handles:
- Basic get/put operations
- LRU eviction
- Memory limits
- Fast mode (unbounded)
- Cache invalidation
- Statistics tracking
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, MagicMock
from collections import OrderedDict

# Import will be: from dazzletreelib.aio.adapters._cache_store import _LruCacheStore
# For now, we'll define what we expect the interface to be


class CacheEntry:
    """Mock CacheEntry for testing."""
    COMPLETE_DEPTH = -1

    def __init__(self, data, depth=1, size_estimate=100):
        self.data = data
        self.depth = depth
        self.size_estimate = size_estimate
        self.access_count = 0
        self.last_access = time.time()
        self.created_at = time.time()


class TestLruCacheStoreBasics:
    """Test basic cache operations."""

    def test_init_safe_mode(self):
        """Test initialization with safe mode (protection enabled)."""
        # This will fail until we implement _LruCacheStore
        from dazzletreelib.aio.adapters._cache_store import _LruCacheStore

        store = _LruCacheStore(
            enable_protection=True,
            max_memory_mb=100,
            max_entries=1000
        )

        assert store.enable_protection is True
        assert store.max_memory == 100 * 1024 * 1024
        assert store.max_entries == 1000
        assert store.current_memory == 0
        assert len(store.cache) == 0

    def test_init_fast_mode(self):
        """Test initialization with fast mode (protection disabled)."""
        from dazzletreelib.aio.adapters._cache_store import _LruCacheStore

        store = _LruCacheStore(enable_protection=False)

        assert store.enable_protection is False
        assert store.current_memory == 0
        assert len(store.cache) == 0
        # In fast mode, limits should be effectively infinite
        assert store.max_memory == float('inf')
        assert store.max_entries == float('inf')

    def test_basic_put_get(self):
        """Test basic put and get operations."""
        from dazzletreelib.aio.adapters._cache_store import _LruCacheStore

        store = _LruCacheStore()
        key = ("path/to/node", 2)  # (path, depth) tuple
        entry = CacheEntry(["child1", "child2"], depth=2)

        # Put entry
        success = store.put(key, entry)
        assert success is True

        # Get entry
        retrieved = store.get(key)
        assert retrieved is entry
        assert retrieved.data == ["child1", "child2"]

    def test_get_nonexistent(self):
        """Test getting a non-existent key returns None."""
        from dazzletreelib.aio.adapters._cache_store import _LruCacheStore

        store = _LruCacheStore()
        result = store.get(("nonexistent", 1))
        assert result is None

    def test_clear(self):
        """Test clearing the cache."""
        from dazzletreelib.aio.adapters._cache_store import _LruCacheStore

        store = _LruCacheStore()

        # Add some entries
        store.put(("path1", 1), CacheEntry([], depth=1))
        store.put(("path2", 2), CacheEntry([], depth=2))
        assert len(store.cache) == 2

        # Clear
        store.clear()
        assert len(store.cache) == 0
        assert store.current_memory == 0


class TestLruEviction:
    """Test LRU eviction behavior."""

    def test_lru_order_on_get(self):
        """Test that getting an entry moves it to the end (most recent)."""
        from dazzletreelib.aio.adapters._cache_store import _LruCacheStore

        store = _LruCacheStore(enable_protection=True)

        # Add entries in order
        store.put(("path1", 1), CacheEntry([], depth=1))
        store.put(("path2", 1), CacheEntry([], depth=1))
        store.put(("path3", 1), CacheEntry([], depth=1))

        # Access path1 (should move to end)
        store.get(("path1", 1))

        # Check order (path2 should be first/oldest, path1 last/newest)
        keys = list(store.cache.keys())
        assert keys[0] == ("path2", 1)
        assert keys[-1] == ("path1", 1)

    def test_eviction_by_entry_count(self):
        """Test eviction when max entries exceeded."""
        from dazzletreelib.aio.adapters._cache_store import _LruCacheStore

        store = _LruCacheStore(
            enable_protection=True,
            max_entries=3
        )

        # Add 3 entries (at capacity)
        store.put(("path1", 1), CacheEntry([], depth=1, size_estimate=100))
        store.put(("path2", 1), CacheEntry([], depth=1, size_estimate=100))
        store.put(("path3", 1), CacheEntry([], depth=1, size_estimate=100))
        assert len(store.cache) == 3

        # Add 4th entry (should evict path1)
        store.put(("path4", 1), CacheEntry([], depth=1, size_estimate=100))
        assert len(store.cache) == 3
        assert ("path1", 1) not in store.cache
        assert ("path4", 1) in store.cache

    def test_eviction_by_memory_limit(self):
        """Test eviction when memory limit exceeded."""
        from dazzletreelib.aio.adapters._cache_store import _LruCacheStore

        # Small memory limit: 400 bytes exactly
        store = _LruCacheStore(
            enable_protection=True,
            max_memory_mb=400 / (1024 * 1024)  # Exactly 400 bytes
        )

        # Add entries with 200 bytes each
        store.put(("path1", 1), CacheEntry([], depth=1, size_estimate=200))
        store.put(("path2", 1), CacheEntry([], depth=1, size_estimate=200))
        assert len(store.cache) == 2
        assert store.current_memory == 400

        # Add 3rd entry (should trigger eviction of path1)
        store.put(("path3", 1), CacheEntry([], depth=1, size_estimate=200))
        assert len(store.cache) == 2
        assert ("path1", 1) not in store.cache
        assert store.current_memory == 400

    def test_no_eviction_in_fast_mode(self):
        """Test that fast mode never evicts."""
        from dazzletreelib.aio.adapters._cache_store import _LruCacheStore

        store = _LruCacheStore(enable_protection=False)

        # Add many large entries
        for i in range(1000):
            store.put(
                (f"path{i}", 1),
                CacheEntry([], depth=1, size_estimate=1000000)  # 1MB each
            )

        # All should be retained (no eviction)
        assert len(store.cache) == 1000


class TestCacheInvalidation:
    """Test cache invalidation patterns."""

    def test_invalidate_single_entry(self):
        """Test invalidating a single cache entry."""
        from dazzletreelib.aio.adapters._cache_store import _LruCacheStore

        store = _LruCacheStore()

        # Add entries
        store.put(("/root/dir1", 1), CacheEntry([], depth=1))
        store.put(("/root/dir2", 1), CacheEntry([], depth=1))
        assert len(store.cache) == 2

        # Invalidate one
        count = store.invalidate("/root/dir1")
        assert count == 1
        assert ("/root/dir1", 1) not in store.cache
        assert ("/root/dir2", 1) in store.cache

    def test_invalidate_pattern(self):
        """Test pattern-based invalidation."""
        from dazzletreelib.aio.adapters._cache_store import _LruCacheStore

        store = _LruCacheStore()

        # Add entries with different paths
        store.put(("/root/dir1/file1", 1), CacheEntry([], depth=1))
        store.put(("/root/dir1/file2", 2), CacheEntry([], depth=2))
        store.put(("/root/dir2/file3", 1), CacheEntry([], depth=1))
        store.put(("/other/file4", 1), CacheEntry([], depth=1))

        # Invalidate pattern
        count = store.invalidate("/root/dir1", deep=True)
        assert count == 2
        assert ("/root/dir1/file1", 1) not in store.cache
        assert ("/root/dir1/file2", 2) not in store.cache
        assert ("/root/dir2/file3", 1) in store.cache
        assert ("/other/file4", 1) in store.cache

    def test_invalidate_all(self):
        """Test invalidating all entries."""
        from dazzletreelib.aio.adapters._cache_store import _LruCacheStore

        store = _LruCacheStore()

        # Add entries
        store.put(("path1", 1), CacheEntry([], depth=1))
        store.put(("path2", 2), CacheEntry([], depth=2))
        store.put(("path3", 3), CacheEntry([], depth=3))

        # Invalidate all (no pattern)
        count = store.invalidate()
        assert count == 3
        assert len(store.cache) == 0


class TestCacheStatistics:
    """Test cache statistics tracking."""

    def test_basic_stats(self):
        """Test basic statistics."""
        from dazzletreelib.aio.adapters._cache_store import _LruCacheStore

        store = _LruCacheStore()

        # Add some entries
        store.put(("path1", 1), CacheEntry([], depth=1, size_estimate=1000))
        store.put(("path2", 2), CacheEntry([], depth=2, size_estimate=2000))

        stats = store.get_stats()
        assert stats['entries'] == 2
        assert stats['memory_mb'] == pytest.approx(3000 / (1024 * 1024), rel=0.01)

    def test_hit_rate_tracking(self):
        """Test hit rate calculation."""
        from dazzletreelib.aio.adapters._cache_store import _LruCacheStore

        store = _LruCacheStore()
        store.hits = 0  # Initialize counter
        store.misses = 0

        # Add entry
        store.put(("path1", 1), CacheEntry([], depth=1))

        # Hits
        store.get(("path1", 1))
        store.hits += 1
        store.get(("path1", 1))
        store.hits += 1

        # Misses
        store.get(("nonexistent", 1))
        store.misses += 1

        stats = store.get_stats()
        # 2 hits, 1 miss = 66.7% hit rate
        assert stats.get('hit_rate', 0) == pytest.approx(0.667, rel=0.01)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_oversized_entry(self):
        """Test that oversized entries are rejected."""
        from dazzletreelib.aio.adapters._cache_store import _LruCacheStore

        # 1MB limit
        store = _LruCacheStore(
            enable_protection=True,
            max_memory_mb=1
        )

        # Try to add 2MB entry (should be rejected)
        huge_entry = CacheEntry([], depth=1, size_estimate=2 * 1024 * 1024)
        success = store.put(("huge", 1), huge_entry)
        assert success is False
        assert len(store.cache) == 0

    def test_deep_path_limit(self):
        """Test that very deep paths are rejected when limits are set."""
        from dazzletreelib.aio.adapters._cache_store import _LruCacheStore

        store = _LruCacheStore(
            enable_protection=True,
            max_path_depth=3
        )

        # Create a deep path
        deep_path = "/level1/level2/level3/level4/level5"
        entry = CacheEntry([], depth=1)

        # Should be rejected due to path depth
        success = store.put((deep_path, 1), entry)
        assert success is False

    def test_cache_depth_limit(self):
        """Test that entries beyond cache depth limit are rejected."""
        from dazzletreelib.aio.adapters._cache_store import _LruCacheStore

        store = _LruCacheStore(
            enable_protection=True,
            max_cache_depth=5
        )

        # Entry at depth 10 (beyond limit)
        entry = CacheEntry([], depth=10)
        success = store.put(("path", 10), entry)
        assert success is False

    def test_memory_tracking_accuracy(self):
        """Test that memory tracking remains accurate through operations."""
        from dazzletreelib.aio.adapters._cache_store import _LruCacheStore

        store = _LruCacheStore(enable_protection=True)

        # Add entries
        store.put(("path1", 1), CacheEntry([], size_estimate=1000))
        assert store.current_memory == 1000

        store.put(("path2", 1), CacheEntry([], size_estimate=2000))
        assert store.current_memory == 3000

        # Replace an entry (should update memory)
        store.put(("path1", 1), CacheEntry([], size_estimate=500))
        assert store.current_memory == 2500

        # Clear
        store.clear()
        assert store.current_memory == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])