#!/usr/bin/env python
"""
Diagnostic script specifically for cache hit performance issues.
Fast mode is sometimes SLOWER than safe mode for cache hits.
"""

import asyncio
import time
import gc
import sys
from pathlib import Path
from typing import List

sys.path.insert(0, ".")

from dazzletreelib.aio.adapters.cache_completeness_adapter import CompletenessAwareCacheAdapter


class MockNode:
    """Mock node for testing."""
    def __init__(self, path):
        self.path = path


class MockAdapter:
    """Mock adapter that generates configurable children."""
    def __init__(self, children_per_node=10):
        self.children_per_node = children_per_node
        self.call_count = 0

    async def get_children(self, node):
        """Generate mock children."""
        self.call_count += 1
        path = node.path if hasattr(node, 'path') else Path(str(node))
        for i in range(self.children_per_node):
            child_path = path / f"child_{i}"
            yield MockNode(child_path)


async def measure_cache_hit_performance():
    """Measure cache hit performance in detail."""
    print("=" * 80)
    print("CACHE HIT PERFORMANCE DIAGNOSTIC")
    print("=" * 80)

    # Test parameters
    num_paths = 100
    num_iterations = 10
    paths = [Path(f"/test/path_{i}") for i in range(num_paths)]

    results = []

    for test_run in range(10):
        print(f"\n--- Test Run {test_run + 1}/10 ---")

        # Create fresh adapters
        mock_safe = MockAdapter(children_per_node=10)
        safe_adapter = CompletenessAwareCacheAdapter(
            mock_safe,
            enable_oom_protection=True,
            max_entries=10000
        )

        mock_fast = MockAdapter(children_per_node=10)
        fast_adapter = CompletenessAwareCacheAdapter(
            mock_fast,
            enable_oom_protection=False
        )

        # Warm up caches (fill them with data)
        print("Warming up caches...", end=" ")
        for path in paths:
            node = MockNode(path)
            async for _ in safe_adapter.get_children(node):
                pass
            async for _ in fast_adapter.get_children(node):
                pass
        print(f"Safe cache size: {len(safe_adapter.cache)}, Fast cache size: {len(fast_adapter.cache)}")

        # Verify both got same number of cache misses (should be equal to num_paths)
        print(f"Safe misses: {safe_adapter.misses}, Fast misses: {fast_adapter.misses}")

        # Reset hit counters
        safe_adapter.hits = 0
        fast_adapter.hits = 0

        # Now measure cache hit performance
        print(f"Measuring cache hits ({num_iterations} iterations)...")

        # Safe mode cache hits
        gc.collect()
        start = time.perf_counter()
        for _ in range(num_iterations):
            for path in paths:
                node = MockNode(path)
                count = 0
                async for _ in safe_adapter.get_children(node):
                    count += 1
        safe_time = time.perf_counter() - start
        safe_hits = safe_adapter.hits

        # Fast mode cache hits
        gc.collect()
        start = time.perf_counter()
        for _ in range(num_iterations):
            for path in paths:
                node = MockNode(path)
                count = 0
                async for _ in fast_adapter.get_children(node):
                    count += 1
        fast_time = time.perf_counter() - start
        fast_hits = fast_adapter.hits

        # Calculate metrics
        improvement = (safe_time - fast_time) / safe_time * 100 if safe_time > 0 else 0

        print(f"  Safe: {safe_time:.4f}s ({safe_hits} hits)")
        print(f"  Fast: {fast_time:.4f}s ({fast_hits} hits)")
        print(f"  Improvement: {improvement:.1f}% {'PASS' if improvement > -10 else 'FAIL'}")

        results.append({
            'run': test_run + 1,
            'safe_time': safe_time,
            'fast_time': fast_time,
            'improvement': improvement,
            'passed': improvement > -10  # Allow 10% slower
        })

    # Analyze results
    print("\n" + "=" * 80)
    print("ANALYSIS")
    print("=" * 80)

    passed = sum(1 for r in results if r['passed'])
    failed = 10 - passed

    print(f"\nResults: {passed}/10 passed, {failed}/10 failed")

    if failed > 0:
        print("\nFailed runs:")
        for r in results:
            if not r['passed']:
                print(f"  Run {r['run']}: Fast was {-r['improvement']:.1f}% slower")

    improvements = [r['improvement'] for r in results]
    avg_improvement = sum(improvements) / len(improvements)
    print(f"\nAverage improvement: {avg_improvement:.1f}%")

    return results


