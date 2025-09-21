#!/usr/bin/env python3
"""
ONE-OFF TEST: Simple fast mode node tracking verification

Related to: GitHub Issue #37 - Node tracking fails in fast mode
Created: 2025-09-15 during semantic redesign work
Purpose: Verify that fast mode properly tracks nodes after our fixes

Connected to real tests:
- tests/test_node_tracking_regression.py::TestNodeTrackingRegression::test_fast_mode_tracking
- tests/test_issue_29_performance_realistic.py (performance impact of tracking)

Context:
This was created to debug why fast mode wasn't tracking nodes. The issue was that
self.should_track_nodes was set to enable_oom_protection (False in fast mode).
We fixed it by setting should_track_nodes = True for both modes.

Usage:
python test_fast_mode_simple.py
"""

import asyncio
import tempfile
from pathlib import Path
from dazzletreelib.aio.adapters import AsyncFileSystemAdapter, CompletenessAwareCacheAdapter
from dazzletreelib.testing.fixtures import CacheTestHelper

async def test_fast_mode():
    """Test that node tracking works in fast mode."""

    # Create a temporary directory structure
    with tempfile.TemporaryDirectory() as tmpdir:
        test_path = Path(tmpdir)

        # Create structure
        (test_path / "folder1").mkdir()
        (test_path / "file1.txt").touch()

        # Create adapter with FAST MODE
        fs_adapter = AsyncFileSystemAdapter()
        cache_adapter = CompletenessAwareCacheAdapter(
            fs_adapter,
            enable_oom_protection=False,  # FAST MODE!
            max_memory_mb=10
        )

        print("\n=== Testing Fast Mode Node Tracking ===")
        print(f"enable_oom_protection: {cache_adapter.enable_oom_protection}")
        print(f"should_track_nodes: {cache_adapter.should_track_nodes}")
        print(f"_track_node_visit_impl: {cache_adapter._track_node_visit_impl}")

        # Create a mock node
        class MockNode:
            def __init__(self, path):
                self.path = path

        # Call get_children to trigger node tracking
        root_node = MockNode(test_path)
        children = []
        async for child in cache_adapter.get_children(root_node):
            children.append(child)

        print(f"\nAfter get_children on root:")
        print(f"node_completeness: {cache_adapter.node_completeness}")

        # Test with CacheTestHelper
        testable = CacheTestHelper(cache_adapter)
        root_visited = testable.was_node_visited(test_path)

        print(f"\nRoot visited: {root_visited}")

        assert root_visited, "Root should be visited in fast mode!"
        print("\n✅ Fast mode node tracking is WORKING!")

if __name__ == "__main__":
    asyncio.run(test_fast_mode())