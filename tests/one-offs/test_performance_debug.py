"""Debug performance regression in fast vs safe mode."""

import asyncio
import time
import pytest


class PerfNode:
    def __init__(self, path):
        self.path = path


class PerfTreeAdapter:
    """Large tree for performance testing."""
    def __init__(self, breadth=20, depth=3):
        self.breadth = breadth
        self.max_depth = depth
        self.call_count = 0

    async def get_children(self, node):
        self.call_count += 1
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


async def test_performance_comparison():
    """Test fast vs safe mode performance."""
    from dazzletreelib.aio.adapters.smart_caching import SmartCachingAdapter

    tree = PerfTreeAdapter(breadth=20, depth=3)  # 8420 nodes total

    # Test 1: Fast mode (unlimited memory, no safe mode)
    fast_adapter = SmartCachingAdapter(
        tree,
        max_memory_mb=0,  # Unlimited
        track_traversal=True,
        enable_safe_mode=False
    )

    root = PerfNode('/')

    # Time fast mode
    start = time.time()
    fast_count = 0
    async def traverse_fast(node):
        nonlocal fast_count
        async for child in fast_adapter.get_children(node):
            fast_count += 1
            await traverse_fast(child)

    await traverse_fast(root)
    fast_time = time.time() - start

    # Test 2: Safe mode (limited memory)
    tree2 = PerfTreeAdapter(breadth=20, depth=3)
    safe_adapter = SmartCachingAdapter(
        tree2,
        max_memory_mb=1,  # Limited memory
        track_traversal=True,
        enable_safe_mode=True
    )

    # Time safe mode
    start = time.time()
    safe_count = 0
    async def traverse_safe(node):
        nonlocal safe_count
        async for child in safe_adapter.get_children(node):
            safe_count += 1
            await traverse_safe(child)

    await traverse_safe(root)
    safe_time = time.time() - start

    # Test 3: No tracking at all
    tree3 = PerfTreeAdapter(breadth=20, depth=3)
    no_track_adapter = SmartCachingAdapter(
        tree3,
        max_memory_mb=0,  # Unlimited
        track_traversal=False,  # NO TRACKING
        enable_safe_mode=False
    )

    # Time no tracking mode
    start = time.time()
    no_track_count = 0
    async def traverse_no_track(node):
        nonlocal no_track_count
        async for child in no_track_adapter.get_children(node):
            no_track_count += 1
            await traverse_no_track(child)

    await traverse_no_track(root)
    no_track_time = time.time() - start

    print(f"\nPerformance Results:")
    print(f"=====================================")
    print(f"Nodes traversed: {fast_count} (all modes)")
    print(f"Fast mode (unlimited, tracking):    {fast_time:.3f}s")
    print(f"Safe mode (1MB limit, tracking):    {safe_time:.3f}s")
    print(f"No tracking mode (unlimited):       {no_track_time:.3f}s")
    print(f"")
    print(f"Fast vs Safe ratio: {fast_time/safe_time:.2f}x")
    print(f"Fast vs No-track ratio: {fast_time/no_track_time:.2f}x")
    print(f"")
    print(f"Adapter call counts:")
    print(f"Fast mode: {tree.call_count}")
    print(f"Safe mode: {tree2.call_count}")
    print(f"No track:  {tree3.call_count}")

    # The problem
    if fast_time > safe_time * 1.5:
        print(f"\n⚠️  PERFORMANCE ISSUE: Fast mode is {fast_time/safe_time:.2f}x slower than safe mode!")
        print(f"   This suggests tracking overhead is the problem, not cache management.")


if __name__ == "__main__":
    asyncio.run(test_performance_comparison())