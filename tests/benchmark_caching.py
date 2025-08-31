"""
Benchmark script to compare warm vs cold traversals with CachingTreeAdapter.

This script measures the performance improvement from caching by:
1. Creating a test directory structure
2. Performing cold traversal (no cache)
3. Performing warm traversal (with cache)
4. Comparing the results
"""

import asyncio
import tempfile
import time
from pathlib import Path
import shutil

from dazzletreelib.aio.caching import CachingTreeAdapter, FilesystemCachingAdapter
from dazzletreelib.aio.adapters.fast_filesystem import FastAsyncFileSystemAdapter, FastAsyncFileSystemNode
from dazzletreelib.aio.api import traverse_tree_async


async def create_test_structure(base_path: Path, depth: int = 3, width: int = 5) -> int:
    """
    Create a test directory structure.
    
    Args:
        base_path: Root directory for test structure
        depth: How many levels deep
        width: How many items per directory
        
    Returns:
        Total number of nodes created
    """
    total_nodes = 0
    
    def create_level(path: Path, current_depth: int):
        nonlocal total_nodes
        if current_depth >= depth:
            return
            
        path.mkdir(exist_ok=True)
        total_nodes += 1
        
        for i in range(width):
            # Create some files
            file_path = path / f"file_{i}.txt"
            file_path.write_text(f"Test content {i}")
            total_nodes += 1
            
            # Create some subdirectories
            if current_depth < depth - 1:
                subdir = path / f"dir_{i}"
                create_level(subdir, current_depth + 1)
    
    create_level(base_path, 0)
    return total_nodes


async def traverse_with_adapter(root: Path, adapter) -> tuple[int, float]:
    """
    Traverse a tree with the given adapter.
    
    Returns:
        Tuple of (node_count, elapsed_time)
    """
    start = time.perf_counter()
    node_count = 0
    
    root_node = FastAsyncFileSystemNode(root)
    async for child in adapter.get_children(root_node):
        node_count += 1
        # Traverse subdirectories
        if not child.is_leaf():
            async for _ in traverse_subtree(child, adapter):
                node_count += 1
    
    elapsed = time.perf_counter() - start
    return node_count, elapsed


async def traverse_subtree(node, adapter):
    """Recursively traverse a subtree."""
    async for child in adapter.get_children(node):
        yield child
        if not child.is_leaf():
            async for subchild in traverse_subtree(child, adapter):
                yield subchild


