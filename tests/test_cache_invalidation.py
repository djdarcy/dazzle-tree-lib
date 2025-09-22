"""
Tests for manual cache invalidation functionality (Issue #32).

This module tests the invalidate() and invalidate_all() methods
of the CompletenessAwareCacheAdapter.
"""

import asyncio
from pathlib import Path
import pytest
import time
from typing import AsyncIterator, Any, List

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

    async def identifier(self) -> str:
        """Return path as string identifier."""
        return str(self.path)

    async def metadata(self):
        """Return mock metadata."""
        return self.metadata_value


class MockAdapter:
    """Mock adapter for testing."""

    def __init__(self):
        self.children_data = {}

    def set_children(self, path: Path, children: List[MockNode]):
        """Set children for a specific path."""
        self.children_data[str(path)] = children

    async def get_children(self, node: Any) -> AsyncIterator[Any]:
        """Return mock children."""
        path_str = str(node.path)
        children = self.children_data.get(path_str, [])
        for child in children:
            yield child


@pytest.mark.asyncio
class TestCacheInvalidation:
    """Test suite for cache invalidation functionality."""

    async def test_invalidate_single_path(self):
        """Test invalidating a single path removes all depth variants."""
        # Create mock adapter
        base_adapter = MockAdapter()
        cache_adapter = CompletenessAwareCacheAdapter(
            base_adapter,
            enable_oom_protection=True
        )

        # Setup mock data
        dir1_path = Path("/test/dir1")
        dir2_path = Path("/test/dir2")

        base_adapter.set_children(dir1_path, [
            MockNode(Path("/test/dir1/subdir1")),
            MockNode(Path("/test/dir1/subdir2"))
        ])
        base_adapter.set_children(dir2_path, [
            MockNode(Path("/test/dir2/subdir1"))
        ])

        # Populate cache with different depths
        node1 = MockNode(dir1_path)
        node2 = MockNode(dir2_path)

        # Get children to populate cache
        async for _ in cache_adapter.get_children(node1):
            pass
        async for _ in cache_adapter.get_children(node2):
            pass

        # Verify cache has entries
        assert len(cache_adapter.cache) > 0
        initial_entries = len(cache_adapter.cache)

        # Invalidate dir1
        count = await cache_adapter.invalidate(dir1_path)

        # Should have removed entries for dir1
        assert count > 0
        assert len(cache_adapter.cache) < initial_entries

        # Verify dir1 entries are gone but dir2 remains
        for key in cache_adapter.cache:
            # Extract path from key tuple (index 3)
            if isinstance(key, tuple) and len(key) >= 5:
                key_path = key[3]
                assert "dir1" not in key_path

    async def test_invalidate_deep(self):
        """Test deep invalidation removes path and all descendants."""
        base_adapter = MockAdapter()
        cache_adapter = CompletenessAwareCacheAdapter(
            base_adapter,
            enable_oom_protection=True
        )

        # Setup nested structure
        root_path = Path("/test/root")
        child1_path = Path("/test/root/child1")
        child2_path = Path("/test/root/child2")
        grandchild_path = Path("/test/root/child1/grandchild1")
        other_path = Path("/test/other")

        base_adapter.set_children(root_path, [
            MockNode(child1_path),
            MockNode(child2_path)
        ])
        base_adapter.set_children(child1_path, [
            MockNode(grandchild_path)
        ])
        base_adapter.set_children(child2_path, [])
        base_adapter.set_children(grandchild_path, [])
        base_adapter.set_children(other_path, [
            MockNode(Path("/test/other/sub"))
        ])

        # Populate cache
        for path in [root_path, child1_path, child2_path, grandchild_path, other_path]:
            node = MockNode(path)
            async for _ in cache_adapter.get_children(node):
                pass

        # Count entries related to root
        root_entries = sum(
            1 for key in cache_adapter.cache
            if isinstance(key, tuple) and len(key) >= 5 and "root" in key[3]
        )
        assert root_entries > 0

        # Deep invalidate root
        count = await cache_adapter.invalidate(root_path, deep=True)

        # Should have removed all root-related entries
        assert count == root_entries

        # Verify no root entries remain
        for key in cache_adapter.cache:
            if isinstance(key, tuple) and len(key) >= 5:
                key_path = key[3]
                assert "root" not in key_path

        # Other entries should remain
        other_entries = sum(
            1 for key in cache_adapter.cache
            if isinstance(key, tuple) and len(key) >= 5 and "other" in key[3]
        )
        assert other_entries > 0

    async def test_invalidate_all(self):
        """Test invalidate_all clears entire cache."""
        base_adapter = MockAdapter()
        cache_adapter = CompletenessAwareCacheAdapter(
            base_adapter,
            enable_oom_protection=True
        )

        # Setup structure
        paths = [
            Path("/test/dir0"),
            Path("/test/dir1"),
            Path("/test/dir2")
        ]

        for path in paths:
            base_adapter.set_children(path, [
                MockNode(path / "subdir")
            ])

        # Populate cache
        for path in paths:
            node = MockNode(path)
            async for _ in cache_adapter.get_children(node):
                pass

        # Verify cache populated
        initial_count = len(cache_adapter.cache)
        assert initial_count > 0
        assert cache_adapter.current_memory > 0

        # Clear all
        count = await cache_adapter.invalidate_all()

        # Verify everything cleared
        assert count == initial_count
        assert len(cache_adapter.cache) == 0
        assert cache_adapter.current_memory == 0
        assert len(cache_adapter.node_completeness) == 0

    async def test_invalidate_nonexistent_path(self):
        """Test invalidating non-existent path returns 0."""
        base_adapter = MockAdapter()
        cache_adapter = CompletenessAwareCacheAdapter(
            base_adapter,
            enable_oom_protection=True
        )

        # Invalidate path that doesn't exist
        count = await cache_adapter.invalidate("/nonexistent/path")

        assert count == 0
        assert cache_adapter.invalidations == 0

    async def test_invalidate_updates_statistics(self):
        """Test that invalidation updates statistics correctly."""
        base_adapter = MockAdapter()
        cache_adapter = CompletenessAwareCacheAdapter(
            base_adapter,
            enable_oom_protection=True
        )

        test_path = Path("/test/path")
        base_adapter.set_children(test_path, [
            MockNode(Path("/test/path/child"))
        ])

        # Populate cache
        node = MockNode(test_path)
        async for _ in cache_adapter.get_children(node):
            pass

        initial_invalidations = cache_adapter.invalidations

        # Invalidate
        count = await cache_adapter.invalidate(test_path)

        # Check statistics updated
        assert cache_adapter.invalidations == initial_invalidations + count

        stats = cache_adapter.get_stats()
        assert "invalidations" in stats
        assert stats["invalidations"] == cache_adapter.invalidations

    async def test_invalidate_memory_tracking(self):
        """Test that invalidation correctly updates memory tracking."""
        base_adapter = MockAdapter()
        cache_adapter = CompletenessAwareCacheAdapter(
            base_adapter,
            enable_oom_protection=True  # Enable memory tracking
        )

        # Create multiple paths
        paths = [Path(f"/test/dir{i}") for i in range(5)]
        for path in paths:
            base_adapter.set_children(path, [
                MockNode(path / "file.txt")
            ])

        # Populate cache
        for path in paths:
            node = MockNode(path)
            async for _ in cache_adapter.get_children(node):
                pass

        initial_memory = cache_adapter.current_memory
        assert initial_memory > 0

        # Invalidate one directory
        await cache_adapter.invalidate(paths[0], deep=True)

        # Memory should decrease
        assert cache_adapter.current_memory < initial_memory

        # Clear all
        await cache_adapter.invalidate_all()

        # Memory should be zero
        assert cache_adapter.current_memory == 0

    async def test_invalidate_completeness_tracking(self):
        """Test that invalidation cleans up completeness tracking."""
        base_adapter = MockAdapter()
        cache_adapter = CompletenessAwareCacheAdapter(
            base_adapter,
            enable_oom_protection=True
        )

        tracked_path = Path("/test/tracked")
        sub_path = Path("/test/tracked/sub")

        base_adapter.set_children(tracked_path, [MockNode(sub_path)])
        base_adapter.set_children(sub_path, [])

        # Populate cache - this triggers completeness tracking
        node = MockNode(tracked_path)
        async for _ in cache_adapter.get_children(node):
            pass

        # Force some completeness tracking
        cache_adapter.node_completeness[str(tracked_path)] = 1

        # Check completeness tracking exists
        assert len(cache_adapter.node_completeness) > 0

        # Deep invalidate
        await cache_adapter.invalidate(tracked_path, deep=True)

        # Completeness tracking for "tracked" should be gone
        for path in cache_adapter.node_completeness:
            assert "tracked" not in path

    async def test_invalidate_windows_paths(self):
        """Test that invalidation handles Windows-style paths correctly."""
        base_adapter = MockAdapter()
        cache_adapter = CompletenessAwareCacheAdapter(
            base_adapter,
            enable_oom_protection=True
        )

        # Use a Windows-style path
        win_path = Path("C:\\test\\windir")
        base_adapter.set_children(win_path, [
            MockNode(Path("C:\\test\\windir\\subdir"))
        ])

        # Populate cache
        node = MockNode(win_path)
        async for _ in cache_adapter.get_children(node):
            pass

        assert len(cache_adapter.cache) > 0

        # Try invalidating with backslashes (Windows style)
        count = await cache_adapter.invalidate(str(win_path))

        # Should still work despite path style difference
        assert count > 0

    async def test_invalidate_with_bypass_interaction(self):
        """Test that invalidation works correctly with bypass feature."""
        base_adapter = MockAdapter()
        cache_adapter = CompletenessAwareCacheAdapter(
            base_adapter,
            enable_oom_protection=True
        )

        data_path = Path("/test/data")
        base_adapter.set_children(data_path, [
            MockNode(Path("/test/data/file.txt"))
        ])

        node = MockNode(data_path)

        # First access - populates cache
        async for _ in cache_adapter.get_children(node):
            pass

        assert cache_adapter.hits == 0
        assert cache_adapter.misses == 1

        # Invalidate the cache
        count = await cache_adapter.invalidate(data_path)
        assert count > 0

        # Next access should miss (cache was invalidated)
        async for _ in cache_adapter.get_children(node):
            pass

        assert cache_adapter.misses == 2

        # Bypass should still work after invalidation
        async for _ in cache_adapter.get_children(node, use_cache=False):
            pass

        assert cache_adapter.bypasses == 1

    async def test_invalidate_fast_mode(self):
        """Test invalidation works in fast mode (no OOM protection)."""
        base_adapter = MockAdapter()
        cache_adapter = CompletenessAwareCacheAdapter(
            base_adapter,
            enable_oom_protection=False  # Fast mode
        )

        fast_path = Path("/test/fast")
        base_adapter.set_children(fast_path, [
            MockNode(Path("/test/fast/child"))
        ])

        # Populate cache
        node = MockNode(fast_path)
        async for _ in cache_adapter.get_children(node):
            pass

        initial_count = len(cache_adapter.cache)
        assert initial_count > 0

        # Invalidate in fast mode
        count = await cache_adapter.invalidate(fast_path)

        assert count > 0
        assert len(cache_adapter.cache) < initial_count

        # Repopulate
        async for _ in cache_adapter.get_children(node):
            pass

        # invalidate_all in fast mode
        await cache_adapter.invalidate_all()
        assert len(cache_adapter.cache) == 0

    async def test_deep_invalidate_root_optimization(self):
        """Test that deep invalidating root path uses optimized path."""
        base_adapter = MockAdapter()
        cache_adapter = CompletenessAwareCacheAdapter(
            base_adapter,
            enable_oom_protection=True
        )

        # Setup paths
        paths = [Path(f"/dir{i}") for i in range(3)]
        for path in paths:
            base_adapter.set_children(path, [
                MockNode(path / "child")
            ])

        # Populate cache
        for path in paths:
            node = MockNode(path)
            async for _ in cache_adapter.get_children(node):
                pass

        initial_count = len(cache_adapter.cache)

        # Deep invalidate "/" should call invalidate_all
        count = await cache_adapter.invalidate("/", deep=True)

        assert count == initial_count
        assert len(cache_adapter.cache) == 0

    async def test_concurrent_invalidation(self):
        """Test that concurrent invalidations don't cause issues."""
        base_adapter = MockAdapter()
        cache_adapter = CompletenessAwareCacheAdapter(
            base_adapter,
            enable_oom_protection=True
        )

        # Create multiple directories
        paths = []
        for i in range(10):
            path = Path(f"/test/dir{i}")
            paths.append(path)
            base_adapter.set_children(path, [
                MockNode(path / "sub")
            ])

        # Populate cache
        for path in paths:
            node = MockNode(path)
            async for _ in cache_adapter.get_children(node):
                pass

        # Concurrent invalidations
        tasks = []
        for path in paths:
            task = cache_adapter.invalidate(path)
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        # All should succeed
        assert all(r >= 0 for r in results)
        assert sum(results) > 0

        # Cache should be empty after invalidating all paths
        assert len(cache_adapter.cache) == 0

    async def test_invalidate_multiple_depths(self):
        """Test invalidating a path removes all depth variants."""
        base_adapter = MockAdapter()
        cache_adapter = CompletenessAwareCacheAdapter(
            base_adapter,
            enable_oom_protection=True
        )

        # Setup path with children
        test_path = Path("/test/multi")
        base_adapter.set_children(test_path, [
            MockNode(Path("/test/multi/child1")),
            MockNode(Path("/test/multi/child2"))
        ])

        node = MockNode(test_path)

        # Access with different depth contexts to create multiple cache entries
        # This simulates what happens when traverse_tree_async is called with different max_depth values

        # First access with implicit depth
        async for _ in cache_adapter.get_children(node):
            pass

        # Check we have cache entries
        cache_keys_before = list(cache_adapter.cache.keys())
        assert len(cache_keys_before) > 0

        # Invalidate the path
        count = await cache_adapter.invalidate(test_path)

        # Should have removed all entries for this path
        assert count > 0
        assert len(cache_adapter.cache) == 0

        # Verify the path is completely gone from cache
        for key in cache_adapter.cache:
            if isinstance(key, tuple) and len(key) >= 5:
                assert str(test_path) not in key[3]

    async def test_invalidate_node_basic(self):
        """Test invalidating a single node."""
        # Create adapter with cache
        mock_adapter = MockAdapter()
        cache_adapter = CompletenessAwareCacheAdapter(mock_adapter, enable_oom_protection=False)

        # Create and populate a node
        test_node = MockNode(Path("/test/path"))
        child_node = MockNode(Path("/test/path/child"))
        mock_adapter.set_children(test_node.path, [child_node])

        # Get children to populate cache
        async for _ in cache_adapter.get_children(test_node):
            pass

        # Cache should have the entry
        assert len(cache_adapter.cache) > 0

        # Invalidate using the node directly
        count = await cache_adapter.invalidate_node(test_node)

        # Should have invalidated the entry
        assert count == 1
        assert len(cache_adapter.cache) == 0

    async def test_invalidate_node_deep(self):
        """Test deep invalidation via node."""
        # Create adapter with cache
        mock_adapter = MockAdapter()
        cache_adapter = CompletenessAwareCacheAdapter(mock_adapter, enable_oom_protection=False)

        # Create hierarchy
        root_node = MockNode(Path("/root"))
        child_node = MockNode(Path("/root/child"))
        grandchild_node = MockNode(Path("/root/child/grandchild"))

        # Set up mock adapter hierarchy
        mock_adapter.set_children(root_node.path, [child_node])
        mock_adapter.set_children(child_node.path, [grandchild_node])
        mock_adapter.set_children(grandchild_node.path, [])

        # Populate cache at various levels
        async for _ in cache_adapter.get_children(root_node):
            pass
        async for _ in cache_adapter.get_children(child_node):
            pass
        async for _ in cache_adapter.get_children(grandchild_node):
            pass

        initial_count = len(cache_adapter.cache)
        assert initial_count >= 3

        # Deep invalidate from root using node
        count = await cache_adapter.invalidate_node(root_node, deep=True)

        # Should have invalidated all entries
        assert count == initial_count
        assert len(cache_adapter.cache) == 0

    async def test_invalidate_node_none_raises(self):
        """Test that None node raises ValueError."""
        mock_adapter = MockAdapter()
        cache_adapter = CompletenessAwareCacheAdapter(mock_adapter, enable_oom_protection=False)

        # Should raise ValueError for None node
        with pytest.raises(ValueError, match="Cannot invalidate None node"):
            await cache_adapter.invalidate_node(None)

    async def test_invalidate_nodes_batch(self):
        """Test batch node invalidation."""
        # Create adapter with cache
        mock_adapter = MockAdapter()
        cache_adapter = CompletenessAwareCacheAdapter(mock_adapter, enable_oom_protection=False)

        # Create multiple nodes
        nodes = [
            MockNode(Path("/path1")),
            MockNode(Path("/path2")),
            MockNode(Path("/path3"))
        ]

        # Populate cache for each node
        for node in nodes:
            mock_adapter.set_children(node.path, [])
            async for _ in cache_adapter.get_children(node):
                pass

        assert len(cache_adapter.cache) == 3

        # Invalidate all nodes at once
        count = await cache_adapter.invalidate_nodes(nodes)

        # Should have invalidated all entries
        assert count == 3
        assert len(cache_adapter.cache) == 0

    async def test_invalidate_nodes_ignore_errors(self):
        """Test ignore_errors flag in batch invalidation."""
        # Create adapter with cache
        mock_adapter = MockAdapter()
        cache_adapter = CompletenessAwareCacheAdapter(mock_adapter, enable_oom_protection=False)

        # Create good nodes
        good_node1 = MockNode(Path("/good1"))
        good_node2 = MockNode(Path("/good2"))

        # Populate cache for good nodes
        mock_adapter.set_children(good_node1.path, [])
        mock_adapter.set_children(good_node2.path, [])
        async for _ in cache_adapter.get_children(good_node1):
            pass
        async for _ in cache_adapter.get_children(good_node2):
            pass

        # Mix of good and bad nodes - put None first to test properly
        mixed_nodes = [None, good_node1, good_node2]

        # Without ignore_errors, should raise immediately on None
        with pytest.raises(ValueError, match="Cannot invalidate None node"):
            await cache_adapter.invalidate_nodes(mixed_nodes, ignore_errors=False)

        # Cache should still have both entries after failed attempt
        assert len(cache_adapter.cache) == 2

        # With ignore_errors, should continue past None
        count = await cache_adapter.invalidate_nodes(mixed_nodes, ignore_errors=True)

        # Should have invalidated the good nodes
        assert count == 2
        assert len(cache_adapter.cache) == 0

    async def test_invalidate_nodes_empty(self):
        """Test empty node list returns 0."""
        mock_adapter = MockAdapter()
        cache_adapter = CompletenessAwareCacheAdapter(mock_adapter, enable_oom_protection=False)

        # Empty list should return 0 without error
        count = await cache_adapter.invalidate_nodes([])
        assert count == 0

    async def test_invalidate_nodes_duplicates(self):
        """Test duplicate nodes handled correctly."""
        # Create adapter with cache
        mock_adapter = MockAdapter()
        cache_adapter = CompletenessAwareCacheAdapter(mock_adapter, enable_oom_protection=False)

        # Create a node
        node = MockNode(Path("/test"))

        # Populate cache
        mock_adapter.set_children(node.path, [])
        async for _ in cache_adapter.get_children(node):
            pass
        assert len(cache_adapter.cache) == 1

        # Pass same node multiple times
        count = await cache_adapter.invalidate_nodes([node, node, node])

        # Should invalidate once (idempotent)
        assert count == 1  # First invalidation succeeds, others find nothing
        assert len(cache_adapter.cache) == 0

    async def test_invalidate_node_with_identifier_method(self):
        """Test that node's identifier() method is properly called."""
        # Create a custom node class with identifier method
        class CustomNode:
            def __init__(self, path: str):
                self.path = Path(path)

            async def identifier(self) -> str:
                """Return path as string identifier."""
                return str(self.path)

            async def metadata(self):
                """Return mock metadata."""
                return {'modified_time': time.time()}

        # Create adapter with cache
        mock_adapter = MockAdapter()
        cache_adapter = CompletenessAwareCacheAdapter(mock_adapter, enable_oom_protection=False)

        # Create custom node and populate cache
        custom_node = CustomNode("/custom/path")

        # Manually add to cache (since get_children expects MockAdapter)
        cache_key = cache_adapter._get_cache_key(custom_node.path, 1)
        from dazzletreelib.aio.adapters.cache_completeness_adapter import CacheEntry
        cache_adapter.cache[cache_key] = CacheEntry(
            data=[],  # Empty children list
            depth=1,
            mtime=time.time()
        )

        assert len(cache_adapter.cache) == 1

        # Invalidate using the custom node
        count = await cache_adapter.invalidate_node(custom_node)

        # Should have worked via identifier() method
        assert count == 1
        assert len(cache_adapter.cache) == 0