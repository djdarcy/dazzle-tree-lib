"""
Test cache bypass functionality (Issue #31).

Tests that the use_cache=False parameter correctly bypasses the cache
and fetches directly from the source adapter.
"""

import pytest
import asyncio
import time
from pathlib import Path
from typing import AsyncIterator, Any, List
from unittest.mock import AsyncMock, MagicMock

# Add parent directory to path for imports
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dazzletreelib.aio.adapters.cache_completeness_adapter import CompletenessAwareCacheAdapter


class MockNode:
    """Mock node for testing."""
    def __init__(self, path: Path):
        self.path = path
        self.metadata_value = {'modified_time': time.time()}

    async def metadata(self):
        """Return mock metadata."""
        return self.metadata_value


class MockAdapter:
    """Mock adapter that can change its data between calls."""

    def __init__(self):
        self.call_count = 0
        self.children_sets = [
            # First call returns these children
            [MockNode(Path(f"/test/child_{i}")) for i in range(3)],
            # Second call returns different children (simulating file changes)
            [MockNode(Path(f"/test/new_child_{i}")) for i in range(4)],
        ]

    async def get_children(self, node: Any) -> AsyncIterator[Any]:
        """Return different children on different calls."""
        # Use the appropriate set based on call count
        children = self.children_sets[min(self.call_count, len(self.children_sets) - 1)]
        self.call_count += 1

        for child in children:
            yield child


