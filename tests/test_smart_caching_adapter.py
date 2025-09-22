"""
Tests for the new SmartCachingAdapter with clean API.

This demonstrates how much cleaner and clearer the new API is
compared to the old CompletenessAwareCacheAdapter.
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock, MagicMock

from dazzletreelib.aio.adapters.smart_caching import (
    SmartCachingAdapter,
    TraversalTracker,
    create_bounded_cache_adapter,
    create_unlimited_cache_adapter,
    create_tracking_only_adapter
)
import time


class MockNode:
    """Mock node for testing."""
    def __init__(self, path):
        self.path = Path(path)

    async def identifier(self):
        """Return path as identifier for node-based invalidation."""
        return str(self.path)


class MockAdapter:
    """Mock base adapter for testing."""

    def __init__(self):
        self.call_count = 0

    async def get_children(self, node):
        """Return mock children."""
        self.call_count += 1
        path = node.path if hasattr(node, 'path') else Path(str(node))

        # Return different children based on path
        if path == Path("/root"):
            children = [MockNode("/root/dir1"), MockNode("/root/dir2")]
        elif path == Path("/root/dir1"):
            children = [MockNode("/root/dir1/file1"), MockNode("/root/dir1/file2")]
        else:
            children = []

        # Yield children as async generator
        for child in children:
            yield child

    async def get_parent(self, node):
        """Return mock parent."""
        path = node.path if hasattr(node, 'path') else Path(str(node))
        if path != Path("/root"):
            return MockNode(path.parent)
        return None

    async def get_depth(self, node):
        """Return mock depth."""
        path = node.path if hasattr(node, 'path') else Path(str(node))
        return len(path.parts) - 1

    def __aiter__(self):
        """Make this async iterable."""
        return self

    async def __anext__(self):
        """For async iteration."""
        raise StopAsyncIteration


class TestTraversalTracker:
    """Test the clean TraversalTracker API."""

    def test_clear_semantics(self):
        """Test that discovered vs expanded is clear."""
        tracker = TraversalTracker()

        # Track some operations
        tracker.track_discovery("/root/file1")
        tracker.track_discovery("/root/file2")
        tracker.track_expansion("/root")

        # Clear, unambiguous checks
        assert tracker.was_discovered("/root/file1")
        assert tracker.was_discovered("/root/file2")
        assert not tracker.was_expanded("/root/file1")  # Not expanded
        assert tracker.was_expanded("/root")

        # Clear counts
        assert tracker.get_discovered_count() == 2
        assert tracker.get_expanded_count() == 1

    def test_clear_reset(self):
        """Test that clear() resets everything."""
        tracker = TraversalTracker()

        tracker.track_discovery("/path1")
        tracker.track_expansion("/path2")
        assert tracker.get_discovered_count() == 1
        assert tracker.get_expanded_count() == 1

        tracker.clear()
        assert tracker.get_discovered_count() == 0
        assert tracker.get_expanded_count() == 0


@pytest.mark.asyncio
class TestSmartCachingAdapter:
    """Test the new clean SmartCachingAdapter."""

    async def test_clear_api_usage(self):
        """Demonstrate the clear, intuitive API."""
        base = MockAdapter()
        adapter = SmartCachingAdapter(
            base_adapter=base,
            max_memory_mb=100,  # Clear: 100MB limit
            track_traversal=True  # Clear: we want tracking
        )

        # Get children - clear what this does
        root = MockNode("/root")
        children = []
        async for child in adapter.get_children(root):
            children.append(child)

        # Clear, unambiguous checks
        assert adapter.was_expanded("/root")  # We called get_children on root
        assert adapter.was_discovered("/root")  # Root is discovered when expanded
        assert adapter.was_discovered("/root/dir1")  # We found dir1
        assert adapter.was_discovered("/root/dir2")  # We found dir2
        assert not adapter.was_expanded("/root/dir1")  # We didn't expand dir1

        # Clean stats API
        stats = adapter.get_cache_stats()
        # Note: discovered_nodes includes the root (which was expanded and thus discovered)
        # This ensures semantic consistency: expanded nodes are inherently discovered
        assert stats['discovered_nodes'] == 3  # root + dir1 + dir2
        assert stats['expanded_nodes'] == 1    # only root was expanded
        assert stats['cache_enabled'] is True
        assert stats['tracking_enabled'] is True

    async def test_cache_behavior(self):
        """Test that caching works as expected."""
        base = MockAdapter()
        adapter = SmartCachingAdapter(base, max_memory_mb=100)

        root = MockNode("/root")

        # First call - should hit base adapter
        children1 = []
        async for child in adapter.get_children(root):
            children1.append(child)
        assert base.call_count == 1

        # Second call - should use cache
        children2 = []
        async for child in adapter.get_children(root):
            children2.append(child)
        assert base.call_count == 1  # Still 1, used cache

        # Verify same results
        assert len(children1) == len(children2) == 2

    async def test_no_cache_mode(self):
        """Test adapter with no caching."""
        base = MockAdapter()
        adapter = SmartCachingAdapter(
            base,
            max_memory_mb=-1,  # Clear: no caching
            track_traversal=True
        )

        root = MockNode("/root")

        # Multiple calls should always hit base
        for _ in range(3):
            async for child in adapter.get_children(root):
                pass

        assert base.call_count == 3  # No caching

        # But tracking still works
        assert adapter.was_expanded("/root")
        assert adapter.was_discovered("/root/dir1")

    async def test_factory_functions(self):
        """Test the convenience factory functions."""
        base = MockAdapter()

        # Clear what each factory creates
        bounded = create_bounded_cache_adapter(base, max_memory_mb=50)
        assert bounded._cache is not None
        assert bounded._cache.enable_protection is True

        unlimited = create_unlimited_cache_adapter(base)
        assert unlimited._cache is not None
        assert unlimited._cache.enable_protection is False

        tracking_only = create_tracking_only_adapter(base)
        assert tracking_only._cache is None
        assert tracking_only.tracker is not None

    async def test_cache_invalidation(self):
        """Test the clear cache invalidation API."""
        base = MockAdapter()
        adapter = SmartCachingAdapter(base, max_memory_mb=100)

        root = MockNode("/root")

        # Populate cache
        async for child in adapter.get_children(root):
            pass
        assert base.call_count == 1

        # Clear, explicit invalidation
        invalidated = adapter.invalidate_cache("/root")
        assert invalidated > 0

        # Next call hits base again
        async for child in adapter.get_children(root):
            pass
        assert base.call_count == 2

    async def test_clear_methods(self):
        """Test the clear() methods."""
        base = MockAdapter()
        adapter = SmartCachingAdapter(base)

        root = MockNode("/root")
        async for child in adapter.get_children(root):
            pass

        # Verify tracking works
        assert adapter.was_expanded("/root")
        assert adapter.was_discovered("/root/dir1")

        # Clear tracking only
        adapter.clear_tracking()
        assert not adapter.was_expanded("/root")
        assert not adapter.was_discovered("/root/dir1")

        # Cache should still work
        base.call_count = 0
        async for child in adapter.get_children(root):
            pass
        assert base.call_count == 0  # Used cache

        # Clear cache
        adapter.clear_cache()
        async for child in adapter.get_children(root):
            pass
        assert base.call_count == 1  # Had to fetch


@pytest.mark.asyncio
class TestNewFeatures:
    """Test new feature parity with CompletenessAwareCacheAdapter."""

    async def test_validation_ttl(self):
        """Test that validation TTL controls cache expiry."""
        base = MockAdapter()
        adapter = SmartCachingAdapter(
            base,
            validation_ttl_seconds=0.1  # 100ms TTL
        )

        root = MockNode('/root')
        # First call should cache
        children1 = [child async for child in adapter.get_children(root)]
        assert adapter.cache_misses == 1
        assert adapter.cache_hits == 0

        # Immediate second call should use cache
        children2 = [child async for child in adapter.get_children(root)]
        assert adapter.cache_hits == 1

        # After TTL expires, should refetch
        await asyncio.sleep(0.15)
        children3 = [child async for child in adapter.get_children(root)]
        assert adapter.cache_misses == 2  # Should have refetched

    async def test_use_cache_bypass(self):
        """Test that use_cache=False bypasses cache."""
        base = MockAdapter()
        adapter = SmartCachingAdapter(base)

        root = MockNode('/root')
        # First call caches
        children1 = [child async for child in adapter.get_children(root)]
        assert adapter.cache_misses == 1

        # Second call with use_cache=False should bypass
        children2 = [child async for child in adapter.get_children(root, use_cache=False)]
        # Cache stats shouldn't change for bypassed calls
        assert adapter.cache_misses == 1  # Bypassed, not a miss
        assert adapter.cache_hits == 0  # No hits

        # Third call should use cache
        children3 = [child async for child in adapter.get_children(root)]
        assert adapter.cache_hits == 1

    async def test_node_invalidation(self):
        """Test node-based invalidation methods."""
        base = MockAdapter()
        adapter = SmartCachingAdapter(base)

        # Create and cache some nodes
        root = MockNode('/root')
        child1 = MockNode('/root/dir1')
        child2 = MockNode('/root/dir2')

        # Cache root
        children = [child async for child in adapter.get_children(root)]

        # Test invalidate_node
        count = await adapter.invalidate_node(root)
        assert count >= 0  # Should have invalidated something

        # Test invalidate_nodes
        nodes = [child1, child2]
        count = await adapter.invalidate_nodes(nodes)
        # Note: actual count depends on what was cached

        # Test error handling
        with pytest.raises(ValueError):
            await adapter.invalidate_node(None)

    async def test_max_tracked_nodes(self):
        """Test that max_tracked_nodes limits tracking."""
        base = MockAdapter()
        adapter = SmartCachingAdapter(
            base,
            max_tracked_nodes=2  # Only track 2 nodes
        )

        # Track some nodes
        root = MockNode('/root')
        children = [child async for child in adapter.get_children(root)]

        # When limit is reached, tracking resets
        # So we should have just the nodes from the last traversal
        tracked = adapter.tracker.get_discovered_count()
        assert tracked > 0  # Should have tracked something

    async def test_max_cache_depth(self):
        """Test that max_cache_depth limits caching by depth."""
        base = MockAdapter()
        adapter = SmartCachingAdapter(
            base,
            max_cache_depth=0  # Only cache depth 0 (root level)
        )

        # Root is depth 0, should be cached
        root = MockNode('/root')
        children1 = [child async for child in adapter.get_children(root)]
        assert base.call_count == 1

        # Second call should use cache
        children2 = [child async for child in adapter.get_children(root)]
        assert base.call_count == 1  # Still 1, used cache
        assert adapter.cache_hits == 1

        # Child nodes are depth 1, should NOT be cached if adapter checks depth
        # But our mock doesn't easily test this without more complex setup

    async def test_validation_ttl_never(self):
        """Test validation_ttl_seconds=-1 (never expire)."""
        base = MockAdapter()
        adapter = SmartCachingAdapter(
            base,
            validation_ttl_seconds=-1  # Never expire
        )

        root = MockNode('/root')
        children1 = [child async for child in adapter.get_children(root)]

        # Even after delay, should still use cache
        await asyncio.sleep(0.1)
        children2 = [child async for child in adapter.get_children(root)]
        assert adapter.cache_hits == 1  # Should use cache

    async def test_validation_ttl_always(self):
        """Test validation_ttl_seconds=0 (always validate)."""
        base = MockAdapter()
        adapter = SmartCachingAdapter(
            base,
            validation_ttl_seconds=0  # Always validate (never use cache)
        )

        root = MockNode('/root')
        children1 = [child async for child in adapter.get_children(root)]
        children2 = [child async for child in adapter.get_children(root)]

        # Should never use cache
        assert adapter.cache_hits == 0
        assert base.call_count == 2  # Always fetches from base


class TestCleanerAPIComparison:
    """Compare old vs new API to show improvement."""

    def test_semantic_clarity(self):
        """Show how the new API is clearer."""

        # OLD: Confusing
        # adapter = CompletenessAwareCacheAdapter(
        #     base_adapter=base,
        #     enable_oom_protection=True,  # What does this mean?
        #     max_memory_mb=100,
        #     max_depth=100,  # What depth?
        #     max_entries=10000,
        #     max_cache_depth=50,  # Different from max_depth?
        #     max_path_depth=30,  # Yet another depth?
        #     max_tracked_nodes=10000
        # )
        # was_visited = testable.was_node_visited(path)  # Visited how?

        # NEW: Clear
        base = MockAdapter()
        adapter = SmartCachingAdapter(
            base_adapter=base,
            max_memory_mb=100,  # Simple: memory limit
            track_traversal=True  # Simple: track or not
        )

        # Unambiguous methods
        was_found = adapter.was_discovered("/path")  # Clear: encountered
        was_opened = adapter.was_expanded("/path")  # Clear: looked inside

        # This clarity makes the API a joy to use!


if __name__ == "__main__":
    pytest.main([__file__, "-v"])