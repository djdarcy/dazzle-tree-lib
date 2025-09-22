"""
Comprehensive test suite for tracking semantics (Issue #40).

This module tests the clear separation between discovered and expanded nodes,
including depth tracking, edge cases, and mode-specific behaviors.
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock

from dazzletreelib.aio.adapters.smart_caching import (
    SmartCachingAdapter,
    TraversalTracker
)


class MockNode:
    """Mock node for testing."""
    def __init__(self, path):
        # Store path as string to avoid Windows path conversion
        self.path = path

    def __str__(self):
        return str(self.path)


class MockAdapter:
    """Mock base adapter for controlled testing."""

    def __init__(self, tree_structure=None):
        """
        Initialize with optional tree structure.

        Args:
            tree_structure: Dict mapping paths to lists of child paths
        """
        self.tree = tree_structure or {
            '/': ['/a', '/b', '/c'],
            '/a': ['/a/1', '/a/2'],
            '/a/1': ['/a/1/x', '/a/1/y'],
            '/a/2': [],
            '/b': ['/b/1'],
            '/b/1': [],
            '/c': [],
        }
        self.get_children_calls = []
        self.get_depth_calls = []

    async def get_children(self, node):
        """Return children based on tree structure."""
        path = str(node.path) if hasattr(node, 'path') else str(node)
        self.get_children_calls.append(path)

        children_paths = self.tree.get(path, [])
        for child_path in children_paths:
            yield MockNode(child_path)

    async def get_depth(self, node):
        """Calculate depth based on path separators."""
        path = str(node.path) if hasattr(node, 'path') else str(node)
        # Normalize Windows paths
        path = path.replace('\\', '/')
        self.get_depth_calls.append(path)

        # Root is depth 0
        if path == '/':
            return 0
        # Count slashes (path segments)
        parts = [p for p in path.split('/') if p]  # Filter empty parts
        return len(parts)


class TestBasicTrackingSemantics:
    """Test basic discovered vs expanded tracking."""

    @pytest.mark.asyncio
    async def test_root_node_tracking(self):
        """Test that root node is both discovered and expanded when traversed."""
        mock_adapter = MockAdapter()
        adapter = SmartCachingAdapter(mock_adapter, track_traversal=True)

        root = MockNode('/')
        children = []
        async for child in adapter.get_children(root):
            children.append(child)

        # Root should be both discovered and expanded
        assert adapter.was_discovered('/'), "Root should be discovered"
        assert adapter.was_expanded('/'), "Root should be expanded"

        # Children should only be discovered (not expanded yet)
        for child in children:
            child_path = str(child.path)
            assert adapter.was_discovered(child_path), f"{child_path} should be discovered"
            assert not adapter.was_expanded(child_path), f"{child_path} should not be expanded"

    @pytest.mark.asyncio
    async def test_nodes_at_max_depth_discovered_not_expanded(self):
        """Test that nodes at maximum traversal depth are discovered but not expanded."""
        mock_adapter = MockAdapter()
        adapter = SmartCachingAdapter(mock_adapter, track_traversal=True)

        # Traverse with depth limit
        async def traverse_to_depth(node, current_depth, max_depth):
            # Always call get_children to discover children
            async for child in adapter.get_children(node):
                # Only recurse if we haven't reached max depth
                if current_depth < max_depth:
                    await traverse_to_depth(child, current_depth + 1, max_depth)

        root = MockNode('/')
        await traverse_to_depth(root, 0, 2)  # Traverse to depth 2

        # Nodes at depth 2 should be discovered but not expanded
        depth_2_nodes = ['/a/1', '/a/2', '/b/1']
        for path in depth_2_nodes:
            assert adapter.was_discovered(path), f"{path} should be discovered"
            assert adapter.was_expanded(path), f"{path} should be expanded (depth 2)"

        # Nodes at depth 3 (max depth) should be discovered but not expanded
        depth_3_nodes = ['/a/1/x', '/a/1/y']
        for path in depth_3_nodes:
            assert adapter.was_discovered(path), f"{path} should be discovered"
            assert not adapter.was_expanded(path), f"{path} should not be expanded (at max depth)"

    @pytest.mark.asyncio
    async def test_empty_tree_tracking(self):
        """Test tracking behavior with an empty tree (no children)."""
        mock_adapter = MockAdapter(tree_structure={'/': []})
        adapter = SmartCachingAdapter(mock_adapter, track_traversal=True)

        root = MockNode('/')
        children = list([c async for c in adapter.get_children(root)])

        # Root should still be expanded even with no children
        assert adapter.was_discovered('/')
        assert adapter.was_expanded('/')
        assert len(children) == 0

        # Statistics should reflect this
        stats = adapter.get_stats()
        assert stats['discovered_nodes'] == 1
        assert stats['expanded_nodes'] == 1

    @pytest.mark.asyncio
    async def test_single_node_tree(self):
        """Test tracking with a single-node tree."""
        mock_adapter = MockAdapter(tree_structure={})  # No entries = no children anywhere
        adapter = SmartCachingAdapter(mock_adapter, track_traversal=True)

        node = MockNode('/single')
        children = list([c async for c in adapter.get_children(node)])

        assert adapter.was_discovered('/single')
        assert adapter.was_expanded('/single')
        assert len(children) == 0


class TestDepthTracking:
    """Test depth tracking functionality."""

    @pytest.mark.asyncio
    async def test_depth_tracking_accuracy(self):
        """Test that depth is accurately tracked for discovered and expanded nodes."""
        mock_adapter = MockAdapter()
        adapter = SmartCachingAdapter(mock_adapter, track_traversal=True)

        # Traverse the tree
        async def traverse(node, expected_depth=0):
            actual_discovery_depth = adapter.get_discovery_depth(str(node.path))
            actual_expansion_depth = adapter.get_expansion_depth(str(node.path))

            # After get_children, both depths should match expected
            async for child in adapter.get_children(node):
                # Child should be discovered at parent_depth + 1
                child_discovery = adapter.get_discovery_depth(str(child.path))
                assert child_discovery == expected_depth + 1, \
                    f"Child {child.path} discovered at wrong depth"

                # Recurse
                await traverse(child, expected_depth + 1)

        root = MockNode('/')
        await traverse(root, 0)

        # Verify specific depths
        assert adapter.get_discovery_depth('/') == 0
        assert adapter.get_expansion_depth('/') == 0
        assert adapter.get_discovery_depth('/a') == 1
        assert adapter.get_expansion_depth('/a') == 1
        assert adapter.get_discovery_depth('/a/1') == 2
        assert adapter.get_expansion_depth('/a/1') == 2
        assert adapter.get_discovery_depth('/a/1/x') == 3
        assert adapter.get_expansion_depth('/a/1/x') == 3

    @pytest.mark.asyncio
    async def test_depth_statistics(self):
        """Test that depth statistics are correctly calculated."""
        mock_adapter = MockAdapter()
        adapter = SmartCachingAdapter(mock_adapter, track_traversal=True)

        # Traverse entire tree
        async def traverse(node):
            async for child in adapter.get_children(node):
                await traverse(child)

        root = MockNode('/')
        await traverse(root)

        stats = adapter.get_stats()

        # Check depth statistics
        assert 'max_discovered_depth' in stats
        assert 'avg_discovered_depth' in stats
        assert 'max_expanded_depth' in stats
        assert 'avg_expanded_depth' in stats

        # Max depth should be 3 (for /a/1/x and /a/1/y)
        assert stats['max_discovered_depth'] == 3
        # When we traverse the entire tree, leaf nodes at depth 3 also get expanded
        # (even though they have no children), so max expanded is also 3
        assert stats['max_expanded_depth'] == 3


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_repeated_traversal(self):
        """Test that repeated traversal doesn't double-count nodes."""
        mock_adapter = MockAdapter()
        adapter = SmartCachingAdapter(mock_adapter, track_traversal=True)

        root = MockNode('/')

        # First traversal
        async for child in adapter.get_children(root):
            pass

        first_stats = adapter.get_stats()

        # Second traversal of same node
        async for child in adapter.get_children(root):
            pass

        second_stats = adapter.get_stats()

        # Should not double-count discoveries
        assert first_stats['discovered_nodes'] == second_stats['discovered_nodes']
        # Expansion count shouldn't change either (same node)
        assert first_stats['expanded_nodes'] == second_stats['expanded_nodes']

    @pytest.mark.asyncio
    async def test_tracking_disabled(self):
        """Test behavior when tracking is disabled."""
        mock_adapter = MockAdapter()
        adapter = SmartCachingAdapter(mock_adapter, track_traversal=False)

        root = MockNode('/')
        async for child in adapter.get_children(root):
            pass

        # Should return False/None for all tracking queries
        assert not adapter.was_discovered('/')
        assert not adapter.was_expanded('/')
        assert adapter.get_discovery_depth('/') is None
        assert adapter.get_expansion_depth('/') is None

        stats = adapter.get_stats()
        assert stats['tracking_enabled'] == False

    @pytest.mark.asyncio
    async def test_path_normalization(self):
        """Test that Windows-style paths are properly normalized."""
        mock_adapter = MockAdapter()
        adapter = SmartCachingAdapter(mock_adapter, track_traversal=True)

        # Use Windows-style path
        node = MockNode('C:\\Users\\Test')

        async for child in adapter.get_children(node):
            pass

        # The adapter should normalize internally to forward slashes
        # Check that it was tracked (with forward slashes internally)
        assert adapter.was_discovered('C:/Users/Test'), "Should discover with normalized path"
        assert adapter.was_expanded('C:/Users/Test'), "Should expand with normalized path"

    @pytest.mark.asyncio
    async def test_clear_tracking(self):
        """Test that clear_tracking resets all tracking state."""
        mock_adapter = MockAdapter()
        adapter = SmartCachingAdapter(mock_adapter, track_traversal=True)

        root = MockNode('/')
        async for child in adapter.get_children(root):
            pass

        # Verify tracking exists
        assert adapter.was_discovered('/')
        assert adapter.was_expanded('/')

        # Clear tracking
        adapter.clear_tracking()

        # Should be reset
        assert not adapter.was_discovered('/')
        assert not adapter.was_expanded('/')
        assert adapter.get_discovery_depth('/') is None

        stats = adapter.get_stats()
        assert stats['discovered_nodes'] == 0
        assert stats['expanded_nodes'] == 0


