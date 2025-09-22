#!/usr/bin/env python3
"""
Enhanced performance tests for depth tracking with progress indicators.

These tests are designed to run on large trees (1M+ nodes) and provide
progress updates during execution to ensure the test is running properly.
"""

import asyncio
import shutil
import tempfile
import time
from pathlib import Path
import sys
import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dazzletreelib.aio import (
    traverse_with_depth,
    filter_by_depth,
    traverse_tree_async
)


class TestDepthPerformanceEnhanced:
    """Enhanced performance tests with progress tracking."""
    
    @staticmethod
    def create_wide_tree_with_progress(width: int = 100, depth: int = 4, show_progress: bool = True) -> Path:
        """
        Create a wide tree for performance testing with progress updates.
        
        Args:
            width: Number of items at each level
            depth: Depth of the tree
            show_progress: Whether to show progress updates
            
        Returns:
            Path to the root of the created tree
        """
        root = Path(tempfile.mkdtemp(prefix="perf_depth_"))
        
        # Calculate total expected nodes for progress tracking
        total_nodes = sum(width ** i for i in range(depth))
        nodes_created = 0
        last_progress = 0
        
        if show_progress:
            print(f"\nCreating test tree: width={width}, depth={depth}")
            print(f"Expected total nodes: {total_nodes:,}")
            print("Progress: ", end="", flush=True)
        
        def create_level(parent: Path, current_depth: int):
            nonlocal nodes_created, last_progress
            
            if current_depth >= depth:
                return
            
            for i in range(width):
                nodes_created += 1
                
                # Update progress at 10%, 25%, 50%, 75%, 100%
                if show_progress:
                    progress = int(nodes_created * 100 / total_nodes)
                    if progress >= 10 and last_progress < 10:
                        print("10%...", end="", flush=True)
                        last_progress = 10
                    elif progress >= 25 and last_progress < 25:
                        print("25%...", end="", flush=True)
                        last_progress = 25
                    elif progress >= 50 and last_progress < 50:
                        print("50%...", end="", flush=True)
                        last_progress = 50
                    elif progress >= 75 and last_progress < 75:
                        print("75%...", end="", flush=True)
                        last_progress = 75
                
                if current_depth == depth - 1:
                    # Create files at leaf level
                    (parent / f"file_{i}.txt").write_text(f"File {i}")
                else:
                    # Create directories
                    subdir = parent / f"dir_{i}"
                    subdir.mkdir()
                    create_level(subdir, current_depth + 1)
        
        start_time = time.perf_counter()
        create_level(root, 0)
        creation_time = time.perf_counter() - start_time
        
        if show_progress:
            print("100%")
            print(f"Tree created in {creation_time:.2f}s")
            print(f"Actual nodes created: {nodes_created:,}")
        
        return root
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_large_tree_performance_with_progress(self):
        """Test performance on large tree with progress indicators."""
        import time
        
        # Use reasonable size for CI but still meaningful
        # 100^4 would be 100M nodes - too much
        # 20^4 = 160,000 nodes - reasonable for testing
        width = 20
        depth = 4
        expected_nodes = sum(width ** i for i in range(depth))
        
        print(f"\n{'='*60}")
        print("Large Tree Performance Test")
        print(f"Configuration: width={width}, depth={depth}")
        print(f"Expected nodes: ~{expected_nodes:,}")
        print(f"{'='*60}")
        
        root = self.create_wide_tree_with_progress(width=width, depth=depth)
        
        try:
            # Test 1: Regular traversal with progress
            print("\nTest 1: Regular traversal")
            print("Progress: ", end="", flush=True)
            
            start = time.perf_counter()
            count_regular = 0
            last_progress = 0
            
            async for node in traverse_tree_async(root):
                count_regular += 1
                progress = int(count_regular * 100 / expected_nodes)
                
                if progress >= 10 and last_progress < 10:
                    print("10%...", end="", flush=True)
                    last_progress = 10
                elif progress >= 25 and last_progress < 25:
                    print("25%...", end="", flush=True)
                    last_progress = 25
                elif progress >= 50 and last_progress < 50:
                    print("50%...", end="", flush=True)
                    last_progress = 50
                elif progress >= 75 and last_progress < 75:
                    print("75%...", end="", flush=True)
                    last_progress = 75
            
            time_regular = time.perf_counter() - start
            print("100%")
            print(f"Time: {time_regular:.4f}s")
            print(f"Nodes traversed: {count_regular:,}")
            print(f"Throughput: {count_regular/time_regular:.0f} nodes/sec")
            
            # Test 2: Depth tracking traversal with progress
            print("\nTest 2: Depth tracking traversal")
            print("Progress: ", end="", flush=True)
            
            start = time.perf_counter()
            count_depth = 0
            last_progress = 0
            max_depth_seen = 0
            
            async for node, depth in traverse_with_depth(root):
                count_depth += 1
                max_depth_seen = max(max_depth_seen, depth)
                progress = int(count_depth * 100 / expected_nodes)
                
                if progress >= 10 and last_progress < 10:
                    print("10%...", end="", flush=True)
                    last_progress = 10
                elif progress >= 25 and last_progress < 25:
                    print("25%...", end="", flush=True)
                    last_progress = 25
                elif progress >= 50 and last_progress < 50:
                    print("50%...", end="", flush=True)
                    last_progress = 50
                elif progress >= 75 and last_progress < 75:
                    print("75%...", end="", flush=True)
                    last_progress = 75
            
            time_depth = time.perf_counter() - start
            print("100%")
            print(f"Time: {time_depth:.4f}s")
            print(f"Nodes traversed: {count_depth:,}")
            print(f"Max depth seen: {max_depth_seen}")
            print(f"Throughput: {count_depth/time_depth:.0f} nodes/sec")
            
            # Calculate overhead
            overhead = (time_depth - time_regular) / time_regular * 100
            
            print(f"\nPerformance Summary:")
            print(f"  Regular traversal: {time_regular:.4f}s")
            print(f"  With depth tracking: {time_depth:.4f}s")
            print(f"  Overhead: {overhead:.1f}%")
            
            # Depth tracking should have reasonable overhead (< 30% for large trees)
            assert overhead < 30, f"Depth tracking overhead too high: {overhead:.1f}%"
            assert count_regular == count_depth, "Node counts don't match"
            
        finally:
            print("\nCleaning up test tree...")
            shutil.rmtree(root)
            print("Cleanup complete.")
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_filter_performance_realistic(self):
        """Test filtering performance with realistic tree size."""
        import time
        
        # Smaller tree for filter tests since filtering is more expensive
        width = 10
        depth = 4
        expected_at_depth_2 = width ** 2
        
        print(f"\n{'='*60}")
        print("Filter Performance Test")
        print(f"Configuration: width={width}, depth={depth}")
        print(f"Expected nodes at depth 2: {expected_at_depth_2:,}")
        print(f"{'='*60}")
        
        root = self.create_wide_tree_with_progress(width=width, depth=depth)
        
        try:
            # Test exact depth filtering
            print("\nTest 1: Exact depth filter (depth=2)")
            start = time.perf_counter()
            depth_2_nodes = await filter_by_depth(root, exact_depth=2)
            time_exact = time.perf_counter() - start
            
            print(f"Time: {time_exact:.4f}s")
            print(f"Nodes found: {len(depth_2_nodes):,}")
            print(f"Throughput: {len(depth_2_nodes)/time_exact:.0f} nodes/sec")
            
            # Test range filtering
            print("\nTest 2: Range filter (depth 1-2)")
            start = time.perf_counter()
            range_nodes = await filter_by_depth(root, min_depth=1, max_depth=2)
            time_range = time.perf_counter() - start
            
            expected_range = width + (width ** 2)
            print(f"Time: {time_range:.4f}s")
            print(f"Nodes found: {len(range_nodes):,}")
            print(f"Expected: {expected_range:,}")
            print(f"Throughput: {len(range_nodes)/time_range:.0f} nodes/sec")
            
            # Verify correctness
            assert len(depth_2_nodes) == expected_at_depth_2, f"Expected {expected_at_depth_2} nodes at depth 2"
            assert len(range_nodes) == expected_range, f"Expected {expected_range} nodes in range"
            
            # Performance assertions - adjust based on realistic expectations
            # For 10^4 tree, should complete in reasonable time
            assert time_exact < 10.0, f"Exact depth filtering took too long: {time_exact:.2f}s"
            assert time_range < 10.0, f"Range filtering took too long: {time_range:.2f}s"
            
        finally:
            print("\nCleaning up test tree...")
            shutil.rmtree(root)
            print("Cleanup complete.")


if __name__ == "__main__":
    # Run with: python tests/test_depth_tracking_performance_enhanced.py
    # Or: pytest tests/test_depth_tracking_performance_enhanced.py -v -s
    print("Running enhanced performance tests...")
    pytest.main([__file__, "-v", "-s"])