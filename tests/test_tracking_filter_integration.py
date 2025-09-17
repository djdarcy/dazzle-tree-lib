"""
Test filter and tracking interactions.

This module tests how filtering affects discovery and expansion tracking
in the SmartCachingAdapter.
"""

import pytest
import asyncio
from typing import Any, AsyncIterator, Optional
from pathlib import Path

from dazzletreelib.aio.adapters.smart_caching import SmartCachingAdapter
from dazzletreelib.aio.core import AsyncTreeAdapter


class FilterNode:
    """Simple node for filtering tests."""

    def __init__(self, path, depth=None, metadata=None):
        self.path = path
        self.depth = depth if depth is not None else self._calculate_depth(path)
        self.metadata = metadata or {}

    def _calculate_depth(self, path):
        """Calculate depth from path."""
        if path == '/':
            return 0
        parts = [p for p in str(path).split('/') if p]
        return len(parts)

    def __str__(self):
        return str(self.path)


class MockFilterAdapter:
    """Mock adapter for filter testing."""

    def __init__(self, tree_structure=None):
        self.tree = tree_structure or {
            '/': ['/docs', '/src', '/tests', '/hidden'],
            '/docs': ['/docs/api', '/docs/guide'],
            '/docs/api': ['/docs/api/index.md'],
            '/src': ['/src/core', '/src/utils'],
            '/src/core': ['/src/core/main.py', '/src/core/helper.py'],
            '/tests': ['/tests/unit', '/tests/integration'],
            '/hidden': ['/hidden/.git', '/hidden/.env'],
        }

    async def get_children(self, node):
        """Yield children for a node."""
        path = str(node.path) if hasattr(node, 'path') else str(node)
        children_paths = self.tree.get(path, [])

        for child_path in children_paths:
            metadata = {}
            # Add metadata for specific nodes
            if '.git' in child_path or '.env' in child_path:
                metadata['hidden'] = True
            if child_path.endswith('.py'):
                metadata['type'] = 'python'
            if child_path.endswith('.md'):
                metadata['type'] = 'markdown'

            yield FilterNode(child_path, metadata=metadata)

    async def get_depth(self, node):
        """Return node depth."""
        if hasattr(node, 'depth'):
            return node.depth
        path = str(node.path) if hasattr(node, 'path') else str(node)
        if path == '/':
            return 0
        parts = [p for p in path.split('/') if p]
        return len(parts)

    async def get_parent(self, node):
        """Return parent node."""
        return None


class FilteringWrapper(AsyncTreeAdapter):
    """Simple filtering wrapper for tests."""

    def __init__(self, base_adapter, node_filter=None):
        self.base_adapter = base_adapter
        self.node_filter = node_filter

    async def get_children(self, node):
        """Get filtered children."""
        async for child in self.base_adapter.get_children(node):
            if self.node_filter is None or self.node_filter(child):
                yield child

    async def get_depth(self, node):
        """Delegate to base adapter."""
        return await self.base_adapter.get_depth(node)

    async def get_parent(self, node):
        """Delegate to base adapter."""
        return await self.base_adapter.get_parent(node)


