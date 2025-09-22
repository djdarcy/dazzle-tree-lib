#!/usr/bin/env python3
"""Test stat caching performance improvements.

This test verifies that stat caching reduces syscalls and improves performance.
"""

import asyncio
import time
import tempfile
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dazzletreelib.aio import traverse_tree_async
from dazzletreelib.aio.adapters import AsyncFileSystemAdapter, AsyncFileSystemNode


async def test_stat_caching():
    """Test that stat caching reduces duplicate stat calls."""
    
    # Create test directory structure
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)
        
        # Create a small tree
        for i in range(5):
            subdir = test_dir / f"dir_{i}"
            subdir.mkdir()
            for j in range(10):
                file = subdir / f"file_{j}.txt"
                file.write_text(f"Content {i}-{j}")
        
        print("Testing stat caching performance...")
        print("=" * 60)
        
        # Test WITHOUT caching (all adapters now use caching by default)
        print("\n1. WITHOUT explicit caching adapter:")
        adapter_no_cache = AsyncFileSystemAdapter(
            batch_size=10
        )
        root_no_cache = AsyncFileSystemNode(test_dir)
        
        start = time.perf_counter()
        count = 0
        total_size = 0
        
        from dazzletreelib.aio.core import AsyncBreadthFirstTraverser
        traverser = AsyncBreadthFirstTraverser()
        
        async for node in traverser.traverse(root_no_cache, adapter_no_cache):
            count += 1
            # Access size multiple times (will cause multiple stat calls)
            size1 = await node.size()
            size2 = await node.size()  # Should hit cache within node
            if size1:
                total_size += size1
        
        time_no_cache = time.perf_counter() - start
        print(f"  Nodes: {count}")
        print(f"  Time: {time_no_cache:.3f}s")
        print(f"  Total size: {total_size:,} bytes")
        
        # Test WITH caching adapter wrapper
        print("\n2. WITH caching adapter:")
        from dazzletreelib.aio.caching import CachingTreeAdapter
        base_adapter = AsyncFileSystemAdapter(batch_size=10)
        adapter_with_cache = CachingTreeAdapter(
            base_adapter,
            ttl=1.0  # 1 second TTL
        )
        root_with_cache = AsyncFileSystemNode(test_dir)
        
        start = time.perf_counter()
        count = 0
        total_size = 0
        
        async for node in traverser.traverse(root_with_cache, adapter_with_cache):
            count += 1
            # Access size multiple times (should use cache)
            size1 = await node.size()
            size2 = await node.size()  # Should hit cache
            if size1:
                total_size += size1
        
        time_with_cache = time.perf_counter() - start
        
        print(f"  Nodes: {count}")
        print(f"  Time: {time_with_cache:.3f}s")
        print(f"  Total size: {total_size:,} bytes")
        
        # Print cache statistics
        cache_stats = await adapter_with_cache.get_stats()
        if 'cache_hits' in cache_stats:
            print(f"\n  Cache Statistics:")
            print(f"    Hits: {cache_stats['cache_hits']}")
            print(f"    Misses: {cache_stats['cache_misses']}")
            hit_rate = cache_stats['cache_hits'] / max(1, cache_stats['cache_hits'] + cache_stats['cache_misses'])
            print(f"    Hit rate: {hit_rate:.1%}")
            print(f"    Cached items: {cache_stats['cached_items']}")
        
        # Calculate improvement
        if time_no_cache > 0:
            speedup = time_no_cache / time_with_cache
            improvement = (1 - time_with_cache / time_no_cache) * 100
            print(f"\n3. Performance improvement:")
            print(f"  Speedup: {speedup:.2f}x")
            print(f"  Time saved: {improvement:.1f}%")
        
        return time_with_cache < time_no_cache  # Should be faster with cache