class TestCacheInteraction:
    """Test interaction between caching and tracking."""

    @pytest.mark.asyncio
    async def test_cached_children_tracked_as_discovered(self):
        """Test that children returned from cache are still tracked as discovered."""
        mock_adapter = MockAdapter()
        adapter = SmartCachingAdapter(
            mock_adapter,
            track_traversal=True,
            max_memory_mb=100
        )

        root = MockNode('/')

        # First traversal (cache miss)
        children1 = []
        async for child in adapter.get_children(root):
            children1.append(str(child.path))

        # Second traversal (cache hit)
        children2 = []
        async for child in adapter.get_children(root):
            children2.append(str(child.path))

        # Children should be discovered regardless of cache
        for child_path in children1:
            assert adapter.was_discovered(child_path)

        # Check cache was used
        stats = adapter.get_stats()
        assert stats.get('hit_rate', 0) > 0, "Cache should have been hit"

    @pytest.mark.asyncio
    async def test_cache_disabled_tracking_enabled(self):
        """Test that tracking works even when caching is disabled."""
        mock_adapter = MockAdapter()
        adapter = SmartCachingAdapter(
            mock_adapter,
            track_traversal=True,
            max_memory_mb=-1  # Disable caching
        )

        root = MockNode('/')
        async for child in adapter.get_children(root):
            pass

        # Tracking should still work
        assert adapter.was_discovered('/')
        assert adapter.was_expanded('/')
        assert adapter.was_discovered('/a')

        # But cache should be disabled
        stats = adapter.get_stats()
        assert stats['cache_enabled'] == False
        assert stats['tracking_enabled'] == True


class TestStatistics:
    """Test statistics and monitoring functionality."""

    @pytest.mark.asyncio
    async def test_comprehensive_statistics(self):
        """Test that get_stats returns comprehensive information."""
        mock_adapter = MockAdapter()
        adapter = SmartCachingAdapter(
            mock_adapter,
            track_traversal=True,
            max_memory_mb=100
        )

        # Do some traversal
        root = MockNode('/')
        async for child in adapter.get_children(root):
            async for grandchild in adapter.get_children(child):
                pass

        stats = adapter.get_stats()

        # Check all expected keys
        assert 'cache_enabled' in stats
        assert 'tracking_enabled' in stats
        assert 'discovered_nodes' in stats
        assert 'expanded_nodes' in stats
        assert 'max_discovered_depth' in stats
        assert 'avg_discovered_depth' in stats
        assert 'max_expanded_depth' in stats
        assert 'avg_expanded_depth' in stats

        # Verify counts
        assert stats['discovered_nodes'] > 0
        assert stats['expanded_nodes'] > 0
        assert stats['discovered_nodes'] >= stats['expanded_nodes']