#!/usr/bin/env python
"""
Diagnostic script to check for state contamination as suggested by Gemini.
Focuses on cache state and unbounded growth in fast mode.
"""

import asyncio
import time
import gc
import sys
from pathlib import Path

# Add the project to path
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


async def run_test_with_cache_inspection():
    """Run test while inspecting cache state."""
    print("=" * 80)
    print("CACHE STATE INSPECTION TEST")
    print("=" * 80)

    # Create paths for testing
    operations = 1000
    paths = [Path(f"/test/path_{i}") for i in range(operations)]

    # Test 1: Fresh adapters each time
    print("\n--- Test 1: Fresh Adapters Each Iteration ---")
    for iteration in range(3):
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

        print(f"\nIteration {iteration + 1}:")
        print(f"  Safe cache ID: {id(safe_adapter.cache)}, Size: {len(safe_adapter.cache)}")
        print(f"  Fast cache ID: {id(fast_adapter.cache)}, Size: {len(fast_adapter.cache)}")

        # Run operations
        start = time.perf_counter()
        for path in paths:
            node = MockNode(path)
            async for _ in safe_adapter.get_children(node):
                pass
        safe_time = time.perf_counter() - start

        start = time.perf_counter()
        for path in paths:
            node = MockNode(path)
            async for _ in fast_adapter.get_children(node):
                pass
        fast_time = time.perf_counter() - start

        print(f"  Safe time: {safe_time:.3f}s, Final cache size: {len(safe_adapter.cache)}")
        print(f"  Fast time: {fast_time:.3f}s, Final cache size: {len(fast_adapter.cache)}")
        print(f"  Performance: {'PASS' if fast_time < safe_time else 'FAIL'} "
              f"({(safe_time - fast_time) / safe_time * 100:.1f}% improvement)")

    # Test 2: Reused adapters (simulate potential state leak)
    print("\n--- Test 2: Reused Adapters (Simulating State Leak) ---")

    # Create adapters once
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

    for iteration in range(3):
        print(f"\nIteration {iteration + 1}:")
        print(f"  Safe cache ID: {id(safe_adapter.cache)}, Size before: {len(safe_adapter.cache)}")
        print(f"  Fast cache ID: {id(fast_adapter.cache)}, Size before: {len(fast_adapter.cache)}")

        # Run operations
        start = time.perf_counter()
        for path in paths:
            node = MockNode(path)
            async for _ in safe_adapter.get_children(node):
                pass
        safe_time = time.perf_counter() - start

        start = time.perf_counter()
        for path in paths:
            node = MockNode(path)
            async for _ in fast_adapter.get_children(node):
                pass
        fast_time = time.perf_counter() - start

        print(f"  Safe time: {safe_time:.3f}s, Final cache size: {len(safe_adapter.cache)}")
        print(f"  Fast time: {fast_time:.3f}s, Final cache size: {len(fast_adapter.cache)}")
        print(f"  Performance: {'PASS' if fast_time < safe_time else 'FAIL'} "
              f"({(safe_time - fast_time) / safe_time * 100:.1f}% improvement)")


async def test_gc_impact():
    """Test impact of garbage collection."""
    print("\n" + "=" * 80)
    print("GARBAGE COLLECTION IMPACT TEST")
    print("=" * 80)

    operations = 1000
    paths = [Path(f"/test/path_{i}") for i in range(operations)]

    print("\n--- With GC Enabled (Normal) ---")
    for i in range(3):
        mock_fast = MockAdapter(children_per_node=10)
        fast_adapter = CompletenessAwareCacheAdapter(
            mock_fast,
            enable_oom_protection=False
        )

        gc.collect()  # Force collection before timing
        start = time.perf_counter()
        for path in paths:
            node = MockNode(path)
            async for _ in fast_adapter.get_children(node):
                pass
        elapsed = time.perf_counter() - start
        print(f"  Iteration {i+1}: {elapsed:.3f}s")

    print("\n--- With GC Disabled ---")
    gc.disable()
    try:
        for i in range(3):
            mock_fast = MockAdapter(children_per_node=10)
            fast_adapter = CompletenessAwareCacheAdapter(
                mock_fast,
                enable_oom_protection=False
            )

            start = time.perf_counter()
            for path in paths:
                node = MockNode(path)
                async for _ in fast_adapter.get_children(node):
                    pass
            elapsed = time.perf_counter() - start
            print(f"  Iteration {i+1}: {elapsed:.3f}s")
    finally:
        gc.enable()


async def test_event_loop_isolation():
    """Test with isolated event loops as Gemini suggested."""
    print("\n" + "=" * 80)
    print("EVENT LOOP ISOLATION TEST")
    print("=" * 80)

    operations = 1000
    paths = [Path(f"/test/path_{i}") for i in range(operations)]

    async def run_operations(adapter, paths):
        for path in paths:
            node = MockNode(path)
            async for _ in adapter.get_children(node):
                pass

    print("\n--- Using asyncio.run() for Each Test ---")
    for i in range(3):
        # Safe mode
        mock_safe = MockAdapter(children_per_node=10)
        safe_adapter = CompletenessAwareCacheAdapter(
            mock_safe,
            enable_oom_protection=True,
            max_entries=10000
        )

        start = time.perf_counter()
        await run_operations(safe_adapter, paths)  # Run in current loop
        safe_time = time.perf_counter() - start

        # Fast mode
        mock_fast = MockAdapter(children_per_node=10)
        fast_adapter = CompletenessAwareCacheAdapter(
            mock_fast,
            enable_oom_protection=False
        )

        start = time.perf_counter()
        await run_operations(fast_adapter, paths)  # Run in current loop
        fast_time = time.perf_counter() - start

        improvement = (safe_time - fast_time) / safe_time * 100
        print(f"  Iteration {i+1}: Safe={safe_time:.3f}s, Fast={fast_time:.3f}s, "
              f"Improvement={improvement:.1f}% {'PASS' if improvement > 0 else 'FAIL'}")


def main():
    """Run all diagnostic tests."""
    print("Starting State Contamination Diagnostics...")
    print(f"Python {sys.version}")
    print(f"Platform: {sys.platform}")

    # Run tests
    asyncio.run(run_test_with_cache_inspection())
    asyncio.run(test_gc_impact())
    asyncio.run(test_event_loop_isolation())

    # Windows-specific test
    if sys.platform == "win32":
        print("\n" + "=" * 80)
        print("WINDOWS EVENT LOOP POLICY TEST")
        print("=" * 80)

        print("\n--- Using SelectorEventLoop ---")
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(test_event_loop_isolation())


if __name__ == "__main__":
    main()