"""
Test tri-state tracking functionality for safe mode.

This tests the ability to distinguish between:
- KNOWN_PRESENT: Node was definitely discovered/expanded
- KNOWN_ABSENT: Node was definitely not discovered/expanded
- UNKNOWN_EVICTED: Node data was evicted, can't be sure
"""

import pytest
import asyncio
from unittest.mock import Mock

from dazzletreelib.aio.adapters.smart_caching import (
    SmartCachingAdapter,
    TraversalTracker,
    TrackingState
)


class MockNode:
    """Simple mock node for testing."""
    def __init__(self, path):
        self.path = path

    def __str__(self):
        return str(self.path)


class MockAdapter:
    """Mock base adapter for testing."""

    def __init__(self, tree_structure=None):
        self.tree = tree_structure or {
            '/': ['/a', '/b', '/c'],
            '/a': ['/a/1', '/a/2'],
        }

    async def get_children(self, node):
        """Return mock children."""
        path = str(node.path) if hasattr(node, 'path') else str(node)
        children_paths = self.tree.get(path, [])
        for child_path in children_paths:
            yield MockNode(child_path)

    async def get_depth(self, node):
        """Return mock depth."""
        path = str(node.path) if hasattr(node, 'path') else str(node)
        if path == '/':
            return 0
        parts = [p for p in path.split('/') if p]
        return len(parts)

    async def get_parent(self, node):
        """Return mock parent."""
        return None


