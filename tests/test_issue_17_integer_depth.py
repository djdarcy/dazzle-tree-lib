"""
Test Issue #17 fix: Integer-based depth tracking instead of enum.

This validates that the cache system now supports unlimited depth
using integer values with -1 as a sentinel for complete scans.
"""

import pytest
from pathlib import Path

from dazzletreelib.aio.adapters.cache_completeness_adapter import (
    CacheEntry,
    CompletenessAwareCacheAdapter
)


class TestIntegerDepthTracking:
    """Test that cache uses integer depths instead of enum."""
    
    def test_depth_constants(self):
        """Verify depth constants are properly defined."""
        assert CacheEntry.COMPLETE_DEPTH == -1
        assert CacheEntry.MAX_DEPTH == 100
    
    def test_valid_depths(self):
        """Test creating entries with valid depths."""
        # Complete scan
        entry = CacheEntry([], depth=-1)
        assert entry.depth == -1
        
        # Root only
        entry = CacheEntry([], depth=0)
        assert entry.depth == 0
        
        # Shallow scan
        entry = CacheEntry([], depth=1)
        assert entry.depth == 1
        
        # Deep scan
        entry = CacheEntry([], depth=50)
        assert entry.depth == 50
        
        # At limit
        entry = CacheEntry([], depth=100)
        assert entry.depth == 100
    
    def test_invalid_depths(self):
        """Test that invalid depths raise errors."""
        # Negative depth (other than -1)
        with pytest.raises(ValueError, match="Invalid depth -2"):
            CacheEntry([], depth=-2)
        
        # Over limit
        with pytest.raises(ValueError, match="exceeds maximum"):
            CacheEntry([], depth=101)
    
    def test_depth_satisfaction_logic(self):
        """Test that depth satisfaction works correctly."""
        complete = CacheEntry([], depth=-1)
        partial_10 = CacheEntry([], depth=10)
        partial_5 = CacheEntry([], depth=5)
        
        # Complete satisfies everything
        assert complete.satisfies(-1)
        assert complete.satisfies(0)
        assert complete.satisfies(50)
        assert complete.satisfies(100)
        
        # Partial satisfies shallower
        assert partial_10.satisfies(5)
        assert partial_10.satisfies(10)
        assert not partial_10.satisfies(11)
        assert not partial_10.satisfies(-1)
        
        # Shallow doesn't satisfy deep
        assert partial_5.satisfies(0)
        assert partial_5.satisfies(5)
        assert not partial_5.satisfies(10)
    
    def test_configurable_max_depth(self):
        """Test that maximum depth can be configured."""
        # Set new limit
        CacheEntry.set_max_depth(200)
        assert CacheEntry.MAX_DEPTH == 200
        
        # Can now create deeper entries
        entry = CacheEntry([], depth=150)
        assert entry.depth == 150
        
        # But not over new limit
        with pytest.raises(ValueError, match="exceeds maximum 200"):
            CacheEntry([], depth=201)
        
        # Reset for other tests
        CacheEntry.set_max_depth(100)
    
    def test_depths_beyond_old_enum_limit(self):
        """Test that depths > 5 work correctly (old enum limit)."""
        # Old system failed at depth 6+
        test_depths = [6, 7, 10, 20, 50, 100]
        
        for depth in test_depths:
            entry = CacheEntry([], depth=depth)
            assert entry.depth == depth
            
            # Should satisfy shallower requests
            assert entry.satisfies(5)
            assert entry.satisfies(depth - 1)
            assert entry.satisfies(depth)
            
            # Should not satisfy deeper
            assert not entry.satisfies(depth + 1)
            assert not entry.satisfies(-1)
    
    def test_depth_0_is_valid(self):
        """Test that depth 0 (root only) is valid."""
        entry = CacheEntry([], depth=0)
        assert entry.depth == 0
        
        # Satisfies only depth 0
        assert entry.satisfies(0)
        assert not entry.satisfies(1)
        assert not entry.satisfies(-1)
    
    def test_mtime_field_present(self):
        """Test that mtime field exists for future Issue #18."""
        entry = CacheEntry([], depth=5, mtime=1234567890.0)
        assert entry.mtime == 1234567890.0
        
        # Also works without mtime
        entry2 = CacheEntry([], depth=5)
        assert entry2.mtime is None
    
    def test_cache_key_includes_depth(self):
        """Test that cache keys include the depth value."""
        from unittest.mock import Mock
        
        base = Mock()
        adapter = CompletenessAwareCacheAdapter(base)
        
        # Get cache keys for different depths
        key_complete = adapter._get_cache_key(Path("/test"), -1)
        key_5 = adapter._get_cache_key(Path("/test"), 5)
        key_10 = adapter._get_cache_key(Path("/test"), 10)
        
        # All should be tuples
        assert isinstance(key_complete, tuple)
        assert isinstance(key_5, tuple)
        assert isinstance(key_10, tuple)
        
        # Last element should be the depth
        assert key_complete[-1] == -1
        assert key_5[-1] == 5
        assert key_10[-1] == 10
        
        # Keys should be different
        assert key_complete != key_5
        assert key_5 != key_10


