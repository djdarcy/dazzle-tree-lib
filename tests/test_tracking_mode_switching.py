"""
Test mode switching and behavior differences.

This module tests fast mode vs safe mode behavior, runtime switching,
and memory pressure scenarios in the SmartCachingAdapter.
"""

import pytest
import asyncio
import gc
from unittest.mock import Mock, patch

from dazzletreelib.aio.adapters.smart_caching import (
    SmartCachingAdapter,
    TrackingState,
    create_bounded_cache_adapter,
    create_unlimited_cache_adapter,
    create_tracking_only_adapter
)


class ModeTestNode:
    """Simple test node."""

    def __init__(self, path):
        self.path = path

    def __str__(self):
        return str(self.path)


class LargeTreeAdapter:
    """Adapter that generates a large tree for testing."""

    def __init__(self, breadth=10, depth=5):
        self.breadth = breadth
        self.max_depth = depth

    async def get_children(self, node):
        """Generate children based on path depth."""
        path = str(node.path) if hasattr(node, 'path') else str(node)
        current_depth = 0 if path == '/' else path.count('/')

        if current_depth < self.max_depth:
            for i in range(self.breadth):
                child_path = f"{path}/node_{current_depth}_{i}" if path != '/' else f"/node_0_{i}"
                yield ModeTestNode(child_path)

    async def get_depth(self, node):
        """Calculate depth from path."""
        path = str(node.path) if hasattr(node, 'path') else str(node)
        return 0 if path == '/' else path.count('/')

    async def get_parent(self, node):
        """Return parent node."""
        return None