async def profile_cache_hit_code_path():
    """Profile exactly what happens during a cache hit."""
    print("\n" + "=" * 80)
    print("CACHE HIT CODE PATH PROFILING")
    print("=" * 80)

    # Create simple test case
    mock_safe = MockAdapter(children_per_node=10)
    safe_adapter = CompletenessAwareCacheAdapter(
        mock_safe,
        enable_oom_protection=True
    )

    mock_fast = MockAdapter(children_per_node=10)
    fast_adapter = CompletenessAwareCacheAdapter(
        mock_fast,
        enable_oom_protection=False
    )

    # Add one item to cache
    node = MockNode(Path("/test"))

    # Fill cache
    async for _ in safe_adapter.get_children(node):
        pass
    async for _ in fast_adapter.get_children(node):
        pass

    # Now time individual operations for cache hits
    iterations = 10000

    print(f"\nTiming {iterations} cache hit operations...")

    # Time safe mode operations
    operations = []
    for i in range(5):
        gc.collect()
        start = time.perf_counter()
        for _ in range(iterations):
            async for _ in safe_adapter.get_children(node):
                pass
        elapsed = time.perf_counter() - start
        operations.append(elapsed)
        print(f"  Safe mode run {i+1}: {elapsed:.4f}s")

    safe_avg = sum(operations) / len(operations)
    print(f"  Safe average: {safe_avg:.4f}s")

    # Time fast mode operations
    operations = []
    for i in range(5):
        gc.collect()
        start = time.perf_counter()
        for _ in range(iterations):
            async for _ in fast_adapter.get_children(node):
                pass
        elapsed = time.perf_counter() - start
        operations.append(elapsed)
        print(f"  Fast mode run {i+1}: {elapsed:.4f}s")

    fast_avg = sum(operations) / len(operations)
    print(f"  Fast average: {fast_avg:.4f}s")

    print(f"\nPer-operation time:")
    print(f"  Safe: {safe_avg/iterations*1000000:.2f} microseconds")
    print(f"  Fast: {fast_avg/iterations*1000000:.2f} microseconds")
    print(f"  Difference: {(fast_avg-safe_avg)/iterations*1000000:.2f} microseconds")


async def test_different_cache_sizes():
    """Test if cache size affects performance."""
    print("\n" + "=" * 80)
    print("CACHE SIZE IMPACT TEST")
    print("=" * 80)

    cache_sizes = [10, 100, 1000, 10000]

    for size in cache_sizes:
        print(f"\nCache size: {size} entries")

        # Create adapters
        mock_safe = MockAdapter()
        safe_adapter = CompletenessAwareCacheAdapter(
            mock_safe,
            enable_oom_protection=True,
            max_entries=size * 2  # Ensure we don't hit limit
        )

        mock_fast = MockAdapter()
        fast_adapter = CompletenessAwareCacheAdapter(
            mock_fast,
            enable_oom_protection=False
        )

        # Fill caches
        for i in range(size):
            node = MockNode(Path(f"/test/path_{i}"))
            async for _ in safe_adapter.get_children(node):
                pass
            async for _ in fast_adapter.get_children(node):
                pass

        # Test cache hit performance
        test_node = MockNode(Path("/test/path_0"))  # First entry
        iterations = 1000

        # Safe mode
        gc.collect()
        start = time.perf_counter()
        for _ in range(iterations):
            async for _ in safe_adapter.get_children(test_node):
                pass
        safe_time = time.perf_counter() - start

        # Fast mode
        gc.collect()
        start = time.perf_counter()
        for _ in range(iterations):
            async for _ in fast_adapter.get_children(test_node):
                pass
        fast_time = time.perf_counter() - start

        improvement = (safe_time - fast_time) / safe_time * 100
        print(f"  Safe: {safe_time:.4f}s, Fast: {fast_time:.4f}s")
        print(f"  Improvement: {improvement:.1f}% {'OK' if improvement > -10 else 'SLOW'}")


async def test_isinstance_overhead():
    """Test if isinstance() checks are causing the slowdown."""
    print("\n" + "=" * 80)
    print("ISINSTANCE() OVERHEAD TEST")
    print("=" * 80)

    iterations = 1000000
    test_list = [1, 2, 3, 4, 5]

    # Test 1: isinstance check
    start = time.perf_counter()
    for _ in range(iterations):
        if isinstance(test_list, list):
            pass
    isinstance_time = time.perf_counter() - start

    # Test 2: no check
    start = time.perf_counter()
    for _ in range(iterations):
        pass
    no_check_time = time.perf_counter() - start

    print(f"isinstance() check: {isinstance_time:.4f}s")
    print(f"No check: {no_check_time:.4f}s")
    print(f"Overhead: {(isinstance_time - no_check_time) / iterations * 1000000:.2f} microseconds per call")

    # Test yielding from list with isinstance check
    print(f"\nYielding from list test ({iterations} iterations):")

    async def yield_with_check(data):
        if isinstance(data, list):
            for item in data:
                yield item

    async def yield_without_check(data):
        for item in data:
            yield item

    # With check
    start = time.perf_counter()
    for _ in range(iterations // 100):  # Fewer iterations for async
        async for _ in yield_with_check(test_list):
            pass
    with_check = time.perf_counter() - start

    # Without check
    start = time.perf_counter()
    for _ in range(iterations // 100):
        async for _ in yield_without_check(test_list):
            pass
    without_check = time.perf_counter() - start

    print(f"With isinstance: {with_check:.4f}s")
    print(f"Without: {without_check:.4f}s")
    print(f"Overhead: {((with_check - without_check) / with_check * 100):.1f}%")


def main():
    """Run all diagnostics."""
    print("Cache Hit Performance Diagnostic Tool")
    print(f"Python {sys.version}")
    print(f"Platform: {sys.platform}")

    # Run diagnostics
    asyncio.run(measure_cache_hit_performance())
    asyncio.run(profile_cache_hit_code_path())
    asyncio.run(test_different_cache_sizes())
    asyncio.run(test_isinstance_overhead())

    print("\n" + "=" * 80)
    print("DIAGNOSIS COMPLETE")
    print("=" * 80)
    print("\nThe cache hit performance issue is likely caused by:")
    print("1. The isinstance() check in the fast path")
    print("2. Small overhead that's more noticeable for cache hits (which are very fast)")
    print("3. The 'if isinstance(entry.data, list)' check before yielding")
    print("\nRecommendation: Remove the isinstance check from the fast path cache hit code.")


if __name__ == "__main__":
    main()