async def benchmark_caching():
    """Run the caching benchmark."""
    print("=" * 60)
    print("DazzleTreeLib CachingTreeAdapter Benchmark")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_root = Path(tmpdir) / "benchmark"
        
        # Create test structure
        print("\n1. Creating test directory structure...")
        total_nodes = await create_test_structure(test_root, depth=4, width=5)
        print(f"   Created {total_nodes} nodes")
        
        # Create adapters
        base_adapter = FastAsyncFileSystemAdapter()
        cached_adapter = CachingTreeAdapter(base_adapter, max_size=50000, ttl=300)
        filesystem_cached = FilesystemCachingAdapter(base_adapter, max_size=50000)
        
        # Test 1: Cold traversal (no cache)
        print("\n2. Cold traversal (first scan, no cache)...")
        count1, time1 = await traverse_with_adapter(test_root, cached_adapter)
        print(f"   Traversed {count1} nodes in {time1:.3f} seconds")
        print(f"   Speed: {count1/time1:.0f} nodes/second")
        
        # Test 2: Warm traversal (with cache)
        print("\n3. Warm traversal (second scan, with cache)...")
        count2, time2 = await traverse_with_adapter(test_root, cached_adapter)
        print(f"   Traversed {count2} nodes in {time2:.3f} seconds")
        print(f"   Speed: {count2/time2:.0f} nodes/second")
        
        # Test 3: Third traversal to verify cache stability
        print("\n4. Third traversal (verify cache stability)...")
        count3, time3 = await traverse_with_adapter(test_root, cached_adapter)
        print(f"   Traversed {count3} nodes in {time3:.3f} seconds")
        print(f"   Speed: {count3/time3:.0f} nodes/second")
        
        # Get cache statistics
        stats = cached_adapter.get_cache_stats()
        print("\n5. Cache Statistics:")
        print(f"   Cache hits: {stats['cache_hits']}")
        print(f"   Cache misses: {stats['cache_misses']}")
        print(f"   Hit rate: {stats['hit_rate']:.1%}")
        print(f"   Cache size: {stats['cache_size']}")
        print(f"   Concurrent waits: {stats['concurrent_waits']}")
        
        # Calculate speedup
        speedup = time1 / time2
        print("\n6. Performance Summary:")
        print(f"   Cold traversal: {time1:.3f}s")
        print(f"   Warm traversal: {time2:.3f}s")
        print(f"   Speedup: {speedup:.1f}x faster")
        
        if speedup >= 10:
            print(f"   [PASS] Achieved target 10x+ speedup!")
        else:
            print(f"   [INFO] Speedup is {speedup:.1f}x (target was 10x+)")
        
        # Test with filesystem-specific caching
        print("\n7. Testing FilesystemCachingAdapter...")
        cached_adapter.clear_cache()  # Clear to start fresh
        filesystem_cached.clear_cache()
        
        count4, time4 = await traverse_with_adapter(test_root, filesystem_cached)
        print(f"   First scan: {time4:.3f}s")
        
        count5, time5 = await traverse_with_adapter(test_root, filesystem_cached)
        print(f"   Second scan: {time5:.3f}s")
        
        fs_speedup = time4 / time5
        print(f"   Filesystem cache speedup: {fs_speedup:.1f}x")
        
        fs_stats = filesystem_cached.get_cache_stats()
        print(f"   Mtime cache size: {fs_stats.get('mtime_cache_size', 0)}")
        
        # Memory usage estimate
        import sys
        cache_memory = sys.getsizeof(cached_adapter._cache)
        print(f"\n8. Memory Usage:")
        print(f"   Cache memory: ~{cache_memory / 1024:.1f} KB")
        print(f"   Per-node overhead: ~{cache_memory / max(stats['cache_size'], 1):.0f} bytes")
        
        print("\n" + "=" * 60)
        print("Benchmark Complete!")
        print("=" * 60)


async def benchmark_large_tree():
    """Benchmark with a larger tree to test scalability."""
    print("\n" + "=" * 60)
    print("Large Tree Benchmark (100k+ nodes)")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_root = Path(tmpdir) / "large_benchmark"
        
        print("\nCreating large test structure...")
        print("This may take a moment...")
        
        # Create a large structure: depth=5, width=10 gives ~11k nodes
        total_nodes = await create_test_structure(test_root, depth=5, width=10)
        print(f"Created {total_nodes} nodes")
        
        base_adapter = FastAsyncFileSystemAdapter()
        cached_adapter = CachingTreeAdapter(base_adapter, max_size=100000, ttl=300)
        
        # Cold scan
        print("\nCold scan...")
        start = time.perf_counter()
        count1 = 0
        async for _ in traverse_tree_async(test_root, adapter=cached_adapter):
            count1 += 1
        cold_time = time.perf_counter() - start
        
        # Warm scan
        print("Warm scan...")
        start = time.perf_counter()
        count2 = 0
        async for _ in traverse_tree_async(test_root, adapter=cached_adapter):
            count2 += 1
        warm_time = time.perf_counter() - start
        
        speedup = cold_time / warm_time
        
        print(f"\nResults:")
        print(f"  Nodes: {count1}")
        print(f"  Cold: {cold_time:.2f}s ({count1/cold_time:.0f} nodes/s)")
        print(f"  Warm: {warm_time:.2f}s ({count2/warm_time:.0f} nodes/s)")
        print(f"  Speedup: {speedup:.1f}x")
        
        stats = cached_adapter.get_cache_stats()
        print(f"  Cache hit rate: {stats['hit_rate']:.1%}")


async def main():
    """Run all benchmarks."""
    await benchmark_caching()
    
    # Uncomment to run large tree benchmark
    # await benchmark_large_tree()


if __name__ == "__main__":
    asyncio.run(main())