"""
Test suite verifying cache collision prevention with tuple-based keys.
These tests should PASS after implementing the fix for Issue #20.
"""

import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock
import pytest

from dazzletreelib.aio.adapters.cache_completeness_adapter import (
    CompletenessAwareCacheAdapter as CacheCompletenessAdapter,
    CacheCompleteness,
    CacheEntry
)
from dazzletreelib.aio.caching.adapter import CachingTreeAdapter
from dazzletreelib.aio.adapters.filesystem import AsyncFileSystemAdapter
from dazzletreelib.aio.core import AsyncTreeNode


class MockNode:
    """Mock node for testing."""
    def __init__(self, path):
        self.path = path


class TestCacheKeyUniqueness:
    """Test that cache keys are unique across adapters and instances."""
    
    def test_different_adapter_types_have_different_keys(self):
        """Different adapter types generate different cache keys."""
        base = Mock()
        
        caching_adapter = CachingTreeAdapter(base)
        completeness_adapter = CacheCompletenessAdapter(base)
        
        # Same path but different adapters
        path = Path("/test/path")
        node = MockNode(path)
        
        key1 = caching_adapter._get_cache_key(node)
        key2 = completeness_adapter._get_cache_key(path, depth=5)
        
        # Keys must be different
        assert key1 != key2, f"Keys should differ: {key1} vs {key2}"
        
        # Keys should be tuples
        assert isinstance(key1, tuple), "CachingTreeAdapter should return tuple key"
        assert isinstance(key2, tuple), "CacheCompletenessAdapter should return tuple key"
        
        # Keys should contain class names
        assert "CachingTreeAdapter" in key1[0]
        assert "CompletenessAwareCacheAdapter" in key2[0]
    
    def test_same_adapter_different_instances_have_different_keys(self):
        """Multiple instances of same adapter type have different keys."""
        base = Mock()
        
        # Two instances of same adapter class
        adapter1 = CachingTreeAdapter(base)
        adapter2 = CachingTreeAdapter(base)
        
        path = Path("/test/path")
        node = MockNode(path)
        
        key1 = adapter1._get_cache_key(node)
        key2 = adapter2._get_cache_key(node)
        
        # Keys must be different due to instance numbers
        assert key1 != key2, "Different instances should have different keys"
        
        # Instance numbers should differ
        assert key1[1] != key2[1], f"Instance numbers should differ: {key1[1]} vs {key2[1]}"
    
    def test_cache_key_structure(self):
        """Verify cache key structure matches specification."""
        base = Mock()
        adapter = CachingTreeAdapter(base)
        
        path = Path("/test/path")
        node = MockNode(path)
        
        key = adapter._get_cache_key(node)
        
        # Verify tuple structure: (class_id, instance_num, key_type, path)
        assert len(key) == 4, f"Key should have 4 elements, got {len(key)}"
        assert isinstance(key[0], str), "First element should be class ID string"
        assert isinstance(key[1], int), "Second element should be instance number"
        assert key[2] == "node_data", "Third element should be key type"
        assert str(path) in key[3], "Fourth element should contain path"
    
    def test_completeness_adapter_key_includes_depth(self):
        """CacheCompletenessAdapter keys include depth specification."""
        base = Mock()
        adapter = CacheCompletenessAdapter(base)
        
        path = Path("/test/path")
        
        # Keys with different depths
        key_depth_5 = adapter._get_cache_key(path, depth=5)
        key_depth_10 = adapter._get_cache_key(path, depth=10)
        key_complete = adapter._get_cache_key(path, depth=None)
        
        # All keys should be different
        assert key_depth_5 != key_depth_10
        assert key_depth_5 != key_complete
        assert key_depth_10 != key_complete
        
        # Verify depth is in key
        assert "5" in key_depth_5[-1]
        assert "10" in key_depth_10[-1]
        assert "complete" in key_complete[-1]


