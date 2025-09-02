"""Tests for depth tracking functionality in DazzleTreeLib.

This module tests the depth-aware traversal functions to ensure
they correctly track and expose depth information during traversal.
"""

import asyncio
import tempfile
import shutil
from pathlib import Path
from typing import List, Tuple
import pytest

from dazzletreelib.aio import (
    traverse_with_depth,
    traverse_tree_by_level,
    filter_by_depth,
)


class TestDepthTracking:
    """Test suite for depth tracking features."""
    
    @staticmethod
    def create_test_tree() -> Path:
        """Create a test directory structure with known depth.
        
        Structure:
        root/
        ├── file1.txt (depth 1)
        ├── dir1/ (depth 1)
        │   ├── file2.txt (depth 2)
        │   └── subdir1/ (depth 2)
        │       ├── file3.txt (depth 3)
        │       └── deepdir/ (depth 3)
        │           └── file4.txt (depth 4)
        └── dir2/ (depth 1)
            └── file5.txt (depth 2)
        """
        root = Path(tempfile.mkdtemp(prefix="depth_test_"))
        
        # Depth 1
        (root / "file1.txt").write_text("Root file")
        dir1 = root / "dir1"
        dir1.mkdir()
        dir2 = root / "dir2"
        dir2.mkdir()
        
        # Depth 2
        (dir1 / "file2.txt").write_text("Level 2 file")
        (dir2 / "file5.txt").write_text("Another level 2 file")
        subdir1 = dir1 / "subdir1"
        subdir1.mkdir()
        
        # Depth 3
        (subdir1 / "file3.txt").write_text("Level 3 file")
        deepdir = subdir1 / "deepdir"
        deepdir.mkdir()
        
        # Depth 4
        (deepdir / "file4.txt").write_text("Level 4 file")
        
        return root
    
    @pytest.mark.asyncio
    async def test_traverse_with_depth_basic(self):
        """Test basic depth tracking during traversal."""
        root = self.create_test_tree()
        
        try:
            # Collect all nodes with their depths
            nodes_with_depth = []
            async for node, depth in traverse_with_depth(root):
                nodes_with_depth.append((node.path.name, depth))
            
            # Verify root is at depth 0
            assert any(name == root.name and d == 0 for name, d in nodes_with_depth)
            
            # Verify depth 1 items
            depth_1_names = [name for name, d in nodes_with_depth if d == 1]
            assert "file1.txt" in depth_1_names
            assert "dir1" in depth_1_names
            assert "dir2" in depth_1_names
            
            # Verify depth 2 items
            depth_2_names = [name for name, d in nodes_with_depth if d == 2]
            assert "file2.txt" in depth_2_names
            assert "file5.txt" in depth_2_names
            assert "subdir1" in depth_2_names
            
            # Verify depth 3 items
            depth_3_names = [name for name, d in nodes_with_depth if d == 3]
            assert "file3.txt" in depth_3_names
            assert "deepdir" in depth_3_names
            
            # Verify depth 4 items
            depth_4_names = [name for name, d in nodes_with_depth if d == 4]
            assert "file4.txt" in depth_4_names
            
            # Verify max depth
            max_depth = max(d for _, d in nodes_with_depth)
            assert max_depth == 4
            
        finally:
            shutil.rmtree(root)
    
    @pytest.mark.asyncio
    async def test_max_depth_limiting(self):
        """Test that max_depth correctly limits traversal."""
        root = self.create_test_tree()
        
        try:
            # Test max_depth=2
            depths_seen = set()
            async for node, depth in traverse_with_depth(root, max_depth=2):
                depths_seen.add(depth)
            
            assert 0 in depths_seen  # Root
            assert 1 in depths_seen  # Level 1
            assert 2 in depths_seen  # Level 2
            assert 3 not in depths_seen  # Should not see level 3
            assert 4 not in depths_seen  # Should not see level 4
            
            # Test max_depth=0 (only root)
            count = 0
            async for node, depth in traverse_with_depth(root, max_depth=0):
                assert depth == 0
                count += 1
            assert count == 1  # Only root node
            
        finally:
            shutil.rmtree(root)
    
    @pytest.mark.asyncio
    async def test_start_depth_offset(self):
        """Test starting traversal with a depth offset."""
        root = self.create_test_tree()
        
        try:
            # Start with depth offset of 5
            min_depth = float('inf')
            max_depth = 0
            
            async for node, depth in traverse_with_depth(root, start_depth=5):
                min_depth = min(min_depth, depth)
                max_depth = max(max_depth, depth)
            
            # Root should be at depth 5
            assert min_depth == 5
            # Deepest should be at depth 9 (5 + 4)
            assert max_depth == 9
            
        finally:
            shutil.rmtree(root)
    
    @pytest.mark.asyncio
    async def test_traverse_by_level(self):
        """Test level-order traversal with batch yielding."""
        root = self.create_test_tree()
        
        try:
            levels = {}
            async for depth, nodes in traverse_tree_by_level(root):
                levels[depth] = [n.path.name for n in nodes]
            
            # Check level 0 (root)
            assert len(levels[0]) == 1
            assert root.name in levels[0]
            
            # Check level 1
            assert len(levels[1]) == 3  # file1.txt, dir1, dir2
            assert "file1.txt" in levels[1]
            assert "dir1" in levels[1]
            assert "dir2" in levels[1]
            
            # Check level 2
            assert "file2.txt" in levels[2]
            assert "file5.txt" in levels[2]
            assert "subdir1" in levels[2]
            
            # Check level 3
            assert "file3.txt" in levels[3]
            assert "deepdir" in levels[3]
            
            # Check level 4
            assert "file4.txt" in levels[4]
            
        finally:
            shutil.rmtree(root)
    
    @pytest.mark.asyncio
    async def test_filter_by_exact_depth(self):
        """Test filtering nodes by exact depth."""
        root = self.create_test_tree()
        
        try:
            # Get all nodes at depth 2
            depth_2_paths = await filter_by_depth(root, exact_depth=2)
            depth_2_names = [p.name for p in depth_2_paths]
            
            assert len(depth_2_names) == 3
            assert "file2.txt" in depth_2_names
            assert "file5.txt" in depth_2_names
            assert "subdir1" in depth_2_names
            
            # Get all nodes at depth 0 (just root)
            depth_0_paths = await filter_by_depth(root, exact_depth=0)
            assert len(depth_0_paths) == 1
            assert depth_0_paths[0] == root
            
            # Get all nodes at depth 4
            depth_4_paths = await filter_by_depth(root, exact_depth=4)
            depth_4_names = [p.name for p in depth_4_paths]
            assert len(depth_4_names) == 1
            assert "file4.txt" in depth_4_names
            
        finally:
            shutil.rmtree(root)
    
    @pytest.mark.asyncio
    async def test_filter_by_depth_range(self):
        """Test filtering nodes by depth range."""
        root = self.create_test_tree()
        
        try:
            # Get nodes between depth 1 and 3
            range_paths = await filter_by_depth(root, min_depth=1, max_depth=3)
            range_names = [p.name for p in range_paths]
            
            # Should include depths 1, 2, and 3
            assert "file1.txt" in range_names  # Depth 1
            assert "dir1" in range_names  # Depth 1
            assert "file2.txt" in range_names  # Depth 2
            assert "subdir1" in range_names  # Depth 2
            assert "file3.txt" in range_names  # Depth 3
            assert "deepdir" in range_names  # Depth 3
            
            # Should NOT include depth 0 or 4
            assert root.name not in range_names  # Depth 0
            assert "file4.txt" not in range_names  # Depth 4
            
            # Test minimum depth only
            min_3_paths = await filter_by_depth(root, min_depth=3)
            min_3_names = [p.name for p in min_3_paths]
            assert "file3.txt" in min_3_names  # Depth 3
            assert "deepdir" in min_3_names  # Depth 3
            assert "file4.txt" in min_3_names  # Depth 4
            assert "file1.txt" not in min_3_names  # Depth 1
            
        finally:
            shutil.rmtree(root)
    
    @pytest.mark.asyncio
    async def test_depth_tracking_with_dfs(self):
        """Test depth tracking works with depth-first traversal."""
        root = self.create_test_tree()
        
        try:
            # Use DFS strategy
            depths_seen = []
            async for node, depth in traverse_with_depth(root, strategy='dfs'):
                depths_seen.append(depth)
            
            # DFS should still visit all depths
            assert 0 in depths_seen
            assert 1 in depths_seen
            assert 2 in depths_seen
            assert 3 in depths_seen
            assert 4 in depths_seen
            
            # DFS pattern: should go deep before going wide
            # So we should see depth 4 before we've seen all depth 1 items
            first_depth_4 = depths_seen.index(4)
            depth_1_count = depths_seen[:first_depth_4].count(1)
            # In DFS, we shouldn't have visited all 3 depth-1 items before going deep
            assert depth_1_count < 3
            
        finally:
            shutil.rmtree(root)
    
    @pytest.mark.asyncio
    async def test_empty_directory_depth(self):
        """Test depth tracking with empty directories."""
        root = Path(tempfile.mkdtemp(prefix="empty_depth_"))
        
        try:
            # Create structure with empty dirs
            (root / "empty1").mkdir()
            (root / "empty1" / "empty2").mkdir()
            (root / "empty1" / "empty2" / "empty3").mkdir()
            
            max_depth = 0
            async for node, depth in traverse_with_depth(root):
                max_depth = max(max_depth, depth)
            
            # Should reach depth 3 even with empty dirs
            assert max_depth == 3
            
        finally:
            shutil.rmtree(root)
    
    @pytest.mark.asyncio
    async def test_single_file_depth(self):
        """Test depth tracking on a single file."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            test_file = Path(f.name)
            test_file.write_text("Test content")
        
        try:
            count = 0
            async for node, depth in traverse_with_depth(test_file):
                assert depth == 0  # Single file is at depth 0
                count += 1
            
            assert count == 1  # Only one node
            
        finally:
            test_file.unlink()
    
    @pytest.mark.asyncio
    async def test_depth_consistency_across_strategies(self):
        """Verify depth values are consistent across different traversal strategies."""
        root = self.create_test_tree()
        
        try:
            # Collect depths for each strategy
            strategies = ['bfs', 'dfs', 'dfs_post']
            depth_maps = {}
            
            for strategy in strategies:
                depth_map = {}
                async for node, depth in traverse_with_depth(root, strategy=strategy):
                    # Use relative path as key
                    rel_path = str(node.path.relative_to(root.parent))
                    depth_map[rel_path] = depth
                depth_maps[strategy] = depth_map
            
            # All strategies should assign the same depth to each node
            bfs_depths = depth_maps['bfs']
            for strategy in ['dfs', 'dfs_post']:
                strategy_depths = depth_maps[strategy]
                for path, depth in bfs_depths.items():
                    assert path in strategy_depths, f"{path} missing in {strategy}"
                    assert strategy_depths[path] == depth, \
                        f"Depth mismatch for {path}: BFS={depth}, {strategy}={strategy_depths[path]}"
            
        finally:
            shutil.rmtree(root)


class TestDepthPerformance:
    """Performance tests for depth tracking."""
    
    @staticmethod
    def create_wide_tree(width: int = 100, depth: int = 3) -> Path:
        """Create a wide tree for performance testing."""
        root = Path(tempfile.mkdtemp(prefix="perf_depth_"))
        
        def create_level(parent: Path, current_depth: int):
            if current_depth >= depth:
                return
            
            for i in range(width):
                if current_depth == depth - 1:
                    # Create files at leaf level
                    (parent / f"file_{i}.txt").write_text(f"File {i}")
                else:
                    # Create directories
                    subdir = parent / f"dir_{i}"
                    subdir.mkdir()
                    create_level(subdir, current_depth + 1)
        
        create_level(root, 0)
        return root
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_depth_tracking_overhead(self):
        """Measure overhead of depth tracking vs regular traversal."""
        import time
        
        root = self.create_wide_tree(width=50, depth=3)
        
        try:
            # Time regular traversal
            from dazzletreelib.aio import traverse_tree_async
            
            start = time.perf_counter()
            count_regular = 0
            async for node in traverse_tree_async(root):
                count_regular += 1
            time_regular = time.perf_counter() - start
            
            # Time depth tracking traversal
            start = time.perf_counter()
            count_depth = 0
            async for node, depth in traverse_with_depth(root):
                count_depth += 1
            time_depth = time.perf_counter() - start
            
            # Verify same number of nodes
            assert count_regular == count_depth
            
            # Calculate overhead
            overhead = (time_depth - time_regular) / time_regular * 100
            
            print(f"\nDepth tracking performance:")
            print(f"  Regular traversal: {time_regular:.4f}s")
            print(f"  With depth tracking: {time_depth:.4f}s")
            print(f"  Overhead: {overhead:.1f}%")
            print(f"  Nodes traversed: {count_regular}")
            
            # Depth tracking should have minimal overhead (< 20%)
            assert overhead < 20, f"Depth tracking overhead too high: {overhead:.1f}%"
            
        finally:
            shutil.rmtree(root)
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_filter_by_depth_performance(self):
        """Test performance of depth-based filtering."""
        import time
        
        root = self.create_wide_tree(width=100, depth=4)
        
        try:
            # Time filtering for exact depth
            start = time.perf_counter()
            depth_2_nodes = await filter_by_depth(root, exact_depth=2)
            time_exact = time.perf_counter() - start
            
            # Time filtering for range
            start = time.perf_counter()
            range_nodes = await filter_by_depth(root, min_depth=1, max_depth=2)
            time_range = time.perf_counter() - start
            
            print(f"\nDepth filtering performance:")
            print(f"  Exact depth filter: {time_exact:.4f}s ({len(depth_2_nodes)} nodes)")
            print(f"  Range filter: {time_range:.4f}s ({len(range_nodes)} nodes)")
            
            # Both should complete quickly even for large trees
            assert time_exact < 2.0, "Exact depth filtering too slow"
            assert time_range < 2.0, "Range filtering too slow"
            
        finally:
            shutil.rmtree(root)


if __name__ == "__main__":
    # Run tests with: python -m pytest tests/test_depth_tracking.py -v
    pytest.main([__file__, "-v"])