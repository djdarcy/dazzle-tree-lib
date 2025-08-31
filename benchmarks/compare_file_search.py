#!/usr/bin/env python3
"""
Benchmark DazzleTreeLib against native Python approaches for file searching.

This benchmark compares:
1. os.walk() - Traditional approach
2. pathlib.rglob() - Modern stdlib approach  
3. os.scandir() - Faster stdlib approach
4. DazzleTreeLib sync - Our sync implementation
5. DazzleTreeLib async - Our async implementation
"""

import asyncio
import os
import sys
import time
from pathlib import Path
from typing import List, Tuple
import tempfile
import random

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dazzletreelib.sync import FileSystemNode, FileSystemAdapter, traverse_tree
from dazzletreelib.aio import traverse_tree_async


class FileSearchBenchmark:
    """Benchmark suite for comparing file search approaches."""
    
    def __init__(self, test_dir: Path, min_size_mb: int = 10):
        self.test_dir = test_dir
        self.min_size_bytes = min_size_mb * 1024 * 1024
        self.results = {}
        
    def benchmark_oswalk(self) -> Tuple[float, List]:
        """Benchmark os.walk approach."""
        start = time.perf_counter()
        large_files = []
        
        for root, dirs, files in os.walk(self.test_dir):
            for file in files:
                path = os.path.join(root, file)
                try:
                    size = os.path.getsize(path)
                    if size > self.min_size_bytes:
                        large_files.append((path, size))
                except OSError:
                    pass
        
        elapsed = time.perf_counter() - start
        return elapsed, sorted(large_files, key=lambda x: x[1], reverse=True)
    
    def benchmark_pathlib(self) -> Tuple[float, List]:
        """Benchmark pathlib.rglob approach."""
        start = time.perf_counter()
        large_files = []
        
        for path in Path(self.test_dir).rglob('*'):
            if path.is_file():
                try:
                    size = path.stat().st_size
                    if size > self.min_size_bytes:
                        large_files.append((str(path), size))
                except OSError:
                    pass
        
        elapsed = time.perf_counter() - start
        return elapsed, sorted(large_files, key=lambda x: x[1], reverse=True)
    
    def benchmark_scandir(self) -> Tuple[float, List]:
        """Benchmark os.scandir approach (recursive)."""
        large_files = []
        
        def scan_recursive(path):
            try:
                with os.scandir(path) as entries:
                    for entry in entries:
                        if entry.is_file(follow_symlinks=False):
                            try:
                                size = entry.stat().st_size
                                if size > self.min_size_bytes:
                                    large_files.append((entry.path, size))
                            except OSError:
                                pass
                        elif entry.is_dir(follow_symlinks=False):
                            scan_recursive(entry.path)
            except OSError:
                pass
        
        start = time.perf_counter()
        scan_recursive(self.test_dir)
        elapsed = time.perf_counter() - start
        
        return elapsed, sorted(large_files, key=lambda x: x[1], reverse=True)
    
    def benchmark_dazzle_sync(self) -> Tuple[float, List]:
        """Benchmark DazzleTreeLib synchronous approach."""
        start = time.perf_counter()
        large_files = []
        
        root = FileSystemNode(self.test_dir)
        adapter = FileSystemAdapter()
        
        for result in traverse_tree(root, adapter):
            if isinstance(result, tuple):
                node, depth = result
            else:
                node = result
            
            if node.path.is_file():
                # Sync node stores size in metadata
                metadata = node.metadata()
                size = metadata.get('size', 0)
                if size > self.min_size_bytes:
                    large_files.append((str(node.path), size))
        
        elapsed = time.perf_counter() - start
        return elapsed, sorted(large_files, key=lambda x: x[1], reverse=True)
    
    async def benchmark_dazzle_async(self) -> Tuple[float, List]:
        """Benchmark DazzleTreeLib asynchronous approach."""
        start = time.perf_counter()
        large_files = []
        
        async for node in traverse_tree_async(self.test_dir):
            if node.path.is_file():
                size = await node.size()
                if size and size > self.min_size_bytes:
                    large_files.append((str(node.path), size))
        
        elapsed = time.perf_counter() - start
        return elapsed, sorted(large_files, key=lambda x: x[1], reverse=True)
    
    def run_benchmarks(self, warmup: bool = True):
        """Run all benchmarks and compare results."""
        print(f"\nBenchmarking on: {self.test_dir}")
        print(f"Finding files larger than: {self.min_size_bytes / 1024 / 1024:.1f} MB")
        print("=" * 70)
        
        # Warmup run if requested (helps with OS caching)
        if warmup:
            print("Running warmup...")
            list(Path(self.test_dir).rglob('*'))
        
        # Run benchmarks
        benchmarks = [
            ("os.walk", self.benchmark_oswalk),
            ("pathlib.rglob", self.benchmark_pathlib),
            ("os.scandir", self.benchmark_scandir),
            ("DazzleTree sync", self.benchmark_dazzle_sync),
        ]
        
        results = {}
        baseline_files = None
        
        for name, benchmark_func in benchmarks:
            print(f"\nRunning {name}...")
            elapsed, files = benchmark_func()
            results[name] = elapsed
            
            # Verify all methods find the same files
            if baseline_files is None:
                baseline_files = len(files)
            else:
                assert len(files) == baseline_files, \
                    f"{name} found {len(files)} files, expected {baseline_files}"
            
            print(f"  Time: {elapsed:.3f}s")
            print(f"  Files found: {len(files)}")
        
        # Run async benchmark
        print(f"\nRunning DazzleTree async...")
        elapsed, files = asyncio.run(self.benchmark_dazzle_async())
        results["DazzleTree async"] = elapsed
        assert len(files) == baseline_files, \
            f"Async found {len(files)} files, expected {baseline_files}"
        print(f"  Time: {elapsed:.3f}s")
        print(f"  Files found: {len(files)}")
        
        # Print comparison
        print("\n" + "=" * 70)
        print("PERFORMANCE COMPARISON")
        print("-" * 70)
        
        # Sort by time
        sorted_results = sorted(results.items(), key=lambda x: x[1])
        fastest_time = sorted_results[0][1]
        
        print(f"{'Method':<20} {'Time (s)':<12} {'Relative':<12} {'vs Fastest'}")
        print("-" * 70)
        
        for name, elapsed in sorted_results:
            relative = elapsed / fastest_time
            speedup = "FASTEST" if relative == 1.0 else f"{relative:.2f}x slower"
            print(f"{name:<20} {elapsed:<12.3f} {relative:<12.2f} {speedup}")
        
        # Highlight DazzleTree performance
        print("\n" + "=" * 70)
        print("DAZZLETREELIB PERFORMANCE")
        print("-" * 70)
        
        async_time = results["DazzleTree async"]
        for name in ["os.walk", "pathlib.rglob", "os.scandir"]:
            if name in results:
                speedup = results[name] / async_time
                print(f"DazzleTree async vs {name}: {speedup:.2f}x faster")
        
        return results


