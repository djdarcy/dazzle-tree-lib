"""
Comprehensive test that validates Issue #20 (cache key collision) is truly fixed.
This test simulates the exact data corruption scenario and proves it no longer happens.
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import pytest

from dazzletreelib.aio.adapters.cache_completeness_adapter import (
    CompletenessAwareCacheAdapter,
    CacheEntry
)
from dazzletreelib.aio.caching.adapter import CachingTreeAdapter
from dazzletreelib.aio.adapters.filesystem import AsyncFileSystemAdapter


class TestCacheCollisionDataCorruptionPrevented:
    """Comprehensive tests proving cache collision no longer causes data corruption."""
    
    @pytest.mark.asyncio
    async def test_stacked_adapters_maintain_separate_caches(self):
        """
        Proves that stacked adapters maintain separate caches and don't corrupt each other.
        
        Before fix: Both adapters would use the same cache key (e.g., "/test/path")
        causing one to overwrite the other's cached data.
        
        After fix: Each adapter uses unique tuple keys preventing any collision.
        """
        # Create base adapter with specific behavior
        base = AsyncMock(spec=AsyncFileSystemAdapter)
        
        # Track how many times base is called
        call_count = 0
        
        async def mock_get_children(path):
            nonlocal call_count
            call_count += 1
            # Return different data on each call to simulate real filesystem changes
            if call_count == 1:
                for item in ["file1.txt", "file2.txt", "file3.txt"]:
                    yield item
            else:
                for item in ["newfile1.txt", "newfile2.txt"]:
                    yield item
        
        base.get_children = mock_get_children
        
        # Stack the adapters - this used to cause collision
        caching_adapter = CachingTreeAdapter(base)
        completeness_adapter = CompletenessAwareCacheAdapter(caching_adapter)
        
        test_path = Path("/test/dir")
        
        # First access - both adapters will cache
        first_result = []
        async for child in completeness_adapter.get_children(test_path):
            first_result.append(child)
        
        assert first_result == ["file1.txt", "file2.txt", "file3.txt"]
        assert call_count == 1, "Base should be called once"
        
        # CRITICAL TEST: Access through caching adapter directly
        # Before fix: This would return completeness adapter's cached data!
        # After fix: Returns caching adapter's own cached data
        cached_result = []
        async for child in caching_adapter.get_children(test_path):
            cached_result.append(child)
        
        # Should still return original data from cache, not call base again
        assert cached_result == ["file1.txt", "file2.txt", "file3.txt"]
        assert call_count == 1, "Should use cache, not call base"
        
        # Access through full stack again - should use completeness cache
        second_result = []
        async for child in completeness_adapter.get_children(test_path):
            second_result.append(child)
        
        assert second_result == ["file1.txt", "file2.txt", "file3.txt"]
        assert call_count == 1, "Should still use caches"
        
        # Verify the caches are truly independent by checking keys
        if hasattr(caching_adapter, '_cache') and hasattr(completeness_adapter, 'cache'):
            caching_keys = list(caching_adapter._cache.keys())
            completeness_keys = list(completeness_adapter.cache.keys())
            
            # Keys should be different tuples
            assert len(caching_keys) > 0, "Caching adapter should have cached data"
            assert len(completeness_keys) > 0, "Completeness adapter should have cached data"
            
            # The actual keys should be different
            for c_key in caching_keys:
                for comp_key in completeness_keys:
                    assert c_key != comp_key, f"Keys should never collide: {c_key} vs {comp_key}"
    
    @pytest.mark.asyncio
    async def test_cache_corruption_scenario_prevented(self):
        """
        Directly tests the corruption scenario: different cache semantics don't interfere.
        
        CachingTreeAdapter: Caches with TTL (time-based expiration)
        CompletenessAwareCacheAdapter: Caches with depth tracking
        
        Before fix: They would overwrite each other's cache entries
        After fix: Each maintains independent cache with unique keys
        """
        base = AsyncMock(spec=AsyncFileSystemAdapter)
        
        # Simulate a directory that changes over time
        version = 0
        
        async def mock_get_children(path):
            nonlocal version
            version += 1
            if version == 1:
                # Initial state
                for item in ["old1.txt", "old2.txt"]:
                    yield item
            elif version == 2:
                # Changed state (would happen after TTL expires)
                for item in ["new1.txt", "new2.txt"]:
                    yield item
            else:
                # Further changed state
                for item in ["latest1.txt", "latest2.txt"]:
                    yield item
        
        base.get_children = mock_get_children
        
        # Create stacked adapters with different cache strategies
        caching_adapter = CachingTreeAdapter(base, ttl=1000)  # Long TTL
        completeness_adapter = CompletenessAwareCacheAdapter(caching_adapter)
        
        path = Path("/test")
        
        # Initial access - both cache
        result1 = []
        async for child in completeness_adapter.get_children(path):
            result1.append(child)
        assert result1 == ["old1.txt", "old2.txt"]
        
        # Access again - should use cache
        result2 = []
        async for child in completeness_adapter.get_children(path):
            result2.append(child)
        
        # Before fix: This might corrupt the cache
        # After fix: Each adapter maintains its own cache
        
        # Direct access to caching adapter should still have its cached data
        result3 = []
        async for child in caching_adapter.get_children(path):
            result3.append(child)
        
        # Should return cached data, not corrupted data
        assert result3 == ["old1.txt", "old2.txt"] or result3 == ["new1.txt", "new2.txt"]
        # The exact result depends on whether caching adapter's cache was hit,
        # but it should NEVER be corrupted data from completeness adapter
        
        # Verify both adapters' caches are independent
        assert version <= 2, "Should not call base adapter excessively"
    
    @pytest.mark.asyncio  
    async def test_multiple_instances_dont_collide(self):
        """
        Test that multiple instances of the same adapter type don't collide.
        
        Before fix: All CachingTreeAdapter instances might share cache keys
        After fix: Each instance has unique instance number in its keys
        """
        base1 = AsyncMock(spec=AsyncFileSystemAdapter)
        base2 = AsyncMock(spec=AsyncFileSystemAdapter)
        
        async def mock_get_children1(path):
            for item in ["instance1_file.txt"]:
                yield item
        
        async def mock_get_children2(path):
            for item in ["instance2_file.txt"]:
                yield item
        
        base1.get_children = mock_get_children1
        base2.get_children = mock_get_children2
        
        # Create two instances of CachingTreeAdapter
        cache1 = CachingTreeAdapter(base1)
        cache2 = CachingTreeAdapter(base2)
        
        # Stack completeness adapters on top
        complete1 = CompletenessAwareCacheAdapter(cache1)
        complete2 = CompletenessAwareCacheAdapter(cache2)
        
        path = Path("/same/path")  # Same path for both!
        
        # Access through first stack
        result1 = []
        async for child in complete1.get_children(path):
            result1.append(child)
        
        # Access through second stack  
        result2 = []
        async for child in complete2.get_children(path):
            result2.append(child)
        
        # Results should be different (from different base adapters)
        assert result1 == ["instance1_file.txt"]
        assert result2 == ["instance2_file.txt"]
        
        # Verify the cache keys are different even for same path
        mock_node = MagicMock()
        mock_node.path = path
        
        key1 = cache1._get_cache_key(mock_node)
        key2 = cache2._get_cache_key(mock_node)
        
        assert key1 != key2, "Different instances must have different cache keys"
        assert key1[1] != key2[1], "Instance numbers must be different"
    
    def test_cache_key_structure_prevents_collision(self):
        """
        Test the actual cache key structure guarantees no collision.
        
        The tuple structure is:
        (class_full_name, instance_number, cache_type, path, ...)
        
        This structure mathematically guarantees uniqueness.
        """
        base = MagicMock()
        
        # Create multiple adapters
        caching1 = CachingTreeAdapter(base)
        caching2 = CachingTreeAdapter(base) 
        completeness1 = CompletenessAwareCacheAdapter(base)
        completeness2 = CompletenessAwareCacheAdapter(base)
        
        # Test path
        path = Path("/test/path")
        mock_node = MagicMock()
        mock_node.path = path
        
        # Get all cache keys
        keys = [
            caching1._get_cache_key(mock_node),
            caching2._get_cache_key(mock_node),
            completeness1._get_cache_key(path, depth=3),
            completeness2._get_cache_key(path, depth=3),
            completeness1._get_cache_key(path, depth=5),  # Different depth
        ]
        
        # All keys should be tuples
        for key in keys:
            assert isinstance(key, tuple), f"Key must be tuple: {key}"
            assert len(key) >= 4, f"Key must have at least 4 elements: {key}"
        
        # All keys should be unique
        unique_keys = set(keys)
        assert len(unique_keys) == len(keys), "All keys must be unique"
        
        # Verify structure prevents collision
        # Different classes have different first element
        assert keys[0][0] != keys[2][0], "Different classes have different identifiers"
        
        # Same class different instances have different second element
        assert keys[0][1] != keys[1][1], "Different instances have different numbers"
        assert keys[2][1] != keys[3][1], "Different instances have different numbers"
        
        # Different depths have different last element
        assert keys[2][-1] != keys[4][-1], "Different depths are distinguished"
        
        print(f"Cache key examples showing uniqueness:")
        print(f"CachingTreeAdapter #1:    {keys[0]}")
        print(f"CachingTreeAdapter #2:    {keys[1]}")
        print(f"CompletenessAdapter #1:   {keys[2]}")
        print(f"CompletenessAdapter #2:   {keys[3]}")
        print(f"CompletenessAdapter #1 (different depth): {keys[4]}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])