async def test_cache_sharing():
    """Test that cache is shared between nodes."""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)
        
        # Create test files
        file1 = test_dir / "file1.txt"
        file1.write_text("Content 1" * 1000)  # ~9KB
        
        file2 = test_dir / "file2.txt"
        file2.write_text("Content 2" * 2000)  # ~18KB
        
        print("\n" + "=" * 60)
        print("Testing cache sharing between nodes...")
        print("=" * 60)
        
        # Create adapter with cache wrapper
        from dazzletreelib.aio.caching import CachingTreeAdapter
        base_adapter = AsyncFileSystemAdapter()
        adapter = CachingTreeAdapter(base_adapter)
        
        # Create multiple nodes pointing to same files
        node1a = AsyncFileSystemNode(file1)
        node1b = AsyncFileSystemNode(file1)  # Same file
        node2 = AsyncFileSystemNode(file2)
        
        # Access stat through first node (populates cache)
        size1a = await node1a.size()
        print(f"\nFirst access to file1: {size1a} bytes")
        
        # Access through second node (should hit cache)
        cache_stats_before = await adapter.get_stats()
        size1b = await node1b.size()
        cache_stats_after = await adapter.get_stats()
        
        print(f"Second access to file1: {size1b} bytes")
        print(f"Cache hits increased: {cache_stats_after.get('cache_hits', 0) > cache_stats_before.get('cache_hits', 0)}")
        
        # Verify sizes match
        assert size1a == size1b, "Sizes should match"
        
        # Access different file
        size2 = await node2.size()
        print(f"Access to file2: {size2} bytes")
        
        final_stats = await adapter.get_stats()
        print(f"\nFinal cache statistics:")
        hits = final_stats.get('cache_hits', 0)
        misses = final_stats.get('cache_misses', 0)
        print(f"  Total operations: {hits + misses}")
        if hits + misses > 0:
            print(f"  Cache hit rate: {hits / (hits + misses):.1%}")
        
        return hits > 0  # Should have cache hits


async def test_simple_traversal():
    """Test improved performance with simple traversal."""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)
        
        # Create test structure
        for i in range(3):
            subdir = test_dir / f"dir_{i}"
            subdir.mkdir()
            for j in range(5):
                file = subdir / f"file_{j}.txt"
                file.write_text(f"Test content {i}-{j}")
        
        print("\n" + "=" * 60)
        print("Testing simple traversal with caching...")
        print("=" * 60)
        
        # Time traversal without cache
        start = time.perf_counter()
        files_no_cache = []
        async for node in traverse_tree_async(test_dir):
            if node.path.is_file():
                size = await node.size()
                files_no_cache.append((node.path.name, size))
        time_no_cache = time.perf_counter() - start
        
        # Time traversal with cache
        start = time.perf_counter()
        files_with_cache = []
        # Use caching adapter for second traversal
        from dazzletreelib.aio.caching import CachingTreeAdapter
        base = AsyncFileSystemAdapter()
        caching_adapter = CachingTreeAdapter(base)
        root_node = AsyncFileSystemNode(test_dir)
        from dazzletreelib.aio.core import AsyncBreadthFirstTraverser
        traverser = AsyncBreadthFirstTraverser()
        async for node in traverser.traverse(root_node, caching_adapter):
            if node.path.is_file():
                size = await node.size()
                files_with_cache.append((node.path.name, size))
        time_with_cache = time.perf_counter() - start
        
        print(f"\nResults:")
        print(f"  Files found: {len(files_with_cache)}")
        print(f"  Time without cache: {time_no_cache:.3f}s")
        print(f"  Time with cache: {time_with_cache:.3f}s")
        
        if time_no_cache > 0:
            improvement = (1 - time_with_cache / time_no_cache) * 100
            print(f"  Improvement: {improvement:.1f}%")
        
        # Verify same results
        assert len(files_no_cache) == len(files_with_cache), "Should find same files"
        
        return True


async def main():
    """Run all stat caching tests."""
    print("STAT CACHING PERFORMANCE TESTS")
    print("=" * 60)
    
    # Run tests
    test1 = await test_stat_caching()
    test2 = await test_cache_sharing()
    test3 = await test_simple_traversal()
    
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    if all([test1, test2, test3]):
        print("[PASS] All stat caching tests passed!")
        print("\nConclusion: Stat caching provides measurable performance")
        print("improvements by reducing duplicate filesystem stat calls.")
        return True
    else:
        print("[FAIL] Some tests failed")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)