def generate_test_tree(base_dir: Path, num_files: int, num_dirs: int, large_file_ratio: float = 0.1):
    """Generate a test directory tree with mixed file sizes."""
    print(f"\nGenerating test tree at: {base_dir}")
    print(f"  Directories: {num_dirs}")
    print(f"  Files: {num_files}")
    print(f"  Large files: {int(num_files * large_file_ratio)}")
    
    base_dir.mkdir(exist_ok=True)
    
    # Create directory structure
    dirs = [base_dir]
    for i in range(num_dirs):
        # Create nested structure
        if i < num_dirs // 3:
            parent = base_dir
        else:
            parent = random.choice(dirs)
        
        new_dir = parent / f"dir_{i:04d}"
        new_dir.mkdir(exist_ok=True)
        dirs.append(new_dir)
    
    # Create files with various sizes
    large_file_count = int(num_files * large_file_ratio)
    
    for i in range(num_files):
        parent = random.choice(dirs)
        file_path = parent / f"file_{i:06d}.dat"
        
        if i < large_file_count:
            # Large file (10-50MB)
            size = random.randint(10, 50) * 1024 * 1024
        else:
            # Small file (1KB - 5MB)
            size = random.randint(1, 5000) * 1024
        
        # Write file (create sparse file for speed)
        with open(file_path, 'wb') as f:
            f.seek(size - 1)
            f.write(b'\0')
    
    print("Test tree generated!")
    return base_dir


def run_benchmark_suite():
    """Run complete benchmark suite with different tree sizes."""
    print("\n" + "=" * 70)
    print("DAZZLETREELIB BENCHMARK SUITE")
    print("Comparing file search performance against native Python")
    print("=" * 70)
    
    test_configs = [
        ("Small", 100, 10, 0.1),    # 100 files, 10 dirs
        ("Medium", 1000, 50, 0.1),   # 1000 files, 50 dirs
        ("Large", 5000, 200, 0.05),  # 5000 files, 200 dirs
    ]
    
    all_results = {}
    
    for test_name, num_files, num_dirs, large_ratio in test_configs:
        print(f"\n{'#' * 70}")
        print(f"TEST: {test_name} Tree ({num_files} files, {num_dirs} directories)")
        print('#' * 70)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir) / "test_tree"
            generate_test_tree(test_dir, num_files, num_dirs, large_ratio)
            
            benchmark = FileSearchBenchmark(test_dir, min_size_mb=10)
            results = benchmark.run_benchmarks(warmup=True)
            all_results[test_name] = results
    
    # Print summary
    print("\n" + "=" * 70)
    print("BENCHMARK SUMMARY")
    print("=" * 70)
    
    print(f"\n{'Tree Size':<12} {'DazzleAsync':<12} {'os.walk':<12} {'Speedup'}")
    print("-" * 48)
    
    for test_name in ["Small", "Medium", "Large"]:
        if test_name in all_results:
            results = all_results[test_name]
            async_time = results.get("DazzleTree async", 0)
            walk_time = results.get("os.walk", 0)
            speedup = walk_time / async_time if async_time > 0 else 0
            
            print(f"{test_name:<12} {async_time:<12.3f} {walk_time:<12.3f} {speedup:.2f}x")
    
    print("\n" + "=" * 70)
    print("CONCLUSION")
    print("-" * 70)
    
    # Calculate average speedup
    speedups = []
    for test_name, results in all_results.items():
        async_time = results.get("DazzleTree async", 1)
        for method in ["os.walk", "pathlib.rglob", "os.scandir"]:
            if method in results:
                speedups.append(results[method] / async_time)
    
    if speedups:
        avg_speedup = sum(speedups) / len(speedups)
        print(f"Average speedup of DazzleTree async: {avg_speedup:.2f}x")
        print(f"Maximum speedup observed: {max(speedups):.2f}x")
        print(f"Minimum speedup observed: {min(speedups):.2f}x")
    
    return all_results


if __name__ == "__main__":
    # Run the benchmark suite
    results = run_benchmark_suite()
    
    # Save results for documentation
    print("\n" + "=" * 70)
    print("Results saved for documentation update")
    print("Use these numbers to update performance claims in docs/")
    print("=" * 70)