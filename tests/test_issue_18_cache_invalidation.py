"""
Test Issue #18 fix: Cache invalidation based on mtime.

This validates that the cache system properly invalidates stale entries
when files are modified, preventing serving of outdated data.
"""

import pytest
import asyncio
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, Mock, MagicMock

from dazzletreelib.aio.adapters.cache_completeness_adapter import (
    CacheEntry,
    CompletenessAwareCacheAdapter
)
from dazzletreelib.aio.adapters.filesystem import AsyncFileSystemNode


class TestCacheInvalidation:
    """Test that cache properly invalidates stale entries."""
    
    @pytest.mark.asyncio
    async def test_mtime_is_captured_when_caching(self):
        """Test that mtime is captured when caching data."""
        # Create a mock node with metadata
        mock_node = AsyncMock()
        mock_node.path = Path("/test/path")
        mock_node.metadata.return_value = {
            'modified_time': 1234567890.123,
            'type': 'directory'
        }
        
        # Create mock base adapter
        base_adapter = AsyncMock()
        child1 = AsyncMock()
        child1.path = Path("/test/path/child1")
        child2 = AsyncMock()
        child2.path = Path("/test/path/child2")
        
        async def mock_get_children(node):
            for child in [child1, child2]:
                yield child
        
        base_adapter.get_children = mock_get_children
        
        # Create cache adapter
        cache_adapter = CompletenessAwareCacheAdapter(base_adapter)
        
        # Get children (should cache with mtime)
        children = []
        async for child in cache_adapter.get_children(mock_node):
            children.append(child)
        
        # Verify children were returned
        assert len(children) == 2
        
        # Check that cache entry has mtime
        cache_key = cache_adapter._get_cache_key(Path("/test/path"), 1)
        assert cache_key in cache_adapter.cache
        entry = cache_adapter.cache[cache_key]
        assert entry.mtime == 1234567890.123
    
    @pytest.mark.asyncio
    async def test_stale_cache_is_invalidated(self):
        """Test that stale cache entries are invalidated when mtime changes."""
        # Create a mock node with metadata
        mock_node = AsyncMock()
        mock_node.path = Path("/test/path")
        initial_mtime = 1234567890.123
        mock_node.metadata.return_value = {
            'modified_time': initial_mtime,
            'type': 'directory'
        }
        
        # Create mock base adapter
        base_adapter = AsyncMock()
        
        # First call returns original children
        original_child = AsyncMock()
        original_child.path = Path("/test/path/original")
        
        # Second call returns new children
        new_child = AsyncMock()
        new_child.path = Path("/test/path/new")
        
        call_count = 0
        async def mock_get_children(node):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                yield original_child
            else:
                yield new_child
        
        base_adapter.get_children = mock_get_children
        
        # Create cache adapter
        cache_adapter = CompletenessAwareCacheAdapter(base_adapter)
        
        # First call - should cache
        children1 = []
        async for child in cache_adapter.get_children(mock_node):
            children1.append(child)
        assert len(children1) == 1
        assert children1[0] == original_child
        assert cache_adapter.hits == 0
        assert cache_adapter.misses == 1
        
        # Simulate file modification - update mtime
        mock_node.metadata.return_value = {
            'modified_time': initial_mtime + 10,  # File modified
            'type': 'directory'
        }
        
        # Second call - should detect stale cache and fetch fresh
        children2 = []
        async for child in cache_adapter.get_children(mock_node):
            children2.append(child)
        assert len(children2) == 1
        assert children2[0] == new_child  # Got new data, not cached
        assert cache_adapter.hits == 0  # No hit because cache was stale
        assert cache_adapter.misses == 2  # Two misses total
        assert call_count == 2  # Base adapter called twice
    
    @pytest.mark.asyncio
    async def test_fresh_cache_is_reused(self):
        """Test that fresh cache entries are reused when mtime unchanged."""
        # Create a mock node with metadata
        mock_node = AsyncMock()
        mock_node.path = Path("/test/path")
        stable_mtime = 1234567890.123
        mock_node.metadata.return_value = {
            'modified_time': stable_mtime,
            'type': 'directory'
        }
        
        # Create mock base adapter
        base_adapter = AsyncMock()
        child = AsyncMock()
        child.path = Path("/test/path/child")
        
        call_count = 0
        async def mock_get_children(node):
            nonlocal call_count
            call_count += 1
            yield child
        
        base_adapter.get_children = mock_get_children
        
        # Create cache adapter
        cache_adapter = CompletenessAwareCacheAdapter(base_adapter)
        
        # First call - should cache
        children1 = []
        async for child in cache_adapter.get_children(mock_node):
            children1.append(child)
        assert len(children1) == 1
        assert cache_adapter.hits == 0
        assert cache_adapter.misses == 1
        
        # Second call with same mtime - should use cache
        children2 = []
        async for child in cache_adapter.get_children(mock_node):
            children2.append(child)
        assert len(children2) == 1
        assert children2[0] == child  # Same cached child
        assert cache_adapter.hits == 1  # Cache hit!
        assert cache_adapter.misses == 1  # Still just one miss
        assert call_count == 1  # Base adapter only called once
    
    @pytest.mark.asyncio
    async def test_cache_works_without_mtime(self):
        """Test that cache still works for nodes without mtime."""
        # Create a mock node WITHOUT metadata
        mock_node = Mock()  # Not AsyncMock, so no metadata method
        mock_node.path = Path("/test/path")
        
        # Create mock base adapter
        base_adapter = AsyncMock()
        child = AsyncMock()
        child.path = Path("/test/path/child")
        
        call_count = 0
        async def mock_get_children(node):
            nonlocal call_count
            call_count += 1
            yield child
        
        base_adapter.get_children = mock_get_children
        
        # Create cache adapter
        cache_adapter = CompletenessAwareCacheAdapter(base_adapter)
        
        # First call - should cache without mtime
        children1 = []
        async for child in cache_adapter.get_children(mock_node):
            children1.append(child)
        assert len(children1) == 1
        
        # Check cache entry has no mtime
        cache_key = cache_adapter._get_cache_key(Path("/test/path"), 1)
        entry = cache_adapter.cache[cache_key]
        assert entry.mtime is None
        
        # Second call - should use cache (no validation possible)
        children2 = []
        async for child in cache_adapter.get_children(mock_node):
            children2.append(child)
        assert len(children2) == 1
        assert cache_adapter.hits == 1  # Cache hit despite no mtime
        assert call_count == 1  # Base adapter only called once
    
    @pytest.mark.asyncio
    async def test_deeper_scan_also_validates_mtime(self):
        """Test that deeper scan entries also validate mtime."""
        # Create a mock node
        mock_node = AsyncMock()
        mock_node.path = Path("/test/path")
        initial_mtime = 1234567890.123
        mock_node.metadata.return_value = {
            'modified_time': initial_mtime,
            'type': 'directory'
        }
        
        # Create mock base adapter
        base_adapter = AsyncMock()
        original_child = AsyncMock()
        original_child.path = Path("/test/path/original")
        new_child = AsyncMock()
        new_child.path = Path("/test/path/new")
        
        call_count = 0
        async def mock_get_children(node):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                yield original_child
            else:
                yield new_child
        
        base_adapter.get_children = mock_get_children
        
        # Create cache adapter
        cache_adapter = CompletenessAwareCacheAdapter(base_adapter)
        
        # Cache with depth 5
        cache_adapter.set_depth_context(5)
        children1 = []
        async for child in cache_adapter.get_children(mock_node):
            children1.append(child)
        assert children1[0] == original_child
        
        # Update mtime
        mock_node.metadata.return_value = {
            'modified_time': initial_mtime + 10,
            'type': 'directory'
        }
        
        # Request with depth 3 (should find depth 5 cache but invalidate due to stale)
        cache_adapter.set_depth_context(3)
        children2 = []
        async for child in cache_adapter.get_children(mock_node):
            children2.append(child)
        assert children2[0] == new_child  # Got fresh data
        assert call_count == 2  # Base adapter called twice


class TestCacheEntryHelpers:
    """Test the CacheEntry helper methods with mtime."""
    
    def test_cache_entry_with_mtime(self):
        """Test creating cache entry with mtime."""
        mtime = 1234567890.123
        entry = CacheEntry(["data"], depth=3, mtime=mtime)
        
        assert entry.mtime == mtime
        assert entry.depth == 3
        assert entry.is_partial() is True
        assert entry.is_complete() is False
    
    def test_cache_entry_without_mtime(self):
        """Test cache entry works without mtime."""
        entry = CacheEntry(["data"], depth=5)
        
        assert entry.mtime is None
        assert entry.depth == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])