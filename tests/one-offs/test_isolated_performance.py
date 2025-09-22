"""Test performance in isolation vs after memory pressure."""

import asyncio
import time
import gc
import pytest


class PerfNode:
    def __init__(self, path):
        self.path = path


class PerfTreeAdapter:
    """Large tree for performance testing."""
    def __init__(self, breadth=20, depth=3):
        self.breadth = breadth
        self.max_depth = depth

    async def get_children(self, node):
        path = str(node.path)
        current_depth = path.count('/')

        if current_depth >= self.max_depth:
            return

        for i in range(self.breadth):
            yield PerfNode(f"{path}/child_{i}")

    async def get_depth(self, node):
        return str(node.path).count('/')

    async def get_parent(self, node):
        return None


async def run_performance_test(label="Test"):
    """Run the actual performance test."""
    from dazzletreelib.aio.adapters.smart_caching import SmartCachingAdapter

    tree = PerfTreeAdapter(breadth=20, depth=3)

    # Fast mode
    fast_adapter = SmartCachingAdapter(
        tree,
        max_memory_mb=0,  # Unlimited
        track_traversal=True,
        enable_safe_mode=False
    )

    root = PerfNode('/')

    # Time fast mode
    start = time.time()
    async def traverse_fast(node):
        async for child in fast_adapter.get_children(node):
            await traverse_fast(child)

    await traverse_fast(root)
    fast_time = time.time() - start

    # Safe mode
    tree2 = PerfTreeAdapter(breadth=20, depth=3)
    safe_adapter = SmartCachingAdapter(
        tree2,
        max_memory_mb=1,  # Limited memory
        track_traversal=True,
        enable_safe_mode=True
    )

    # Time safe mode
    start = time.time()
    async def traverse_safe(node):
        async for child in safe_adapter.get_children(node):
            await traverse_safe(child)

    await traverse_safe(root)
    safe_time = time.time() - start

    print(f"\n{label}:")
    print(f"  Fast mode: {fast_time:.3f}s")
    print(f"  Safe mode: {safe_time:.3f}s")
    print(f"  Ratio: {fast_time/safe_time:.2f}x")

    return fast_time, safe_time


async def simulate_previous_test():
    """Simulate the test that runs before performance test."""
    from dazzletreelib.aio.adapters.smart_caching import SmartCachingAdapter

    print("\nSimulating test_fast_mode_unlimited_tracking...")

    # Create HUGE tree like the real test does
    large_tree = PerfTreeAdapter(breadth=50, depth=3)  # ~125,000 nodes!

    adapter = SmartCachingAdapter(
        large_tree,
        max_memory_mb=0,  # Unlimited
        track_traversal=True,
        enable_safe_mode=False
    )

    root = PerfNode('/')
    discovered_count = 0

    async def traverse(node):
        nonlocal discovered_count
        async for child in adapter.get_children(node):
            discovered_count += 1
            await traverse(child)

    start = time.time()
    await traverse(root)
    elapsed = time.time() - start

    stats = adapter.get_stats()
    print(f"  Traversed {discovered_count} nodes in {elapsed:.1f}s")
    print(f"  Discovered: {stats['discovered_nodes']}")
    print(f"  Cache size: {stats.get('cache_size_mb', 0):.1f} MB")


async def main():
    # Test 1: Performance in isolation
    print("=" * 60)
    print("TEST 1: Performance in isolation")
    print("=" * 60)
    gc.collect()
    fast1, safe1 = await run_performance_test("Isolated test")

    # Test 2: Performance after simulating previous test
    print("\n" + "=" * 60)
    print("TEST 2: Performance after memory pressure")
    print("=" * 60)
    await simulate_previous_test()
    gc.collect()  # Try to clean up
    fast2, safe2 = await run_performance_test("After memory pressure")

    # Analysis
    print("\n" + "=" * 60)
    print("ANALYSIS")
    print("=" * 60)
    print(f"Fast mode degradation: {fast2/fast1:.2f}x slower after memory pressure")
    print(f"Safe mode degradation: {safe2/safe1:.2f}x slower after memory pressure")

    if fast2 > safe2 * 1.5:
        print(f"\n⚠️  REPRODUCED THE BUG!")
        print(f"   Fast mode is {fast2/safe2:.2f}x slower than safe after memory pressure")
        print(f"   This explains why the test fails in the full suite!")


if __name__ == "__main__":
    asyncio.run(main())