class TestCacheBypass:
    """Test cache bypass functionality."""

    @pytest.mark.asyncio
    async def test_bypass_returns_fresh_data(self):
        """Test that use_cache=False always fetches from source."""
        mock_adapter = MockAdapter()
        cache_adapter = CompletenessAwareCacheAdapter(
            mock_adapter,
            enable_oom_protection=True,
            validation_ttl_seconds=3600  # Long TTL to ensure cache would be used
        )

        node = MockNode(Path("/test"))

        # First call - populates cache with first set of children
        children1 = []
        async for child in cache_adapter.get_children(node):
            children1.append(child.path.name)

        assert len(children1) == 3
        assert all("child_" in name for name in children1)
        assert cache_adapter.misses == 1
        assert cache_adapter.hits == 0
        assert len(cache_adapter.cache) == 1  # Cache populated

        # Second call without bypass - should use cache (old data)
        children2 = []
        async for child in cache_adapter.get_children(node):
            children2.append(child.path.name)

        assert children2 == children1  # Same data from cache
        assert cache_adapter.hits == 1
        assert cache_adapter.misses == 1  # No new miss

        # Third call WITH bypass - should see new data
        children3 = []
        async for child in cache_adapter.get_children(node, use_cache=False):
            children3.append(child.path.name)

        assert len(children3) == 4  # Different count
        assert all("new_child_" in name for name in children3)
        assert cache_adapter.bypasses == 1
        assert cache_adapter.hits == 1  # Unchanged
        assert cache_adapter.misses == 1  # Unchanged

    @pytest.mark.asyncio
    async def test_bypass_doesnt_populate_cache(self):
        """Test that bypassed calls don't affect the cache."""
        mock_adapter = MockAdapter()
        cache_adapter = CompletenessAwareCacheAdapter(
            mock_adapter,
            enable_oom_protection=True
        )

        node = MockNode(Path("/test"))

        # Call with bypass - should not populate cache
        children = []
        async for child in cache_adapter.get_children(node, use_cache=False):
            children.append(child)

        assert len(children) == 3
        assert cache_adapter.bypasses == 1
        assert len(cache_adapter.cache) == 0  # Cache still empty

        # Subsequent normal call should miss cache
        async for child in cache_adapter.get_children(node):
            pass

        assert cache_adapter.misses == 1
        assert cache_adapter.hits == 0
        assert len(cache_adapter.cache) == 1  # Now populated

    @pytest.mark.asyncio
    async def test_bypass_statistics(self):
        """Test that bypass calls are tracked separately."""
        mock_adapter = MockAdapter()
        cache_adapter = CompletenessAwareCacheAdapter(
            mock_adapter,
            enable_oom_protection=True
        )

        node = MockNode(Path("/test"))

        # Normal call
        async for child in cache_adapter.get_children(node):
            pass

        assert cache_adapter.misses == 1
        assert cache_adapter.hits == 0
        assert cache_adapter.bypasses == 0

        # Cache hit
        async for child in cache_adapter.get_children(node):
            pass

        assert cache_adapter.misses == 1
        assert cache_adapter.hits == 1
        assert cache_adapter.bypasses == 0

        # Bypass call
        async for child in cache_adapter.get_children(node, use_cache=False):
            pass

        assert cache_adapter.misses == 1  # Unchanged
        assert cache_adapter.hits == 1  # Unchanged
        assert cache_adapter.bypasses == 1  # Incremented

        # Another bypass
        async for child in cache_adapter.get_children(node, use_cache=False):
            pass

        assert cache_adapter.bypasses == 2

    @pytest.mark.asyncio
    async def test_default_behavior_unchanged(self):
        """Test that existing code without use_cache parameter works."""
        mock_adapter = MockAdapter()
        cache_adapter = CompletenessAwareCacheAdapter(
            mock_adapter,
            enable_oom_protection=True
        )

        node = MockNode(Path("/test"))

        # Should work exactly as before (default use_cache=True)
        children1 = []
        async for child in cache_adapter.get_children(node):
            children1.append(child)

        assert len(children1) == 3
        assert cache_adapter.misses == 1
        assert cache_adapter.bypasses == 0

        # Should use cache on second call
        children2 = []
        async for child in cache_adapter.get_children(node):
            children2.append(child)

        assert len(children2) == 3
        assert cache_adapter.hits == 1
        assert cache_adapter.bypasses == 0

    @pytest.mark.asyncio
    async def test_bypass_in_fast_mode(self):
        """Test that bypass works in fast mode (no OOM protection)."""
        mock_adapter = MockAdapter()
        cache_adapter = CompletenessAwareCacheAdapter(
            mock_adapter,
            enable_oom_protection=False  # Fast mode
        )

        node = MockNode(Path("/test"))

        # First call - populates cache
        children1 = []
        async for child in cache_adapter.get_children(node):
            children1.append(child.path.name)

        assert len(children1) == 3
        assert cache_adapter.misses == 1

        # Second call - uses cache
        children2 = []
        async for child in cache_adapter.get_children(node):
            children2.append(child.path.name)

        assert children2 == children1
        assert cache_adapter.hits == 1

        # Third call with bypass - gets fresh data
        children3 = []
        async for child in cache_adapter.get_children(node, use_cache=False):
            children3.append(child.path.name)

        assert len(children3) == 4  # New data
        assert all("new_child_" in name for name in children3)
        assert cache_adapter.bypasses == 1

    @pytest.mark.asyncio
    async def test_bypass_with_depth_context(self):
        """Test that bypass respects depth context."""
        mock_adapter = MockAdapter()
        cache_adapter = CompletenessAwareCacheAdapter(
            mock_adapter,
            enable_oom_protection=True
        )

        node = MockNode(Path("/test"))

        # Set depth context
        cache_adapter._depth_context = 5

        # Bypass should still work with depth context
        children = []
        async for child in cache_adapter.get_children(node, use_cache=False):
            children.append(child)

        assert len(children) > 0
        assert cache_adapter.bypasses == 1

        # Depth context should be preserved
        assert cache_adapter._depth_context == 5

    @pytest.mark.asyncio
    async def test_concurrent_bypass_and_cached_calls(self):
        """Test that bypass and cached calls can run concurrently."""
        mock_adapter = MockAdapter()
        cache_adapter = CompletenessAwareCacheAdapter(
            mock_adapter,
            enable_oom_protection=True
        )

        node = MockNode(Path("/test"))

        # First populate the cache
        async for child in cache_adapter.get_children(node):
            pass

        assert cache_adapter.misses == 1

        # Run bypass and cached calls concurrently
        async def bypass_call():
            result = []
            async for child in cache_adapter.get_children(node, use_cache=False):
                result.append(child)
            return result

        async def cached_call():
            result = []
            async for child in cache_adapter.get_children(node):
                result.append(child)
            return result

        # Run concurrently
        results = await asyncio.gather(
            bypass_call(),
            cached_call(),
            bypass_call(),
            cached_call()
        )

        # Check statistics
        assert cache_adapter.bypasses == 2  # Two bypass calls
        assert cache_adapter.hits == 2  # Two cached calls
        assert cache_adapter.misses == 1  # Only initial miss

    @pytest.mark.asyncio
    async def test_explicit_use_cache_true(self):
        """Test that use_cache=True explicitly uses cache."""
        mock_adapter = MockAdapter()
        cache_adapter = CompletenessAwareCacheAdapter(
            mock_adapter,
            enable_oom_protection=True
        )

        node = MockNode(Path("/test"))

        # First call to populate cache
        async for child in cache_adapter.get_children(node, use_cache=True):
            pass

        assert cache_adapter.misses == 1

        # Second call with explicit use_cache=True
        async for child in cache_adapter.get_children(node, use_cache=True):
            pass

        assert cache_adapter.hits == 1
        assert cache_adapter.bypasses == 0

    @pytest.mark.asyncio
    async def test_bypass_with_empty_results(self):
        """Test bypass with adapter returning no children."""

        class EmptyAdapter:
            async def get_children(self, node: Any) -> AsyncIterator[Any]:
                # Return nothing
                return
                yield  # Make it a generator

        empty_adapter = EmptyAdapter()
        cache_adapter = CompletenessAwareCacheAdapter(
            empty_adapter,
            enable_oom_protection=True
        )

        node = MockNode(Path("/test"))

        # Bypass call with empty results
        children = []
        async for child in cache_adapter.get_children(node, use_cache=False):
            children.append(child)

        assert len(children) == 0
        assert cache_adapter.bypasses == 1
        assert len(cache_adapter.cache) == 0  # No cache entry created


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])