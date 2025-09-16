#!/usr/bin/env python3
"""
Regression test for Issue #37: Node tracking in fast mode.

This test ensures that node tracking works correctly in both safe and fast modes.
"""

import asyncio
import tempfile
import unittest
from pathlib import Path
from dazzletreelib.aio.adapters import AsyncFileSystemAdapter, CompletenessAwareCacheAdapter
from dazzletreelib.testing.fixtures import TestableCache


class TestNodeTrackingRegression(unittest.TestCase):
    """Test that node tracking works in both safe and fast modes."""

    def setUp(self):
        """Create a temporary directory structure for testing."""
        self.tmpdir = tempfile.TemporaryDirectory()
        self.test_path = Path(self.tmpdir.name)

        # Create structure
        (self.test_path / "folder1").mkdir()
        (self.test_path / "folder1" / "sub1").mkdir()
        (self.test_path / "folder1" / "sub2").mkdir()
        (self.test_path / "folder2").mkdir()
        (self.test_path / "file1.txt").touch()

    def tearDown(self):
        """Clean up temporary directory."""
        self.tmpdir.cleanup()

    def test_fast_mode_tracking(self):
        """Test that node tracking works in fast mode (Issue #37 regression)."""

        async def run_test():
            # Create adapter with FAST MODE
            fs_adapter = AsyncFileSystemAdapter()
            cache_adapter = CompletenessAwareCacheAdapter(
                fs_adapter,
                enable_oom_protection=False,  # FAST MODE!
                max_memory_mb=10
            )

            # Verify fast mode configuration
            self.assertFalse(cache_adapter.enable_oom_protection)
            self.assertTrue(cache_adapter.should_track_nodes)
            self.assertIsNotNone(cache_adapter._track_node_visit_impl)
            self.assertEqual(
                cache_adapter._track_node_visit_impl.__name__,
                "_track_node_visit_fast"
            )

            # Create a mock node and traverse
            class MockNode:
                def __init__(self, path):
                    self.path = path

            # Get children of root to trigger tracking
            root_node = MockNode(self.test_path)
            children = []
            async for child in cache_adapter.get_children(root_node):
                children.append(child)

            # Test with TestableCache
            testable = TestableCache(cache_adapter)

            # Root should be visited
            self.assertTrue(
                testable.was_node_visited(self.test_path),
                "Root should be visited in fast mode"
            )

            # node_completeness should be populated
            self.assertIn(
                str(self.test_path),
                cache_adapter.node_completeness,
                "node_completeness should contain root path in fast mode"
            )

        asyncio.run(run_test())

    def test_safe_mode_tracking(self):
        """Test that node tracking works in safe mode (control test)."""

        async def run_test():
            # Create adapter with SAFE MODE
            fs_adapter = AsyncFileSystemAdapter()
            cache_adapter = CompletenessAwareCacheAdapter(
                fs_adapter,
                enable_oom_protection=True,  # SAFE MODE
                max_memory_mb=10,
                max_tracked_nodes=100
            )

            # Verify safe mode configuration
            self.assertTrue(cache_adapter.enable_oom_protection)
            self.assertTrue(cache_adapter.should_track_nodes)
            self.assertIsNotNone(cache_adapter._track_node_visit_impl)
            self.assertEqual(
                cache_adapter._track_node_visit_impl.__name__,
                "_track_node_visit_safe"
            )

            # Create a mock node and traverse
            class MockNode:
                def __init__(self, path):
                    self.path = path

            # Get children of root to trigger tracking
            root_node = MockNode(self.test_path)
            children = []
            async for child in cache_adapter.get_children(root_node):
                children.append(child)

            # Test with TestableCache
            testable = TestableCache(cache_adapter)

            # Root should be visited
            self.assertTrue(
                testable.was_node_visited(self.test_path),
                "Root should be visited in safe mode"
            )

            # node_completeness should be populated
            self.assertIn(
                str(self.test_path),
                cache_adapter.node_completeness,
                "node_completeness should contain root path in safe mode"
            )

        asyncio.run(run_test())

    def test_visited_vs_discovered_semantics(self):
        """
        Test the semantic difference between visited and discovered nodes.

        This test documents the intended behavior: nodes are only marked as
        "visited" when get_children() is called for them, not when they are
        discovered as children of another node.
        """

        async def run_test():
            fs_adapter = AsyncFileSystemAdapter()
            cache_adapter = CompletenessAwareCacheAdapter(
                fs_adapter,
                enable_oom_protection=True,
                max_memory_mb=10
            )

            class MockNode:
                def __init__(self, path):
                    self.path = path

            # Get children of root (depth 0 → 1)
            root_node = MockNode(self.test_path)
            level1_nodes = []
            async for child in cache_adapter.get_children(root_node):
                level1_nodes.append(child)

            # Get children of folder1 (depth 1 → 2)
            folder1_path = self.test_path / "folder1"
            folder1_node = MockNode(folder1_path)
            level2_nodes = []
            async for child in cache_adapter.get_children(folder1_node):
                level2_nodes.append(child)

            testable = TestableCache(cache_adapter)

            # Root was visited (get_children called)
            self.assertTrue(testable.was_node_visited(self.test_path))

            # folder1 was visited (get_children called)
            self.assertTrue(testable.was_node_visited(folder1_path))

            # folder2 was discovered but NOT visited (get_children not called)
            folder2_path = self.test_path / "folder2"
            self.assertFalse(
                testable.was_node_visited(folder2_path),
                "folder2 should be discovered but not visited"
            )

            # sub1 and sub2 were discovered but NOT visited
            sub1_path = self.test_path / "folder1" / "sub1"
            sub2_path = self.test_path / "folder1" / "sub2"
            self.assertFalse(
                testable.was_node_visited(sub1_path),
                "sub1 should be discovered but not visited"
            )
            self.assertFalse(
                testable.was_node_visited(sub2_path),
                "sub2 should be discovered but not visited"
            )

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()