class TestFilteringWithTracking:
    """Test filter and tracking interactions."""

    @pytest.mark.skip("Filter/tracking layer order - See Issue #43")
    @pytest.mark.asyncio
    async def test_filtered_nodes_not_discovered(self):
        """Test that filtered-out nodes are not marked as discovered."""
        mock_adapter = MockFilterAdapter()
        caching_adapter = SmartCachingAdapter(
            mock_adapter,
            track_traversal=True,
            max_memory_mb=100
        )

        # Create filter that excludes hidden files
        def exclude_hidden(node):
            path = str(node.path)
            return not any(part.startswith('.') for part in path.split('/'))

        filtering_adapter = FilteringWrapper(
            caching_adapter,
            node_filter=exclude_hidden
        )

        # Traverse with filter
        discovered = []
        root = FilterNode('/')

        async def traverse(node):
            async for child in filtering_adapter.get_children(node):
                discovered.append(str(child.path))
                await traverse(child)

        await traverse(root)

        # Verify filtered nodes are NOT discovered
        assert not caching_adapter.was_discovered('/hidden/.git'), ".git should not be discovered (filtered)"
        assert not caching_adapter.was_discovered('/hidden/.env'), ".env should not be discovered (filtered)"

        # Verify parent of filtered nodes IS discovered and expanded
        assert caching_adapter.was_discovered('/hidden'), "/hidden should be discovered"
        assert caching_adapter.was_expanded('/hidden'), "/hidden should be expanded"

        # Verify non-filtered nodes ARE discovered
        assert caching_adapter.was_discovered('/docs'), "/docs should be discovered"
        assert caching_adapter.was_discovered('/src'), "/src should be discovered"

    @pytest.mark.skip("Filter/tracking layer order - See Issue #43")
    @pytest.mark.asyncio
    async def test_filter_change_during_traversal(self):
        """Test changing filter during traversal affects tracking."""
        mock_adapter = MockFilterAdapter()
        caching_adapter = SmartCachingAdapter(
            mock_adapter,
            track_traversal=True,
            max_memory_mb=100
        )

        # Start with no filter
        filtering_adapter = FilteringWrapper(
            caching_adapter,
            node_filter=None
        )

        root = FilterNode('/')

        # First traversal - no filter
        first_discovered = []
        async for child in filtering_adapter.get_children(root):
            first_discovered.append(str(child.path))

        # All children should be discovered
        assert caching_adapter.was_discovered('/docs')
        assert caching_adapter.was_discovered('/hidden')

        # Change filter to exclude hidden
        def exclude_hidden(node):
            path = str(node.path)
            return not any(part.startswith('.') for part in path.split('/'))

        filtering_adapter.node_filter = exclude_hidden

        # Clear tracking to test fresh
        caching_adapter.clear_tracking()

        # Second traversal - with filter
        second_discovered = []
        async for child in filtering_adapter.get_children(root):
            second_discovered.append(str(child.path))

        # Hidden should be discovered but its hidden children should not
        assert caching_adapter.was_discovered('/hidden')
        assert len(first_discovered) > len(second_discovered), "Filter should reduce discovered nodes"

    @pytest.mark.skip("Filter/tracking layer order - See Issue #43")
    @pytest.mark.asyncio
    async def test_depth_filter_tracking_boundary(self):
        """Test that depth filtering correctly tracks nodes at boundary."""
        mock_adapter = MockFilterAdapter()
        caching_adapter = SmartCachingAdapter(
            mock_adapter,
            track_traversal=True,
            max_memory_mb=100
        )

        # Filter to max depth 2
        def depth_filter(node):
            return node.depth <= 2

        filtering_adapter = FilteringWrapper(
            caching_adapter,
            node_filter=depth_filter
        )

        root = FilterNode('/')

        async def traverse(node, depth=0):
            if depth <= 2:  # Only traverse to depth 2
                async for child in filtering_adapter.get_children(node):
                    await traverse(child, depth + 1)

        await traverse(root)

        # Depth 0 (root)
        assert caching_adapter.was_discovered('/')
        assert caching_adapter.was_expanded('/')

        # Depth 1
        assert caching_adapter.was_discovered('/docs')
        assert caching_adapter.was_expanded('/docs')

        # Depth 2 - should be discovered but their children (depth 3) should not
        assert caching_adapter.was_discovered('/docs/api')
        assert caching_adapter.was_expanded('/docs/api')

        # Depth 3 - should NOT be discovered (filtered by depth)
        assert not caching_adapter.was_discovered('/docs/api/index.md'), "Depth 3 should be filtered"

    @pytest.mark.skip("Filter/tracking layer order - See Issue #43")
    @pytest.mark.asyncio
    async def test_custom_filter_tracking_behavior(self):
        """Test custom filter logic with tracking."""
        mock_adapter = MockFilterAdapter()
        caching_adapter = SmartCachingAdapter(
            mock_adapter,
            track_traversal=True,
            max_memory_mb=100
        )

        # Filter that only allows Python files and directories
        def python_only_filter(node):
            path = str(node.path)
            # Allow directories (to traverse into them)
            if not path.endswith('.py') and '.' in path.split('/')[-1]:
                return False  # Reject non-Python files
            return True

        filtering_adapter = FilteringWrapper(
            caching_adapter,
            node_filter=python_only_filter
        )

        root = FilterNode('/')

        discovered = []
        async def traverse(node):
            async for child in filtering_adapter.get_children(node):
                discovered.append(str(child.path))
                await traverse(child)

        await traverse(root)

        # Python files should be discovered
        assert caching_adapter.was_discovered('/src/core/main.py'), "Python files should be discovered"
        assert caching_adapter.was_discovered('/src/core/helper.py'), "Python files should be discovered"

        # Non-Python files should NOT be discovered
        assert not caching_adapter.was_discovered('/docs/api/index.md'), "Markdown files should be filtered"

        # Directories should still be discovered (to traverse into them)
        assert caching_adapter.was_discovered('/docs'), "Directories should be discovered"
        assert caching_adapter.was_discovered('/src'), "Directories should be discovered"

    @pytest.mark.skip("Filter/tracking layer order - See Issue #43")
    @pytest.mark.asyncio
    async def test_filter_cache_tracking_combination(self):
        """Test filter + cache + tracking working together."""
        mock_adapter = MockFilterAdapter()
        caching_adapter = SmartCachingAdapter(
            mock_adapter,
            track_traversal=True,
            max_memory_mb=100
        )

        # Simple filter
        def no_tests_filter(node):
            path = str(node.path)
            return '/tests' not in path

        filtering_adapter = FilteringWrapper(
            caching_adapter,
            node_filter=no_tests_filter
        )

        root = FilterNode('/')

        # First traversal - populate cache
        first_discovered = []
        async def traverse1(node):
            async for child in filtering_adapter.get_children(node):
                first_discovered.append(str(child.path))
                await traverse1(child)

        await traverse1(root)

        # Check cache stats
        stats1 = caching_adapter.get_stats()
        initial_discovered = stats1['discovered_nodes']

        # Second traversal - should hit cache
        second_discovered = []
        async def traverse2(node):
            async for child in filtering_adapter.get_children(node):
                second_discovered.append(str(child.path))
                await traverse2(child)

        await traverse2(root)

        # Check cache was used
        stats2 = caching_adapter.get_stats()
        if 'hit_rate' in stats2:
            assert stats2['hit_rate'] > 0, "Cache should have hits on second traversal"

        # Discovered nodes shouldn't increase (same nodes)
        assert stats2['discovered_nodes'] == initial_discovered, "No new discoveries on cached traversal"

        # Filtered nodes should never appear
        assert not caching_adapter.was_discovered('/tests'), "/tests should be filtered"
        assert not caching_adapter.was_discovered('/tests/unit'), "/tests/unit should be filtered"

    @pytest.mark.skip("Filter/tracking layer order - See Issue #43")
    @pytest.mark.asyncio
    async def test_filter_affects_expansion_not_discovery_parent(self):
        """Test that parent nodes are expanded even if children are filtered."""
        mock_adapter = MockFilterAdapter()
        caching_adapter = SmartCachingAdapter(
            mock_adapter,
            track_traversal=True,
            max_memory_mb=100
        )

        # Filter that excludes all children of /hidden
        def exclude_hidden_children(node):
            path = str(node.path)
            if path.startswith('/hidden/'):
                return False
            return True

        filtering_adapter = FilteringWrapper(
            caching_adapter,
            node_filter=exclude_hidden_children
        )

        root = FilterNode('/')

        # Traverse
        async def traverse(node):
            async for child in filtering_adapter.get_children(node):
                await traverse(child)

        await traverse(root)

        # /hidden should be discovered AND expanded
        assert caching_adapter.was_discovered('/hidden'), "/hidden should be discovered"
        assert caching_adapter.was_expanded('/hidden'), "/hidden should be expanded (even though children filtered)"

        # But its children should NOT be discovered
        assert not caching_adapter.was_discovered('/hidden/.git'), "Filtered children not discovered"
        assert not caching_adapter.was_discovered('/hidden/.env'), "Filtered children not discovered"

    @pytest.mark.skip("Filter/tracking layer order - See Issue #43")
    @pytest.mark.asyncio
    async def test_filter_performance_with_tracking(self):
        """Test that filtering doesn't significantly impact tracking performance."""
        # Create a larger tree
        large_tree = {'/': []}
        for i in range(100):
            dir_path = f'/dir{i}'
            large_tree['/'].append(dir_path)
            large_tree[dir_path] = []
            for j in range(10):
                file_path = f'{dir_path}/file{j}.txt'
                large_tree[dir_path].append(file_path)

        mock_adapter = MockFilterAdapter(large_tree)
        caching_adapter = SmartCachingAdapter(
            mock_adapter,
            track_traversal=True,
            max_memory_mb=100
        )

        # Filter that excludes half the directories
        def even_dirs_only(node):
            path = str(node.path)
            if '/dir' in path:
                try:
                    dir_num = int(path.split('dir')[1].split('/')[0])
                    return dir_num % 2 == 0
                except:
                    return True
            return True

        filtering_adapter = FilteringWrapper(
            caching_adapter,
            node_filter=even_dirs_only
        )

        root = FilterNode('/')

        import time
        start = time.time()

        discovered_count = 0
        async def traverse(node):
            nonlocal discovered_count
            async for child in filtering_adapter.get_children(node):
                discovered_count += 1
                await traverse(child)

        await traverse(root)

        elapsed = time.time() - start

        # Performance check
        assert elapsed < 2.0, f"Filtered traversal too slow: {elapsed:.2f}s"

        # Verify filtering worked
        assert caching_adapter.was_discovered('/dir0'), "Even directories discovered"
        assert not caching_adapter.was_discovered('/dir1'), "Odd directories filtered"

        # Check discovered count is about half
        stats = caching_adapter.get_stats()
        # Should discover root + ~50 even dirs + their files
        assert stats['discovered_nodes'] < 600, "Should filter about half the nodes"