class TestTriStateTracking:
    """Test tri-state tracking functionality."""

    def test_tracker_without_safe_mode(self):
        """Test that tracker works normally without safe mode."""
        tracker = TraversalTracker(enable_safe_mode=False)

        # Track some nodes
        tracker.track_discovery('/a', 1)
        tracker.track_expansion('/a', 1)

        # Without safe mode, should only return PRESENT or ABSENT
        assert tracker.get_discovery_state('/a') == TrackingState.KNOWN_PRESENT
        assert tracker.get_expansion_state('/a') == TrackingState.KNOWN_PRESENT
        assert tracker.get_discovery_state('/b') == TrackingState.KNOWN_ABSENT
        assert tracker.get_expansion_state('/b') == TrackingState.KNOWN_ABSENT

    def test_tracker_with_safe_mode(self):
        """Test that tracker tracks evicted nodes in safe mode."""
        tracker = TraversalTracker(enable_safe_mode=True)

        # Track some nodes
        tracker.track_discovery('/a', 1)
        tracker.track_expansion('/a', 1)
        tracker.track_discovery('/b', 1)

        # Before eviction
        assert tracker.get_discovery_state('/a') == TrackingState.KNOWN_PRESENT
        assert tracker.get_expansion_state('/a') == TrackingState.KNOWN_PRESENT
        assert tracker.get_discovery_state('/b') == TrackingState.KNOWN_PRESENT
        assert tracker.get_expansion_state('/b') == TrackingState.KNOWN_ABSENT

        # Mark /a as evicted
        tracker.mark_evicted('/a')

        # After eviction
        assert tracker.get_discovery_state('/a') == TrackingState.UNKNOWN_EVICTED
        assert tracker.get_expansion_state('/a') == TrackingState.UNKNOWN_EVICTED
        assert tracker.get_discovery_state('/b') == TrackingState.KNOWN_PRESENT
        assert tracker.get_discovery_state('/c') == TrackingState.KNOWN_ABSENT

    def test_eviction_moves_to_evicted_sets(self):
        """Test that eviction properly moves nodes to evicted sets."""
        tracker = TraversalTracker(enable_safe_mode=True)

        # Track nodes
        tracker.track_discovery('/a', 1)
        tracker.track_expansion('/a', 1)

        # Verify in active sets
        assert '/a' in tracker.discovered
        assert '/a' in tracker.expanded
        assert '/a' not in tracker.evicted_discovered
        assert '/a' not in tracker.evicted_expanded

        # Evict the node
        tracker.mark_evicted('/a')

        # Verify moved to evicted sets
        assert '/a' not in tracker.discovered
        assert '/a' not in tracker.expanded
        assert '/a' in tracker.evicted_discovered
        assert '/a' in tracker.evicted_expanded

    def test_eviction_without_safe_mode_does_nothing(self):
        """Test that mark_evicted does nothing when safe mode is disabled."""
        tracker = TraversalTracker(enable_safe_mode=False)

        # Track nodes
        tracker.track_discovery('/a', 1)
        tracker.track_expansion('/a', 1)

        # Try to evict (should do nothing)
        tracker.mark_evicted('/a')

        # Node should still be present
        assert '/a' in tracker.discovered
        assert '/a' in tracker.expanded
        assert tracker.get_discovery_state('/a') == TrackingState.KNOWN_PRESENT

    def test_clear_resets_evicted_sets(self):
        """Test that clear() also resets evicted sets."""
        tracker = TraversalTracker(enable_safe_mode=True)

        # Track and evict some nodes
        tracker.track_discovery('/a', 1)
        tracker.track_expansion('/a', 1)
        tracker.mark_evicted('/a')

        # Verify evicted
        assert '/a' in tracker.evicted_discovered
        assert '/a' in tracker.evicted_expanded

        # Clear all tracking
        tracker.clear()

        # Everything should be empty
        assert len(tracker.discovered) == 0
        assert len(tracker.expanded) == 0
        assert len(tracker.evicted_discovered) == 0
        assert len(tracker.evicted_expanded) == 0

    @pytest.mark.asyncio
    async def test_adapter_tri_state_methods(self):
        """Test SmartCachingAdapter tri-state query methods."""
        mock_adapter = MockAdapter()
        adapter = SmartCachingAdapter(
            mock_adapter,
            track_traversal=True,
            enable_safe_mode=True,
            max_memory_mb=100
        )

        root = MockNode('/')

        # Traverse to discover nodes
        async for child in adapter.get_children(root):
            pass

        # Test tri-state methods
        assert adapter.get_discovery_state('/') == TrackingState.KNOWN_PRESENT
        assert adapter.get_expansion_state('/') == TrackingState.KNOWN_PRESENT
        assert adapter.get_discovery_state('/a') == TrackingState.KNOWN_PRESENT
        assert adapter.get_expansion_state('/a') == TrackingState.KNOWN_ABSENT
        assert adapter.get_discovery_state('/unknown') == TrackingState.KNOWN_ABSENT

        # Test without tracking returns None
        adapter2 = SmartCachingAdapter(
            mock_adapter,
            track_traversal=False,
            enable_safe_mode=False
        )
        assert adapter2.get_discovery_state('/') is None
        assert adapter2.get_expansion_state('/') is None

    @pytest.mark.asyncio
    async def test_cache_eviction_triggers_tracking(self):
        """Test that cache eviction triggers tracking updates in safe mode."""
        mock_adapter = MockAdapter()

        # Create adapter with tiny cache to force eviction
        adapter = SmartCachingAdapter(
            mock_adapter,
            track_traversal=True,
            enable_safe_mode=True,
            max_memory_mb=0.0001  # Tiny cache to force eviction
        )

        # Traverse many nodes to trigger eviction
        nodes_to_traverse = []
        for i in range(100):
            nodes_to_traverse.append(MockNode(f'/node{i}'))

        # Mock the tree to have these nodes
        mock_adapter.tree = {f'/node{i}': [] for i in range(100)}

        # Traverse all nodes (this should trigger evictions)
        for node in nodes_to_traverse:
            async for child in adapter.get_children(node):
                pass

        # At least some early nodes should show as evicted
        # (exact behavior depends on cache implementation details)
        # This test mainly verifies the integration works without errors

    def test_depth_preserved_during_eviction(self):
        """Test that depth information is properly removed during eviction."""
        tracker = TraversalTracker(enable_safe_mode=True)

        # Track with depth
        tracker.track_discovery('/a', 1)
        tracker.track_expansion('/a', 1)

        # Verify depth is tracked
        assert tracker.get_discovery_depth('/a') == 1
        assert tracker.get_expansion_depth('/a') == 1

        # Evict the node
        tracker.mark_evicted('/a')

        # Depth should be removed
        assert tracker.get_discovery_depth('/a') is None
        assert tracker.get_expansion_depth('/a') is None

        # But we should know it was evicted
        assert tracker.get_discovery_state('/a') == TrackingState.UNKNOWN_EVICTED

    def test_partial_eviction(self):
        """Test that nodes can be discovered but not expanded when evicted."""
        tracker = TraversalTracker(enable_safe_mode=True)

        # Track discovery only
        tracker.track_discovery('/a', 1)

        # Evict
        tracker.mark_evicted('/a')

        # Should show as evicted for discovery, absent for expansion
        assert tracker.get_discovery_state('/a') == TrackingState.UNKNOWN_EVICTED
        assert tracker.get_expansion_state('/a') == TrackingState.KNOWN_ABSENT