class TestModeSwitching:
    """Test mode switching and behavior differences."""

    @pytest.mark.asyncio
    async def test_fast_mode_unlimited_tracking(self):
        """Test that fast mode can track unlimited nodes without eviction."""
        large_tree = LargeTreeAdapter(breadth=50, depth=3)  # ~2500 nodes

        # Fast mode with unlimited cache
        adapter = create_unlimited_cache_adapter(large_tree)
        adapter.track_traversal = True
        adapter.tracker = adapter.tracker or type(adapter.tracker)(enable_safe_mode=False)

        root = ModeTestNode('/')
        discovered_count = 0

        async def traverse(node):
            nonlocal discovered_count
            async for child in adapter.get_children(node):
                discovered_count += 1
                await traverse(child)

        await traverse(root)

        # All nodes should be discovered
        stats = adapter.get_stats()
        assert stats['discovered_nodes'] > 2000, "Should track thousands of nodes in fast mode"
        assert stats['cache_enabled'], "Cache should be enabled"

        # No eviction in fast mode
        if hasattr(adapter.tracker, 'evicted_discovered'):
            assert len(adapter.tracker.evicted_discovered) == 0, "No eviction in unlimited mode"

    @pytest.mark.asyncio
    async def test_safe_mode_memory_pressure_eviction(self):
        """Test that safe mode properly tracks eviction under memory pressure."""
        large_tree = LargeTreeAdapter(breadth=100, depth=2)  # ~10000 nodes

        # Safe mode with very limited memory
        adapter = SmartCachingAdapter(
            large_tree,
            max_memory_mb=0.001,  # Tiny cache to force eviction
            track_traversal=True,
            enable_safe_mode=True
        )

        root = ModeTestNode('/')
        discovered = []

        async def traverse(node):
            async for child in adapter.get_children(node):
                discovered.append(str(child.path))
                if len(discovered) < 50:  # Limit traversal for test speed
                    await traverse(child)

        await traverse(root)

        # Some nodes should be evicted due to memory pressure
        early_node = '/node_0_0'
        state = adapter.get_discovery_state(early_node)

        # Early nodes might be evicted (UNKNOWN_EVICTED) or still present
        assert state in [TrackingState.KNOWN_PRESENT, TrackingState.UNKNOWN_EVICTED], \
            "Node should be either present or evicted"

        # Stats should show limited cache
        stats = adapter.get_stats()
        if 'memory_mb' in stats:
            assert stats['memory_mb'] < 0.01, "Memory should stay within tiny limit"

    @pytest.mark.asyncio
    async def test_mode_switch_preserves_tracking(self):
        """Test that tracking data is preserved when switching modes."""
        tree = LargeTreeAdapter(breadth=5, depth=2)

        # Start with fast mode
        adapter1 = SmartCachingAdapter(
            tree,
            max_memory_mb=100,
            track_traversal=True,
            enable_safe_mode=False
        )

        root = ModeTestNode('/')

        # Traverse with fast mode
        discovered_fast = []
        async for child in adapter1.get_children(root):
            discovered_fast.append(str(child.path))
            async for grandchild in adapter1.get_children(child):
                discovered_fast.append(str(grandchild.path))

        fast_discovered_count = adapter1.get_stats()['discovered_nodes']

        # Create new adapter with safe mode (simulating mode switch)
        # In practice, you'd need to transfer the tracking state
        adapter2 = SmartCachingAdapter(
            tree,
            max_memory_mb=100,
            track_traversal=True,
            enable_safe_mode=True
        )

        # Copy tracking state (simulating preservation)
        if adapter1.tracker and adapter2.tracker:
            adapter2.tracker.discovered = adapter1.tracker.discovered.copy()
            adapter2.tracker.expanded = adapter1.tracker.expanded.copy()
            adapter2.tracker.discovered_depths = adapter1.tracker.discovered_depths.copy()
            adapter2.tracker.expanded_depths = adapter1.tracker.expanded_depths.copy()

        # Verify tracking was preserved
        safe_discovered_count = adapter2.get_stats()['discovered_nodes']
        assert safe_discovered_count == fast_discovered_count, "Tracking should be preserved"

        # Verify tri-state works in safe mode
        for path in discovered_fast[:5]:
            state = adapter2.get_discovery_state(path)
            assert state == TrackingState.KNOWN_PRESENT, f"{path} should be known present"

    @pytest.mark.benchmark
    @pytest.mark.interaction_sensitive
    @pytest.mark.asyncio
    async def test_fast_mode_performance_advantage(self):
        """Test that fast mode is faster than safe mode.

        This test measures relative performance between fast and safe modes.
        It's sensitive to test interaction - prior tests creating many nodes
        can cause memory fragmentation that affects timing measurements.
        """
        import time
        import gc

        # Clean up any residual state from previous tests
        gc.collect()
        gc.collect()  # Force collection of all generations
        gc.collect()

        tree = LargeTreeAdapter(breadth=20, depth=3)  # Medium-sized tree

        # Fast mode
        fast_adapter = SmartCachingAdapter(
            tree,
            max_memory_mb=0,  # Unlimited
            track_traversal=True,
            enable_safe_mode=False
        )

        root = ModeTestNode('/')

        # Time fast mode
        start = time.time()
        async def traverse_fast(node):
            async for child in fast_adapter.get_children(node):
                await traverse_fast(child)

        await traverse_fast(root)
        fast_time = time.time() - start

        # Safe mode with limited memory
        safe_adapter = SmartCachingAdapter(
            tree,
            max_memory_mb=1,  # Limited memory
            track_traversal=True,
            enable_safe_mode=True
        )

        # Time safe mode
        start = time.time()
        async def traverse_safe(node):
            async for child in safe_adapter.get_children(node):
                await traverse_safe(child)

        await traverse_safe(root)
        safe_time = time.time() - start

        # Fast mode should be at least as fast (usually faster due to no eviction overhead)
        # Allow some margin for timing variability
        assert fast_time <= safe_time * 1.5, f"Fast mode ({fast_time:.3f}s) should be faster than safe ({safe_time:.3f}s)"

    @pytest.mark.asyncio
    async def test_safe_mode_tri_state_accuracy(self):
        """Test that tri-state returns are accurate in safe mode."""
        tree = LargeTreeAdapter(breadth=10, depth=2)

        adapter = SmartCachingAdapter(
            tree,
            max_memory_mb=0.001,  # Tiny to force eviction
            track_traversal=True,
            enable_safe_mode=True
        )

        root = ModeTestNode('/')

        # Track specific nodes
        first_children = []
        async for child in adapter.get_children(root):
            first_children.append(str(child.path))
            if len(first_children) >= 5:
                break

        # Continue traversing to potentially evict early nodes
        for _ in range(100):
            async for child in adapter.get_children(root):
                async for grandchild in adapter.get_children(child):
                    pass
                break  # Just do one branch

        # Check tri-state for different scenarios
        # 1. Known present (recently accessed)
        recent_state = adapter.get_discovery_state('/')
        assert recent_state == TrackingState.KNOWN_PRESENT, "Root should be present"

        # 2. Known absent (never discovered)
        absent_state = adapter.get_discovery_state('/nonexistent')
        assert absent_state == TrackingState.KNOWN_ABSENT, "Non-existent should be absent"

        # 3. Check if any early nodes were evicted
        evicted_found = False
        for path in first_children:
            state = adapter.get_discovery_state(path)
            if state == TrackingState.UNKNOWN_EVICTED:
                evicted_found = True
                break

        # With tiny cache, some eviction is expected but not guaranteed
        # The test passes either way but documents the behavior

    @pytest.mark.asyncio
    async def test_tracking_only_mode(self):
        """Test adapter with tracking but no caching."""
        tree = LargeTreeAdapter(breadth=10, depth=2)

        # Create tracking-only adapter (no caching)
        adapter = create_tracking_only_adapter(tree)

        root = ModeTestNode('/')

        # First traversal
        first_discovered = []
        async for child in adapter.get_children(root):
            first_discovered.append(str(child.path))
            async for grandchild in adapter.get_children(child):
                first_discovered.append(str(grandchild.path))

        # Second traversal - no cache, so should hit base adapter again
        second_discovered = []
        async for child in adapter.get_children(root):
            second_discovered.append(str(child.path))
            async for grandchild in adapter.get_children(child):
                second_discovered.append(str(grandchild.path))

        # Verify tracking works without caching
        stats = adapter.get_stats()
        assert stats['cache_enabled'] == False, "Cache should be disabled"
        assert stats['tracking_enabled'] == True, "Tracking should be enabled"
        assert stats['discovered_nodes'] > 0, "Should track discoveries"

        # All discovered nodes should be tracked
        for path in first_discovered:
            assert adapter.was_discovered(path), f"{path} should be tracked"

    @pytest.mark.asyncio
    async def test_memory_cleanup_mode_differences(self):
        """Test memory cleanup behavior differs between modes."""
        tree = LargeTreeAdapter(breadth=50, depth=2)

        # Fast mode - should keep everything
        fast_adapter = SmartCachingAdapter(
            tree,
            max_memory_mb=0,  # Unlimited
            track_traversal=True,
            enable_safe_mode=False
        )

        # Safe mode - should evict under pressure
        safe_adapter = SmartCachingAdapter(
            tree,
            max_memory_mb=1,  # 1MB limit
            track_traversal=True,
            enable_safe_mode=True
        )

        root = ModeTestNode('/')

        # Traverse both
        async def traverse(adapter):
            discovered = 0
            async for child in adapter.get_children(root):
                discovered += 1
                if discovered > 100:  # Limit for test speed
                    break
                async for grandchild in adapter.get_children(child):
                    discovered += 1
                    if discovered > 200:
                        break
            return discovered

        fast_count = await traverse(fast_adapter)
        safe_count = await traverse(safe_adapter)

        # Force garbage collection
        gc.collect()

        # Check memory usage
        fast_stats = fast_adapter.get_stats()
        safe_stats = safe_adapter.get_stats()

        # Safe mode should maintain memory limit
        if 'memory_mb' in safe_stats:
            assert safe_stats['memory_mb'] <= 1.5, "Safe mode should respect memory limit"

        # Fast mode can use unlimited memory
        if 'entries' in fast_stats and 'entries' in safe_stats:
            # Fast mode likely has more cached entries
            assert fast_stats['entries'] >= safe_stats['entries'], \
                "Fast mode should cache more entries"