class TestCacheAdapterWithIntegerDepth:
    """Test the cache adapter with integer depths."""
    
    @pytest.mark.asyncio
    async def test_adapter_accepts_max_depth(self):
        """Test that adapter can be configured with max depth."""
        from unittest.mock import AsyncMock
        
        base = AsyncMock()
        
        # Default max depth
        adapter1 = CompletenessAwareCacheAdapter(base)
        assert CacheEntry.MAX_DEPTH == 100
        
        # Custom max depth
        adapter2 = CompletenessAwareCacheAdapter(base, max_depth=200)
        assert CacheEntry.MAX_DEPTH == 200
        
        # Reset
        CacheEntry.MAX_DEPTH = 100
    
    @pytest.mark.asyncio
    async def test_cache_depth_satisfaction(self):
        """Test that cache correctly satisfies depth requirements."""
        from unittest.mock import AsyncMock
        
        base = AsyncMock()
        adapter = CompletenessAwareCacheAdapter(base)
        
        # Manually add a deep cache entry
        cache_key = adapter._get_cache_key(Path("/test"), 10)
        adapter.cache[cache_key] = CacheEntry(["file1", "file2"], depth=10)
        
        # Should satisfy shallower request
        result, was_cached = await adapter.get_children_at_depth(Path("/test"), depth=5)
        assert was_cached
        assert adapter.hits == 1
        
        # Should not satisfy deeper request
        result, was_cached = await adapter.get_children_at_depth(Path("/test"), depth=15)
        assert not was_cached
        assert adapter.misses == 1
    
    def test_stats_tracking(self):
        """Test that statistics are properly tracked."""
        from unittest.mock import Mock
        
        base = Mock()
        adapter = CompletenessAwareCacheAdapter(base)
        
        # Initial stats
        stats = adapter.get_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["entries"] == 0
        
        # Add some entries
        adapter.cache[("key1",)] = CacheEntry([], depth=5)
        adapter.hits = 10
        adapter.misses = 5
        
        stats = adapter.get_stats()
        assert stats["hits"] == 10
        assert stats["misses"] == 5
        assert stats["hit_rate"] == 10 / 15
        assert stats["entries"] == 1


class TestMigrationFromEnum:
    """Test migration path from enum-based system."""
    
    def test_depth_mapping(self):
        """Test mapping old enum values to integer depths."""
        # Old enum values mapped to integers
        mapping = {
            0: 0,    # NONE -> 0
            1: 1,    # SHALLOW -> 1
            2: 2,    # PARTIAL_2 -> 2
            3: 3,    # PARTIAL_3 -> 3
            4: 4,    # PARTIAL_4 -> 4
            5: 5,    # PARTIAL_5 -> 5
            999: -1, # COMPLETE -> -1
        }
        
        for old_value, new_depth in mapping.items():
            if old_value == 999:
                # Complete scan
                entry = CacheEntry([], depth=new_depth)
                assert entry.depth == -1
                assert entry.satisfies(100)  # Satisfies any depth
            else:
                # Specific depth
                entry = CacheEntry([], depth=new_depth)
                assert entry.depth == new_depth
    
    def test_backward_compatibility_enum_exists(self):
        """Verify CacheCompleteness exists for backward compatibility but is deprecated."""
        from dazzletreelib.aio.adapters.cache_completeness_adapter import CacheCompleteness
        # Should be able to import it for backward compatibility
        assert hasattr(CacheCompleteness, 'SHALLOW')
        assert hasattr(CacheCompleteness, 'PARTIAL_2')
        assert hasattr(CacheCompleteness, 'COMPLETE')
        # Check it's marked as deprecated in docstring
        assert "Deprecated" in CacheCompleteness.__doc__ or "backward compatibility" in CacheCompleteness.__doc__.lower()
    
    def test_can_import_cache_entry(self):
        """Verify CacheEntry can be imported."""
        from dazzletreelib.aio.adapters import CacheEntry as ImportedEntry
        assert ImportedEntry == CacheEntry


if __name__ == "__main__":
    pytest.main([__file__, "-v"])