#!/usr/bin/env python
"""
Test performance with cooldown periods between tests.

This script runs performance-sensitive tests with deliberate pauses
and garbage collection between runs to ensure accurate measurements.
"""

import asyncio
import gc
import time
import sys
import os
from pathlib import Path

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dazzletreelib.aio.adapters.smart_caching import (
    SmartCachingAdapter,
    create_unlimited_cache_adapter,
)


class TestNode:
    """Simple test node."""
    def __init__(self, path):
        self.path = path

    def __str__(self):
        return str(self.path)


class LargeTreeAdapter:
    """Adapter that generates a large tree for testing."""

    def __init__(self, breadth=10, depth=5):
        self.breadth = breadth
        self.max_depth = depth

    async def get_children(self, node):
        """Generate children based on path depth."""
        path = str(node.path) if hasattr(node, 'path') else str(node)
        current_depth = 0 if path == '/' else path.count('/')

        if current_depth < self.max_depth:
            for i in range(self.breadth):
                child_path = f"{path}/node_{current_depth}_{i}" if path != '/' else f"/node_0_{i}"
                yield TestNode(child_path)

    async def get_depth(self, node):
        """Calculate depth from path."""
        path = str(node.path) if hasattr(node, 'path') else str(node)
        return 0 if path == '/' else path.count('/')

    async def get_parent(self, node):
        """Return parent node."""
        return None


def cleanup_memory():
    """Aggressive memory cleanup."""
    print("  Cleaning up memory...")
    gc.collect()
    gc.collect()
    gc.collect()
    # Give OS time to reclaim memory
    time.sleep(0.5)


async def warmup_test():
    """Warm up the system with a small test."""
    print("\n1. WARMUP TEST")
    print("-" * 40)
    tree = LargeTreeAdapter(breadth=5, depth=2)
    adapter = SmartCachingAdapter(tree, max_memory_mb=10, enable_safe_mode=False)

    root = TestNode('/')
    count = 0
    async for child in adapter.get_children(root):
        count += 1
        async for grandchild in adapter.get_children(child):
            count += 1

    print(f"  Warmed up with {count} nodes")


async def large_tree_test():
    """Create a large tree like the problematic test."""
    print("\n2. LARGE TREE TEST (simulating test_fast_mode_unlimited_tracking)")
    print("-" * 40)

    tree = LargeTreeAdapter(breadth=50, depth=3)  # ~2500 nodes
    adapter = create_unlimited_cache_adapter(tree)
    adapter.track_traversal = True

    root = TestNode('/')
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
    print(f"  Created {discovered_count} nodes in {elapsed:.2f}s")
    print(f"  Stats: {stats['discovered_nodes']} discovered")


async def performance_test_with_cooldown(cooldown_seconds=2):
    """Run the performance test with optional cooldown."""
    print(f"\n3. PERFORMANCE TEST (with {cooldown_seconds}s cooldown)")
    print("-" * 40)

    if cooldown_seconds > 0:
        print(f"  Cooling down for {cooldown_seconds} seconds...")
        time.sleep(cooldown_seconds)

    cleanup_memory()

    tree = LargeTreeAdapter(breadth=20, depth=3)  # Medium-sized tree

    # Fast mode
    print("  Testing FAST mode...")
    fast_adapter = SmartCachingAdapter(
        tree,
        max_memory_mb=0,  # Unlimited
        track_traversal=True,
        enable_safe_mode=False
    )

    root = TestNode('/')

    # Time fast mode
    start = time.time()
    async def traverse_fast(node):
        async for child in fast_adapter.get_children(node):
            await traverse_fast(child)

    await traverse_fast(root)
    fast_time = time.time() - start

    # Cleanup between tests
    cleanup_memory()

    # Safe mode
    print("  Testing SAFE mode...")
    safe_adapter = SmartCachingAdapter(
        tree,
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

    # Results
    print(f"\n  Results:")
    print(f"    Fast mode: {fast_time:.3f}s")
    print(f"    Safe mode: {safe_time:.3f}s")
    print(f"    Ratio: {safe_time/fast_time:.2f}x")

    if fast_time < safe_time:
        print("    [PASS] Fast mode is faster!")
    else:
        print(f"    [FAIL] Fast mode is {fast_time/safe_time:.2f}x slower!")

    return fast_time, safe_time


async def main():
    """Run various test scenarios."""
    print("=" * 60)
    print("PERFORMANCE TEST WITH COOLDOWN PERIODS")
    print("=" * 60)

    # Scenario 1: Clean state (baseline)
    print("\n" + "=" * 60)
    print("SCENARIO 1: Clean state (baseline)")
    print("=" * 60)
    cleanup_memory()
    await warmup_test()
    fast1, safe1 = await performance_test_with_cooldown(cooldown_seconds=0)

    # Scenario 2: After large tree test (no cooldown)
    print("\n" + "=" * 60)
    print("SCENARIO 2: After large tree (no cooldown)")
    print("=" * 60)
    await large_tree_test()
    fast2, safe2 = await performance_test_with_cooldown(cooldown_seconds=0)

    # Scenario 3: After large tree test (with 2s cooldown)
    print("\n" + "=" * 60)
    print("SCENARIO 3: After large tree (2s cooldown)")
    print("=" * 60)
    await large_tree_test()
    fast3, safe3 = await performance_test_with_cooldown(cooldown_seconds=2)

    # Scenario 4: After large tree test (with 5s cooldown)
    print("\n" + "=" * 60)
    print("SCENARIO 4: After large tree (5s cooldown)")
    print("=" * 60)
    await large_tree_test()
    fast4, safe4 = await performance_test_with_cooldown(cooldown_seconds=5)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Scenario 1 (clean):        Fast={fast1:.3f}s, Safe={safe1:.3f}s, Ratio={safe1/fast1:.2f}x")
    print(f"Scenario 2 (no cooldown):  Fast={fast2:.3f}s, Safe={safe2:.3f}s, Ratio={safe2/fast2:.2f}x")
    print(f"Scenario 3 (2s cooldown):  Fast={fast3:.3f}s, Safe={safe3:.3f}s, Ratio={safe3/fast3:.2f}x")
    print(f"Scenario 4 (5s cooldown):  Fast={fast4:.3f}s, Safe={safe4:.3f}s, Ratio={safe4/fast4:.2f}x")

    print("\nConclusions:")
    if fast1 < safe1:
        print("[OK] Clean state: Fast mode works correctly")
    else:
        print("[PROBLEM] Clean state: Fast mode is slower even in clean state!")

    degradation2 = (fast2 / safe2) / (fast1 / safe1) if fast1 < safe1 else 0
    if degradation2 > 1.5:
        print(f"[WARNING] No cooldown: {degradation2:.1f}x performance degradation")

    if fast3 < safe3 and fast2 >= safe2:
        print("[OK] 2s cooldown helps recover performance")

    if fast4 < safe4 and fast3 >= safe3:
        print("[OK] 5s cooldown helps recover performance")


if __name__ == "__main__":
    asyncio.run(main())