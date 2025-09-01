#!/usr/bin/env python3
"""Benchmark script to compare old vs new AsyncFileSystemAdapter implementations."""

import asyncio
import time
import tempfile
import shutil
from pathlib import Path
from typing import Tuple
import statistics


async def benchmark_new_implementation(test_dir: Path, max_depth: int = None) -> Tuple[int, float]:
    """Benchmark the new unified scandir-based implementation."""
    from dazzletreelib.aio import traverse_tree_async
    
    start = time.perf_counter()
    count = 0
    
    async for node in traverse_tree_async(test_dir, max_depth=max_depth):
        count += 1
        # Force stat call to ensure fair comparison
        _ = await node._get_stat()
    
    elapsed = time.perf_counter() - start
    return count, elapsed


async def benchmark_old_implementation(test_dir: Path, max_depth: int = None) -> Tuple[int, float]:
    """Benchmark the old listdir-based implementation using backup."""
    # We'll need to temporarily import from backup
    import sys
    import importlib.util
    
    # Load the backup module
    spec = importlib.util.spec_from_file_location(
        "filesystem_backup",
        "C:/code/DazzleTreeLib/dazzletreelib/aio/adapters/filesystem.py.backup"
    )
    if spec and spec.loader:
        backup_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(backup_module)
        
        # Use the old implementation
        OldAsyncFileSystemAdapter = backup_module.AsyncFileSystemAdapter
        OldAsyncFileSystemNode = backup_module.AsyncFileSystemNode
        
        from dazzletreelib.aio.core import AsyncBreadthFirstTraverser
        
        adapter = OldAsyncFileSystemAdapter(use_stat_cache=True)
        root_node = OldAsyncFileSystemNode(test_dir, adapter.stat_cache)
        traverser = AsyncBreadthFirstTraverser()
        
        start = time.perf_counter()
        count = 0
        
        async for node in traverser.traverse(root_node, adapter, max_depth):
            count += 1
            # Force stat call for fair comparison
            _ = await node._get_stat()
        
        elapsed = time.perf_counter() - start
        return count, elapsed
    
    return 0, 0.0


def create_test_directory(num_files: int, depth: int = 3) -> Path:
    """Create a test directory structure for benchmarking."""
    test_dir = Path(tempfile.mkdtemp(prefix="dazzle_benchmark_"))
    
    # Create files in root
    for i in range(num_files // 3):
        (test_dir / f"file_{i:04d}.txt").write_text(f"content_{i}")
    
    # Create nested structure
    current_dir = test_dir
    for level in range(depth):
        subdir = current_dir / f"level_{level}"
        subdir.mkdir()
        
        # Add files at each level
        for i in range(num_files // (3 * depth)):
            (subdir / f"file_L{level}_{i:03d}.txt").write_text(f"L{level}_{i}")
        
        current_dir = subdir
    
    return test_dir


async def run_benchmarks():
    """Run comprehensive benchmarks comparing implementations."""
    print("=" * 60)
    print("DazzleTreeLib Performance Benchmark")
    print("Comparing old (listdir) vs new (scandir) implementations")
    print("=" * 60)
    
    results = []
    
    # Test cases
    test_cases = [
        ("Small Directory", 100, 2),
        ("Medium Directory", 1000, 3),
        ("Large Directory", 5000, 3),
    ]
    
    for test_name, num_files, depth in test_cases:
        print(f"\n{test_name} ({num_files} files, {depth} levels deep)")
        print("-" * 40)
        
        # Create test directory
        test_dir = create_test_directory(num_files, depth)
        
        try:
            # Warm up
            await benchmark_new_implementation(test_dir, max_depth=None)
            
            # Run multiple iterations for accuracy
            new_times = []
            old_times = []
            
            for i in range(3):
                # New implementation
                count_new, time_new = await benchmark_new_implementation(test_dir)
                new_times.append(time_new)
                
                # Old implementation (if available)
                try:
                    count_old, time_old = await benchmark_old_implementation(test_dir)
                    old_times.append(time_old)
                    
                    # Verify same results
                    if count_old > 0:
                        assert count_new == count_old, f"Count mismatch: {count_new} != {count_old}"
                except Exception as e:
                    print(f"  Old implementation not available: {e}")
                    old_times.append(0)
            
            # Calculate averages
            avg_new = statistics.mean(new_times)
            avg_old = statistics.mean(old_times) if any(old_times) else 0
            
            print(f"  Files traversed: {count_new}")
            print(f"  New implementation: {avg_new:.4f}s")
            
            if avg_old > 0:
                print(f"  Old implementation: {avg_old:.4f}s")
                speedup = avg_old / avg_new
                print(f"  SPEEDUP: {speedup:.2f}x faster")
                results.append((test_name, count_new, avg_old, avg_new, speedup))
            else:
                print(f"  Old implementation: N/A (backup not found)")
                results.append((test_name, count_new, 0, avg_new, 0))
            
        finally:
            # Clean up
            shutil.rmtree(test_dir, ignore_errors=True)
    
    # Summary table
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"{'Test Case':<20} {'Files':<10} {'Old (s)':<10} {'New (s)':<10} {'Speedup':<10}")
    print("-" * 60)
    
    for name, count, old_time, new_time, speedup in results:
        if old_time > 0:
            print(f"{name:<20} {count:<10} {old_time:<10.4f} {new_time:<10.4f} {speedup:<10.2f}x")
        else:
            print(f"{name:<20} {count:<10} {'N/A':<10} {new_time:<10.4f} {'N/A':<10}")
    
    # Test current working directory
    print("\n" + "=" * 60)
    print("REAL-WORLD TEST: DazzleTreeLib Project")
    print("=" * 60)
    
    project_dir = Path("C:/code/DazzleTreeLib")
    count, elapsed = await benchmark_new_implementation(project_dir, max_depth=3)
    print(f"  Files traversed (depth=3): {count}")
    print(f"  Time: {elapsed:.4f}s")
    print(f"  Throughput: {count/elapsed:.0f} files/second")


if __name__ == "__main__":
    asyncio.run(run_benchmarks())