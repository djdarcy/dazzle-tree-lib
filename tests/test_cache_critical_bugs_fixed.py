"""
Test suite validating that critical cache bugs have been FIXED.
These tests should PASS after our fixes are implemented.
For bug demonstration tests that should always fail, see tests/POC/
"""

import asyncio
import time
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
import pytest

from dazzletreelib.aio.adapters.cache_completeness_adapter import (
    CompletenessAwareCacheAdapter as CacheCompletenessAdapter,
    CacheCompleteness,
    CacheEntry
)
from dazzletreelib.aio.caching.adapter import CachingTreeAdapter
from dazzletreelib.aio.adapters.filesystem import AsyncFileSystemAdapter


class TestCacheKeyCollisionFixed:
    """Verify Issue #20 is FIXED: Cache keys no longer collide when stacking adapters."""
    
    @pytest.mark.asyncio
    async def test_no_cache_collision_after_fix(self):
        """Verify stacking adapters no longer causes cache corruption (Issue #20 FIXED)."""
        # Create mock base adapter
        base = AsyncMock(spec=AsyncFileSystemAdapter)
        
        # Mock get_children to return async generator
        async def mock_get_children(path):
            for item in ["file1.txt", "file2.txt"]:
                yield item
        
        base.get_children = mock_get_children
        
        # Stack both cache adapters - this used to be problematic
        caching_adapter = CachingTreeAdapter(base)
        completeness_adapter = CacheCompletenessAdapter(caching_adapter)
        
        path = Path("/test/dir")
        
        # With our fix, each adapter uses unique tuple keys
        # First access through full stack
        children1 = []
        async for child in completeness_adapter.get_children(path):
            children1.append(child)
        
        # Both adapters should have cached with their unique keys
        # Let's verify the keys are different and tuple-based
        
        # Get keys from caching adapter (if it has exposed cache)
        if hasattr(caching_adapter, '_cache'):
            for key in caching_adapter._cache.keys():
                assert isinstance(key, tuple), f"CachingTreeAdapter key should be tuple, got {type(key)}"
                assert len(key) >= 4, f"Key should have at least 4 elements: {key}"
                assert "CachingTreeAdapter" in key[0], f"Key should include class name: {key}"
        
        # Get keys from completeness adapter
        if hasattr(completeness_adapter, 'cache'):
            for key in completeness_adapter.cache.keys():
                assert isinstance(key, tuple), f"CompletenessAwareCacheAdapter key should be tuple, got {type(key)}"
                assert len(key) >= 4, f"Key should have at least 4 elements: {key}"
                assert "CompletenessAwareCacheAdapter" in key[0], f"Key should include class name: {key}"
        
        # Second access should return same data (no corruption)
        children2 = []
        async for child in completeness_adapter.get_children(path):
            children2.append(child)
        
        # Data should be consistent
        assert children1 == children2, "Data should be consistent after caching"
    
    def test_adapters_use_unique_tuple_keys(self):
        """Verify adapters use unique tuple-based cache keys (Issue #20 FIXED)."""
        base = Mock()
        
        caching_adapter = CachingTreeAdapter(base)
        completeness_adapter = CacheCompletenessAdapter(base)
        
        # Create mock node for testing
        from unittest.mock import MagicMock
        node = MagicMock()
        node.path = Path("/test/path")
        
        # Get cache keys from both adapters
        caching_key = caching_adapter._get_cache_key(node)
        completeness_key = completeness_adapter._get_cache_key(Path("/test/path"), depth=5)
        
        # After fix: keys should be different tuples
        assert isinstance(caching_key, tuple), f"CachingTreeAdapter should use tuple keys, got {type(caching_key)}"
        assert isinstance(completeness_key, tuple), f"CompletenessAwareCacheAdapter should use tuple keys, got {type(completeness_key)}"
        assert caching_key != completeness_key, f"Keys should be unique: {caching_key} vs {completeness_key}"
        
        # Verify structure includes class identifier and instance number
        assert "CachingTreeAdapter" in caching_key[0], "Key should include class name"
        assert "CompletenessAwareCacheAdapter" in completeness_key[0], "Key should include class name"
        assert isinstance(caching_key[1], int), "Key should include instance number"
        assert isinstance(completeness_key[1], int), "Key should include instance number"
    
    def test_multiple_instances_have_unique_keys(self):
        """Verify multiple instances of same adapter have unique keys."""
        base = Mock()
        
        # Create multiple instances of same adapter type
        adapter1 = CachingTreeAdapter(base)
        adapter2 = CachingTreeAdapter(base)
        
        # Create mock node
        from unittest.mock import MagicMock
        node = MagicMock()
        node.path = Path("/test")
        
        # Get keys from both instances
        key1 = adapter1._get_cache_key(node)
        key2 = adapter2._get_cache_key(node)
        
        # Keys should be different due to instance numbers
        assert key1 != key2, f"Different instances should have different keys: {key1} vs {key2}"
        
        # Verify instance numbers are different
        assert key1[1] != key2[1], f"Instance numbers should differ: {key1[1]} vs {key2[1]}"
        
        # But class identifiers should be same
        assert key1[0] == key2[0], "Class identifiers should be same for same class"
    
    @pytest.mark.asyncio
    async def test_triple_stacking_works(self):
        """Verify even triple stacking works without collision."""
        base = AsyncMock()
        
        # Mock get_children to return async generator
        async def mock_get_children(path):
            for item in ["test.txt"]:
                yield item
        
        base.get_children = mock_get_children
        
        # Stack three cache adapters
        cache1 = CachingTreeAdapter(base)
        cache2 = CachingTreeAdapter(cache1)
        cache3 = CacheCompletenessAdapter(cache2)
        
        # All three should work without collision
        path = Path("/test")
        
        result = []
        async for item in cache3.get_children(path):
            result.append(item)
        
        assert result == ["test.txt"], "Triple stacking should work correctly"
        
        # Verify each has unique cache keys
        if hasattr(cache1, '_instance_number') and hasattr(cache2, '_instance_number'):
            assert cache1._instance_number != cache2._instance_number, "Each instance should be unique"


class TestDepthLimitFixed:
    """Verify Issue #17 is FIXED: Cache supports unlimited depth."""
    
    def test_depth_beyond_5_works(self):
        """Cache now works at any depth (Issue #17 FIXED)."""
        from dazzletreelib.aio.adapters.cache_completeness_adapter import CacheEntry
        
        # Test depths that failed with enum
        test_depths = [6, 10, 20, 50, 100]
        
        for depth in test_depths:
            entry = CacheEntry([], depth=depth)
            assert entry.depth == depth
            assert entry.satisfies(depth - 1)
            
        # Issue #17 is FIXED!


class TestCacheInvalidationFixed:
    """Verify Issue #18 is FIXED: Cache entries now track mtime."""
    
    def test_cache_entry_still_has_no_mtime_field(self):
        """CacheEntry now DOES track mtime for validation (Issue #18 FIXED!)."""
        # Check if CacheEntry has mtime field
        entry = CacheEntry(data=[], depth=2)  # depth=2 is equivalent to PARTIAL_2
        
        # This demonstrates the bug is FIXED!
        assert hasattr(entry, 'mtime'), \
            "Issue #18 FIXED: CacheEntry now has mtime field"


if __name__ == "__main__":
    # Run tests to verify our fixes work
    pytest.main([__file__, "-v", "--tb=short"])