class TestCacheStackingWithoutCollision:
    """Test that stacked adapters don't have cache collisions."""
    
    @pytest.mark.asyncio
    async def test_stacked_adapters_no_collision(self):
        """Stacking adapters doesn't cause cache collision."""
        # Create mock base adapter
        base = AsyncMock(spec=AsyncFileSystemAdapter)
        base.get_children = AsyncMock(return_value=[])
        
        # Stack adapters - this was the problematic pattern
        caching = CachingTreeAdapter(base)
        completeness = CacheCompletenessAdapter(caching)
        
        path = Path("/test/dir")
        
        # Generate keys for same path
        node = MockNode(path)
        key1 = caching._get_cache_key(node)
        key2 = completeness._get_cache_key(path, depth=5)
        
        # Keys must be completely different
        assert key1 != key2, "Stacked adapters must have different cache keys"
        
        # No element should be identical (except possibly the path)
        for i in range(min(len(key1), len(key2))):
            if i == 3:  # Path element might be same
                continue
            assert key1[i] != key2[i] or i == 3, \
                f"Element {i} shouldn't match: {key1[i]} vs {key2[i]}"
    
    @pytest.mark.asyncio
    async def test_triple_stacking_unique_keys(self):
        """Even triple stacking maintains unique keys."""
        base = AsyncMock(spec=AsyncFileSystemAdapter)
        
        # Triple stacking
        adapter1 = CachingTreeAdapter(base)
        adapter2 = CacheCompletenessAdapter(adapter1)
        adapter3 = CachingTreeAdapter(adapter2)  # Another caching layer!
        
        path = Path("/test")
        node = MockNode(path)
        
        key1 = adapter1._get_cache_key(node)
        key2 = adapter2._get_cache_key(path, depth=5)
        key3 = adapter3._get_cache_key(node)
        
        # All keys must be unique
        assert key1 != key2
        assert key1 != key3
        assert key2 != key3
        
        # Verify all three are different instances
        assert len({key1, key2, key3}) == 3, "All three keys should be unique"


class TestDeterministicInstanceNumbers:
    """Test that instance numbers are deterministic and sequential."""
    
    def test_instance_numbers_are_sequential(self):
        """Instance numbers increment sequentially."""
        base = Mock()
        
        # Create multiple instances
        adapters = [CachingTreeAdapter(base) for _ in range(5)]
        
        node = MockNode(Path("/test"))
        keys = [adapter._get_cache_key(node) for adapter in adapters]
        
        # Extract instance numbers
        instance_numbers = [key[1] for key in keys]
        
        # Should be sequential
        for i in range(1, len(instance_numbers)):
            assert instance_numbers[i] > instance_numbers[i-1], \
                f"Instance numbers should increase: {instance_numbers}"
    
    def test_different_classes_have_independent_counters(self):
        """Different adapter classes have independent instance counters."""
        base = Mock()
        
        # Alternate creating different adapter types
        caching1 = CachingTreeAdapter(base)
        complete1 = CacheCompletenessAdapter(base)
        caching2 = CachingTreeAdapter(base)
        complete2 = CacheCompletenessAdapter(base)
        
        node = MockNode(Path("/test"))
        path = Path("/test")
        
        # Get instance numbers
        caching1_num = caching1._get_cache_key(node)[1]
        caching2_num = caching2._get_cache_key(node)[1]
        complete1_num = complete1._get_cache_key(path)[1]
        complete2_num = complete2._get_cache_key(path)[1]
        
        # Each class should have its own counter
        assert caching2_num > caching1_num, "CachingTreeAdapter counter should increment"
        assert complete2_num > complete1_num, "CacheCompletenessAdapter counter should increment"


class TestCacheKeyPrefix:
    """Test the CacheKeyMixin functionality."""
    
    def test_cache_key_prefix_format(self):
        """Cache key prefix has correct format."""
        base = Mock()
        adapter = CachingTreeAdapter(base)
        
        prefix = adapter._get_cache_key_prefix()
        
        # Should be (class_id, instance_number)
        assert len(prefix) == 2
        assert isinstance(prefix[0], str)
        assert isinstance(prefix[1], int)
        
        # Class ID should contain module and class name
        assert "dazzletreelib" in prefix[0]
        assert "CachingTreeAdapter" in prefix[0]
    
    def test_cache_key_prefix_unique_per_instance(self):
        """Each instance has unique cache key prefix."""
        base = Mock()
        
        adapter1 = CachingTreeAdapter(base)
        adapter2 = CachingTreeAdapter(base)
        
        prefix1 = adapter1._get_cache_key_prefix()
        prefix2 = adapter2._get_cache_key_prefix()
        
        # Prefixes must be different
        assert prefix1 != prefix2
        
        # Class ID should be same, instance number different
        assert prefix1[0] == prefix2[0], "Same class should have same class ID"
        assert prefix1[1] != prefix2[1], "Different instances should have different numbers"


if __name__ == "__main__":
    # Run tests to verify cache collision prevention
    pytest.main([__file__, "-v", "--tb=short"])