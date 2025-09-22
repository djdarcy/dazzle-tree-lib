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

    @pytest.mark.asyncio
    async def test_filtered_nodes_not_discovered(self):
        """Test semantic distinction between discovered, exposed, and user-received nodes.

        This test demonstrates the solution to Issue #43:
        - was_discovered(): Node was processed by the adapter
        - was_exposed(): Node was yielded by the adapter
        - User's list: What actually passed through the filter
        """
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
        user_received = []
        root = FilterNode('/')

        async def traverse(node):
            async for child in filtering_adapter.get_children(node):
                user_received.append(str(child.path))
                await traverse(child)

        await traverse(root)

        # NEW SEMANTIC UNDERSTANDING (Issue #43 solution):

        # 1. Hidden files WERE discovered by the caching adapter (it saw them)
        assert caching_adapter.was_discovered('/hidden/.git'), ".git WAS discovered by adapter"
        assert caching_adapter.was_discovered('/hidden/.env'), ".env WAS discovered by adapter"

        # 2. Hidden files WERE exposed by the caching adapter (it yielded them)
        assert caching_adapter.was_exposed('/hidden/.git'), ".git WAS exposed by adapter"
        assert caching_adapter.was_exposed('/hidden/.env'), ".env WAS exposed by adapter"

        # 3. But hidden files were NOT received by the user (filter blocked them)
        assert '/hidden/.git' not in user_received, ".git NOT in user's received list"
        assert '/hidden/.env' not in user_received, ".env NOT in user's received list"

        # Parent of filtered nodes IS discovered and expanded
        assert caching_adapter.was_discovered('/hidden'), "/hidden should be discovered"
        assert caching_adapter.was_expanded('/hidden'), "/hidden should be expanded"

        # Non-filtered nodes ARE discovered, exposed, AND received
        assert caching_adapter.was_discovered('/docs'), "/docs should be discovered"
        assert caching_adapter.was_exposed('/docs'), "/docs should be exposed"
        assert any('/docs' in path for path in user_received), "/docs should be in user's list"

    @pytest.mark.asyncio
    async def test_filter_change_during_traversal(self):
        """Test changing filter during traversal affects user-received nodes, not discovery."""
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
        first_user_received = []
        async for child in filtering_adapter.get_children(root):
            first_user_received.append(str(child.path))

        # All children should be discovered AND exposed
        assert caching_adapter.was_discovered('/docs')
        assert caching_adapter.was_discovered('/hidden')
        assert caching_adapter.was_exposed('/docs')
        assert caching_adapter.was_exposed('/hidden')

        # Change filter to exclude hidden
        def exclude_hidden(node):
            path = str(node.path)
            return not any(part.startswith('.') for part in path.split('/'))

        filtering_adapter.node_filter = exclude_hidden

        # Clear tracking to test fresh
        caching_adapter.clear_tracking()

        # Second traversal - with filter
        second_user_received = []
        async for child in filtering_adapter.get_children(root):
            second_user_received.append(str(child.path))

        # With new semantics: adapter still discovers all nodes
        assert caching_adapter.was_discovered('/hidden')
        assert caching_adapter.was_discovered('/docs')

        # At root level, both get same nodes (filter only affects dot-prefixed files)
        # The /hidden directory itself doesn't start with dot, so it passes filter
        assert len(first_user_received) == len(second_user_received), "Root level same for both"

        # Verify what user actually got
        assert '/hidden' in second_user_received  # /hidden itself passes (no dot prefix)
        assert '/docs' in second_user_received    # Non-hidden still received

        # The difference is that with filter, traversing INTO /hidden would not yield .git/.env

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

        # Depth 3 - With new semantics: adapter discovers it if parent was expanded
        # But it won't be in user's received list due to depth filter
        if caching_adapter.was_expanded('/docs/api'):
            # If parent was expanded, child was discovered
            assert caching_adapter.was_discovered('/docs/api/index.md'), "Depth 3 discovered by adapter"
            assert caching_adapter.was_exposed('/docs/api/index.md'), "Depth 3 exposed by adapter"

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

        # With new semantics: ALL files are discovered by adapter (it sees everything)
        assert caching_adapter.was_discovered('/src/core/main.py'), "Python files discovered"
        assert caching_adapter.was_discovered('/src/core/helper.py'), "Python files discovered"

        # Markdown files are ALSO discovered (adapter sees them before filter)
        assert caching_adapter.was_discovered('/docs/api/index.md'), "Markdown files discovered by adapter"

        # But only Python files and directories are in user's received list
        assert '/src/core/main.py' in discovered, "Python files received by user"
        assert '/docs/api/index.md' not in discovered, "Markdown filtered from user"

        # Directories should be discovered and received
        assert caching_adapter.was_discovered('/docs'), "Directories discovered"
        assert '/docs' in discovered, "Directories received by user"

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
        # With new semantics: /tests IS discovered but not in user's received list
        assert caching_adapter.was_discovered('/tests'), "/tests discovered by adapter"
        # Its children are also discovered if parent was expanded
        if caching_adapter.was_expanded('/tests'):
            assert caching_adapter.was_discovered('/tests/unit'), "/tests/unit discovered"
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

        # With new semantics: children ARE discovered (adapter sees them before filter)
        assert caching_adapter.was_discovered('/hidden/.git'), "Children discovered by adapter"
        assert caching_adapter.was_discovered('/hidden/.env'), "Children discovered by adapter"
        assert caching_adapter.was_exposed('/hidden/.git'), "Children exposed by adapter"
        assert caching_adapter.was_exposed('/hidden/.env'), "Children exposed by adapter"
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

        # With new semantics: adapter discovers ALL nodes
        assert caching_adapter.was_discovered('/dir0'), "Even directories discovered"
        assert caching_adapter.was_discovered('/dir1'), "Odd directories ALSO discovered"

        # Check discovered count includes all nodes
        stats = caching_adapter.get_stats()
        # Should discover all nodes (root + 100 dirs + potentially their files)
        assert stats['discovered_nodes'] > 100, "Adapter discovers all directories"

        # But user received fewer nodes due to filter
        assert discovered_count < 600, "User received filtered subset"