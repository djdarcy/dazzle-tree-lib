"""Performance benchmarks comparing sync vs async implementations.

These tests verify that async implementation provides the expected
performance improvements for I/O-bound tree traversal operations.
"""

import asyncio
import time
import tempfile
import shutil
from pathlib import Path
from typing import Tuple
import pytest

from dazzletreelib.sync import (
    FileSystemNode as SyncNode,
    FileSystemAdapter as SyncAdapter,
    BreadthFirstTraverser as SyncBFS,
    traverse_tree,
    collect_tree_data,
    DataRequirement,
)

from dazzletreelib.aio import (
    AsyncFileSystemNode as AsyncNode,
    AsyncFileSystemAdapter as AsyncAdapter,
    AsyncBreadthFirstTraverser as AsyncBFS,
    traverse_tree_async,
    collect_metadata_async,
)


class TestPerformanceBenchmarks:
    """Performance comparison tests between sync and async."""
    
    @staticmethod
    def create_test_tree(num_dirs: int = 10, files_per_dir: int = 10) -> Path:
        """Create a test directory structure for benchmarking.
        
        Args:
            num_dirs: Number of directories to create
            files_per_dir: Number of files in each directory
            
        Returns:
            Path to root of test tree
        """
        root = Path(tempfile.mkdtemp(prefix="dazzle_perf_"))
        
        # Create directories with files
        for i in range(num_dirs):
            dir_path = root / f"dir_{i:03d}"
            dir_path.mkdir()
            
            # Create files in each directory
            for j in range(files_per_dir):
                file_path = dir_path / f"file_{j:03d}.txt"
                file_path.write_text(f"Content for file {i}/{j}" * 100)
            
            # Create a subdirectory with more files
            subdir = dir_path / "subdir"
            subdir.mkdir()
            for k in range(files_per_dir // 2):
                subfile = subdir / f"subfile_{k:03d}.txt"
                subfile.write_text(f"Subdir content {i}/{k}" * 50)
        
        # Create some files at root level
        for m in range(5):
            root_file = root / f"root_file_{m}.txt"
            root_file.write_text(f"Root file {m}" * 100)
        
        return root
    
    def test_traversal_speed_small_tree(self):
        """Test that async is faster for small trees (100 files)."""
        root = self.create_test_tree(num_dirs=5, files_per_dir=10)
        
        try:
            # Warm up filesystem cache
            list(root.rglob("*"))
            
            # Time sync traversal
            start = time.perf_counter()
            sync_count = 0
            sync_node = SyncNode(root)
            sync_adapter = SyncAdapter()
            for _ in traverse_tree(sync_node, sync_adapter):
                sync_count += 1
            sync_time = time.perf_counter() - start
            
            # Time async traversal
            async def async_traverse():
                count = 0
                async for _ in traverse_tree_async(root):
                    count += 1
                return count
            
            start = time.perf_counter()
            async_count = asyncio.run(async_traverse())
            async_time = time.perf_counter() - start
            
            # Verify same number of nodes
            assert sync_count == async_count, f"Node count mismatch: sync={sync_count}, async={async_count}"
            
            # Calculate speedup
            speedup = sync_time / async_time if async_time > 0 else 1.0
            
            print(f"\nSmall tree (100 files):")
            print(f"  Sync time: {sync_time:.4f}s")
            print(f"  Async time: {async_time:.4f}s")
            print(f"  Speedup: {speedup:.2f}x")
            print(f"  Nodes traversed: {sync_count}")
            
            # For small trees, async might be slightly slower due to overhead
            # But should be within 2x (not slower than 0.5x)
            assert speedup > 0.5, f"Async too slow: {speedup:.2f}x (expected > 0.5x)"
        
        finally:
            shutil.rmtree(root)
    
    @pytest.mark.slow
    def test_traversal_speed_medium_tree(self):
        """Test that async is faster for medium trees (500+ files)."""
        root = self.create_test_tree(num_dirs=20, files_per_dir=20)
        
        try:
            # Warm up filesystem cache
            list(root.rglob("*"))
            
            # Time sync traversal
            start = time.perf_counter()
            sync_count = 0
            sync_node = SyncNode(root)
            sync_adapter = SyncAdapter()
            for _ in traverse_tree(sync_node, sync_adapter):
                sync_count += 1
            sync_time = time.perf_counter() - start
            
            # Time async traversal
            async def async_traverse():
                count = 0
                async for _ in traverse_tree_async(root):
                    count += 1
                return count
            
            start = time.perf_counter()
            async_count = asyncio.run(async_traverse())
            async_time = time.perf_counter() - start
            
            # Verify same number of nodes
            assert sync_count == async_count
            
            # Calculate speedup
            speedup = sync_time / async_time if async_time > 0 else 1.0
            
            print(f"\nMedium tree (500+ files):")
            print(f"  Sync time: {sync_time:.4f}s")
            print(f"  Async time: {async_time:.4f}s")
            print(f"  Speedup: {speedup:.2f}x")
            print(f"  Nodes traversed: {sync_count}")
            
            # For medium trees, expect at least 1.5x speedup
            assert speedup > 1.5, f"Async not fast enough: {speedup:.2f}x (expected > 1.5x)"
        
        finally:
            shutil.rmtree(root)
    
    @pytest.mark.slow
    def test_traversal_speed_large_tree(self):
        """Test that async is significantly faster for large trees (5000+ files)."""
        root = self.create_test_tree(num_dirs=100, files_per_dir=50)
        
        try:
            # Time sync traversal (no warmup for large tree)
            start = time.perf_counter()
            sync_count = 0
            sync_adapter = SyncAdapter()
            sync_root = SyncNode(root)
            for _ in traverse_tree(sync_root, sync_adapter):
                sync_count += 1
            sync_time = time.perf_counter() - start
            
            # Time async traversal
            async def async_traverse():
                count = 0
                async for _ in traverse_tree_async(root):
                    count += 1
                return count
            
            start = time.perf_counter()
            async_count = asyncio.run(async_traverse())
            async_time = time.perf_counter() - start
            
            # Verify same number of nodes
            assert sync_count == async_count
            
            # Calculate speedup
            speedup = sync_time / async_time if async_time > 0 else 1.0
            
            print(f"\nLarge tree (5000+ files):")
            print(f"  Sync time: {sync_time:.4f}s")
            print(f"  Async time: {async_time:.4f}s")
            print(f"  Speedup: {speedup:.2f}x")
            print(f"  Nodes traversed: {sync_count}")
            
            # For large trees, expect at least 3x speedup
            assert speedup > 3.0, f"Async not fast enough: {speedup:.2f}x (expected > 3x)"
        
        finally:
            shutil.rmtree(root)
    
    @pytest.mark.asyncio
    async def test_metadata_collection_speed(self):
        """Test async metadata collection performance."""
        root = self.create_test_tree(num_dirs=10, files_per_dir=10)
        
        try:
            # Time sync metadata collection
            start = time.perf_counter()
            sync_node = SyncNode(root)
            sync_adapter = SyncAdapter()
            sync_metadata = list(collect_tree_data(sync_node, sync_adapter, DataRequirement.METADATA))
            sync_time = time.perf_counter() - start
            
            # Time async metadata collection
            start = time.perf_counter()
            async_metadata = await collect_metadata_async(root)
            async_time = time.perf_counter() - start
            
            # Verify same amount of data collected
            assert len(sync_metadata) == len(async_metadata)
            
            # Calculate speedup
            speedup = sync_time / async_time if async_time > 0 else 1.0
            
            print(f"\nMetadata collection:")
            print(f"  Sync time: {sync_time:.4f}s")
            print(f"  Async time: {async_time:.4f}s")
            print(f"  Speedup: {speedup:.2f}x")
            print(f"  Items collected: {len(sync_metadata)}")
            
            # Metadata collection should show good speedup
            assert speedup > 1.2, f"Async metadata collection too slow: {speedup:.2f}x"
        
        finally:
            shutil.rmtree(root)
    
    @pytest.mark.asyncio
    async def test_parallel_tree_traversal(self):
        """Test traversing multiple trees in parallel with async."""
        # Create multiple test trees
        roots = [
            self.create_test_tree(num_dirs=5, files_per_dir=10)
            for _ in range(3)
        ]
        
        try:
            # Time sequential sync traversal
            start = time.perf_counter()
            sync_counts = []
            for root in roots:
                count = 0
                sync_node = SyncNode(root)
                sync_adapter = SyncAdapter()
                for _ in traverse_tree(sync_node, sync_adapter):
                    count += 1
                sync_counts.append(count)
            sync_time = time.perf_counter() - start
            
            # Time parallel async traversal
            async def traverse_one(root):
                count = 0
                async for _ in traverse_tree_async(root):
                    count += 1
                return count
            
            start = time.perf_counter()
            async_counts = await asyncio.gather(*[traverse_one(root) for root in roots])
            async_time = time.perf_counter() - start
            
            # Verify same counts
            assert sync_counts == async_counts
            
            # Calculate speedup
            speedup = sync_time / async_time if async_time > 0 else 1.0
            
            print(f"\nParallel traversal of 3 trees:")
            print(f"  Sync (sequential) time: {sync_time:.4f}s")
            print(f"  Async (parallel) time: {async_time:.4f}s")
            print(f"  Speedup: {speedup:.2f}x")
            print(f"  Total nodes: {sum(sync_counts)}")
            
            # Parallel traversal should show significant speedup
            assert speedup > 2.0, f"Parallel traversal not fast enough: {speedup:.2f}x"
        
        finally:
            for root in roots:
                shutil.rmtree(root)
    
    def test_batch_size_impact(self):
        """Test impact of different batch sizes on async performance."""
        root = self.create_test_tree(num_dirs=10, files_per_dir=20)
        
        try:
            batch_sizes = [16, 64, 256, 1024]
            times = {}
            
            for batch_size in batch_sizes:
                async def traverse_with_batch_size():
                    count = 0
                    async for _ in traverse_tree_async(root, batch_size=batch_size):
                        count += 1
                    return count
                
                start = time.perf_counter()
                count = asyncio.run(traverse_with_batch_size())
                elapsed = time.perf_counter() - start
                times[batch_size] = elapsed
                
                print(f"\nBatch size {batch_size}: {elapsed:.4f}s ({count} nodes)")
            
            # Verify that extreme batch sizes aren't too slow
            min_time = min(times.values())
            max_time = max(times.values())
            
            # Max should be within 2x of min
            assert max_time < min_time * 2, f"Batch size impact too large: {max_time/min_time:.2f}x difference"
        
        finally:
            shutil.rmtree(root)
    
    def test_memory_usage_comparison(self):
        """Verify async doesn't use excessive memory compared to sync."""
        import tracemalloc
        
        root = self.create_test_tree(num_dirs=20, files_per_dir=20)
        
        try:
            # Measure sync memory usage
            tracemalloc.start()
            sync_snapshot1 = tracemalloc.take_snapshot()
            
            sync_node = SyncNode(root)
            sync_adapter = SyncAdapter()
            sync_nodes = list(traverse_tree(sync_node, sync_adapter))
            
            sync_snapshot2 = tracemalloc.take_snapshot()
            sync_stats = sync_snapshot2.compare_to(sync_snapshot1, 'lineno')
            sync_memory = sum(stat.size_diff for stat in sync_stats) / 1024 / 1024  # MB
            tracemalloc.stop()
            
            # Clear memory
            del sync_nodes
            
            # Measure async memory usage
            async def collect_all():
                nodes = []
                async for node in traverse_tree_async(root):
                    nodes.append(node)
                return nodes
            
            tracemalloc.start()
            async_snapshot1 = tracemalloc.take_snapshot()
            
            async_nodes = asyncio.run(collect_all())
            
            async_snapshot2 = tracemalloc.take_snapshot()
            async_stats = async_snapshot2.compare_to(async_snapshot1, 'lineno')
            async_memory = sum(stat.size_diff for stat in async_stats) / 1024 / 1024  # MB
            tracemalloc.stop()
            
            print(f"\nMemory usage:")
            print(f"  Sync: {sync_memory:.2f} MB")
            print(f"  Async: {async_memory:.2f} MB")
            print(f"  Ratio: {async_memory/sync_memory if sync_memory > 0 else 0:.2f}x")
            
            # Async shouldn't use more than 2x the memory of sync
            # (futures and coroutines have overhead)
            if sync_memory > 0:
                memory_ratio = async_memory / sync_memory
                assert memory_ratio < 2.0, f"Async uses too much memory: {memory_ratio:.2f}x sync"
        
        finally:
            shutil.rmtree(root)


if __name__ == "__main__":
    # Run with: python -m pytest tests/test_performance_async.py -v -s
    pytest.main([__file__, "-v", "-s"])