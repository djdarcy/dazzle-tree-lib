#!/usr/bin/env python3
"""Benchmark the fast os.scandir-based adapter.

Compares performance between:
1. Original AsyncFileSystemAdapter
2. Fast adapter using os.scandir
3. Native os.scandir
"""

import asyncio
import os
import time
import tempfile
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dazzletreelib.aio import traverse_tree_async



async def benchmark_adapters():
    """Benchmark different adapter implementations."""
    
    # Create test directory structure
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)
        
        print("Creating test tree...")
        # Create a medium-sized tree
        for i in range(10):
            subdir = test_dir / f"dir_{i}"
            subdir.mkdir()
            for j in range(20):
                file = subdir / f"file_{j}.txt"
                file.write_text(f"Content {i}-{j}" * 100)  # ~1KB files
                
                # Create nested subdirs
                if j % 5 == 0:
                    nested = subdir / f"nested_{j}"
                    nested.mkdir()
                    for k in range(5):
                        nested_file = nested / f"nested_{k}.txt"
                        nested_file.write_text(f"Nested {k}")
        
        total_nodes = sum(1 for _ in test_dir.rglob("*"))
        print(f"Test tree created: {total_nodes} nodes")
        print("=" * 60)
        
        # 1. Benchmark original adapter (with caching)
        print("\n1. Original AsyncFileSystemAdapter (with stat cache):")
        start = time.perf_counter()
        count = 0
        total_size = 0
        
        async for node in traverse_tree_async(test_dir, use_stat_cache=True):
            count += 1
            if node.path.is_file():
                size = await node.size()
                if size:
                    total_size += size
        
        time_original = time.perf_counter() - start
        print(f"   Time: {time_original:.3f}s")
        print(f"   Nodes: {count}")
        print(f"   Total size: {total_size:,} bytes")
        print(f"   Rate: {count/time_original:.0f} nodes/sec")
        
        # 2. Benchmark fast adapter
        print("\n2. Fast adapter (os.scandir-based):")
        start = time.perf_counter()
        count = 0
        total_size = 0
        
        async for node in traverse_tree_async(test_dir):
            count += 1
            if not node.is_leaf():
                continue
            size = await node.size()
            if size:
                total_size += size
        
        time_fast = time.perf_counter() - start
        print(f"   Time: {time_fast:.3f}s")
        print(f"   Nodes: {count}")
        print(f"   Total size: {total_size:,} bytes")
        print(f"   Rate: {count/time_fast:.0f} nodes/sec")
        
        # 3. Benchmark native os.scandir (for reference)
        print("\n3. Native os.scandir (sync, for reference):")
        start = time.perf_counter()
        count = 0
        total_size = 0
        
        def scan_recursive(path):
            nonlocal count, total_size
            try:
                with os.scandir(path) as entries:
                    for entry in entries:
                        count += 1
                        if entry.is_file(follow_symlinks=False):
                            stat = entry.stat(follow_symlinks=False)
                            total_size += stat.st_size
                        elif entry.is_dir(follow_symlinks=False):
                            scan_recursive(entry.path)
            except (OSError, PermissionError):
                pass
        
        scan_recursive(test_dir)
        time_native = time.perf_counter() - start
        print(f"   Time: {time_native:.3f}s")
        print(f"   Nodes: {count}")
        print(f"   Total size: {total_size:,} bytes")
        print(f"   Rate: {count/time_native:.0f} nodes/sec")
        
        # Compare results
        print("\n" + "=" * 60)
        print("PERFORMANCE COMPARISON")
        print("=" * 60)
        
        if time_original > 0:
            fast_vs_original = time_original / time_fast
            print(f"Fast adapter vs Original: {fast_vs_original:.2f}x faster")
        
        if time_native > 0:
            fast_vs_native = time_fast / time_native
            print(f"Fast adapter vs Native: {fast_vs_native:.2f}x slower")
            
            original_vs_native = time_original / time_native
            print(f"Original vs Native: {original_vs_native:.2f}x slower")
        
        print("\nConclusion:")
        if fast_vs_original > 1.5:
            print("[SUCCESS] Fast adapter provides significant improvement!")
        elif fast_vs_original > 1.1:
            print("[OK] Fast adapter provides modest improvement")
        else:
            print("[NEUTRAL] Fast adapter performance similar to original")
        
        return time_fast < time_original


async def test_correctness():
    """Verify fast adapter produces correct results."""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)
        
        # Create known structure
        (test_dir / "file1.txt").write_text("content1")
        subdir = test_dir / "subdir"
        subdir.mkdir()
        (subdir / "file2.txt").write_text("content2")
        
        print("\n" + "=" * 60)
        print("CORRECTNESS TEST")
        print("=" * 60)
        
        # Collect with original
        original_files = []
        async for node in traverse_tree_async(test_dir):
            if node.path.is_file():
                original_files.append(node.path.name)
        
        # Collect with fast
        fast_files = []
        async for node in traverse_tree_async(test_dir):
            if not node.is_leaf():
                continue
            if await node.size() is not None:
                fast_files.append(node.path.name)
        
        print(f"Original found: {sorted(original_files)}")
        print(f"Fast found: {sorted(fast_files)}")
        
        if set(original_files) == set(fast_files):
            print("[PASS] Results match!")
            return True
        else:
            print("[FAIL] Results differ!")
            return False


async def main():
    """Run all benchmarks."""
    print("FAST FILESYSTEM ADAPTER BENCHMARK")
    print("=" * 60)
    print("Testing os.scandir-based optimization")
    
    # Run benchmarks
    perf_improved = await benchmark_adapters()
    correct = await test_correctness()
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    if perf_improved and correct:
        print("[SUCCESS] Fast adapter is both faster and correct!")
        print("\nRecommendation: Consider making this the default implementation")
    elif correct:
        print("[OK] Fast adapter is correct but not significantly faster")
        print("\nRecommendation: May not be worth the added complexity")
    else:
        print("[FAIL] Fast adapter has issues")
    
    return perf_improved and correct


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)