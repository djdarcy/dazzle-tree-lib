#!/usr/bin/env python
"""
Diagnostic to check if measurements are getting swapped somehow.
The 87% improvement vs 87% degradation is too suspicious to be coincidence.
"""

import asyncio
import time
import sys
from pathlib import Path

sys.path.insert(0, ".")

from dazzletreelib.aio.adapters.cache_completeness_adapter import CompletenessAwareCacheAdapter


class MockNode:
    """Mock node for testing."""
    def __init__(self, path):
        self.path = path


class TrackedMockAdapter:
    """Mock adapter that tracks which instance is being called."""
    def __init__(self, name, children_per_node=10):
        self.name = name
        self.children_per_node = children_per_node
        self.call_count = 0

    async def get_children(self, node):
        """Generate mock children."""
        self.call_count += 1
        path = node.path if hasattr(node, 'path') else Path(str(node))
        for i in range(self.children_per_node):
            child_path = path / f"child_{i}"
            yield MockNode(child_path)


async def run_tracked_test():
    """Run test with tracking to ensure correct adapters are being called."""
    print("=" * 80)
    print("MEASUREMENT SWAP DETECTION TEST")
    print("=" * 80)

    operations = 1000
    paths = [Path(f"/test/path_{i}") for i in range(operations)]

    for iteration in range(10):
        print(f"\n--- Iteration {iteration + 1}/10 ---")

        # Create tracked adapters
        mock_safe = TrackedMockAdapter("SAFE", children_per_node=10)
        safe_adapter = CompletenessAwareCacheAdapter(
            mock_safe,
            enable_oom_protection=True,
            max_entries=10000
        )

        mock_fast = TrackedMockAdapter("FAST", children_per_node=10)
        fast_adapter = CompletenessAwareCacheAdapter(
            mock_fast,
            enable_oom_protection=False
        )

        # Verify configuration
        print(f"Safe adapter: enable_oom_protection={safe_adapter.enable_oom_protection}")
        print(f"Fast adapter: enable_oom_protection={fast_adapter.enable_oom_protection}")

        # Run safe mode
        safe_start = time.perf_counter()
        for path in paths:
            node = MockNode(path)
            children = []
            async for child in safe_adapter.get_children(node):
                children.append(child)
        safe_time = time.perf_counter() - safe_start

        # Run fast mode
        fast_start = time.perf_counter()
        for path in paths:
            node = MockNode(path)
            children = []
            async for child in fast_adapter.get_children(node):
                children.append(child)
        fast_time = time.perf_counter() - fast_start

        # Verify correct adapters were called
        print(f"Safe adapter '{mock_safe.name}' called {mock_safe.call_count} times")
        print(f"Fast adapter '{mock_fast.name}' called {mock_fast.call_count} times")

        # Check for impossible conditions
        if mock_safe.call_count != operations:
            print("ERROR: Safe adapter call count mismatch!")
        if mock_fast.call_count != operations:
            print("ERROR: Fast adapter call count mismatch!")

        # Calculate and verify improvement
        improvement = (safe_time - fast_time) / safe_time * 100
        print(f"Times: Safe={safe_time:.3f}s, Fast={fast_time:.3f}s")
        print(f"Improvement: {improvement:.1f}%")

        # Check for the suspicious pattern
        if improvement < -80 and improvement > -90:
            print("SUSPICIOUS: Fast mode is ~87% slower - possible measurement swap!")
            print(f"Cache types: Safe={type(safe_adapter.cache).__name__}, "
                  f"Fast={type(fast_adapter.cache).__name__}")

        # Additional sanity checks
        if safe_adapter.enable_oom_protection is False:
            print("ERROR: Safe adapter has protection OFF!")
        if fast_adapter.enable_oom_protection is True:
            print("ERROR: Fast adapter has protection ON!")


async def test_actual_performance():
    """Test the actual performance characteristics of dict vs OrderedDict."""
    print("\n" + "=" * 80)
    print("DICT VS ORDEREDDICT PERFORMANCE TEST")
    print("=" * 80)

    from collections import OrderedDict

    # Test with different sizes
    sizes = [100, 1000, 10000]

    for size in sizes:
        print(f"\nTesting with {size} items:")

        # Create and populate dicts
        regular_dict = {}
        ordered_dict = OrderedDict()

        for i in range(size):
            key = f"key_{i}"
            regular_dict[key] = i
            ordered_dict[key] = i

        # Test lookup performance
        test_key = "key_50"  # Middle key
        iterations = 100000

        # Regular dict
        start = time.perf_counter()
        for _ in range(iterations):
            _ = regular_dict[test_key]
        dict_time = time.perf_counter() - start

        # OrderedDict
        start = time.perf_counter()
        for _ in range(iterations):
            _ = ordered_dict[test_key]
        ordered_time = time.perf_counter() - start

        print(f"  Dict lookup: {dict_time:.4f}s")
        print(f"  OrderedDict lookup: {ordered_time:.4f}s")
        print(f"  Dict is {(ordered_time - dict_time) / ordered_time * 100:.1f}% faster")

        # Test with move_to_end (OrderedDict only)
        start = time.perf_counter()
        for _ in range(iterations // 10):  # Fewer iterations for this
            _ = ordered_dict[test_key]
            ordered_dict.move_to_end(test_key)
        ordered_lru_time = time.perf_counter() - start

        print(f"  OrderedDict with LRU: {ordered_lru_time:.4f}s")


async def test_async_overhead():
    """Test if async iteration adds overhead."""
    print("\n" + "=" * 80)
    print("ASYNC ITERATION OVERHEAD TEST")
    print("=" * 80)

    test_list = list(range(10))
    iterations = 100000

    async def yield_items():
        for item in test_list:
            yield item

    # Time async iteration
    start = time.perf_counter()
    for _ in range(iterations):
        items = []
        async for item in yield_items():
            items.append(item)
    async_time = time.perf_counter() - start

    print(f"Async iteration: {async_time:.4f}s")
    print(f"Per iteration: {async_time / iterations * 1000000:.2f} microseconds")


def main():
    """Run all diagnostics."""
    print("Measurement Swap Diagnostic Tool")
    print(f"Python {sys.version}")
    print(f"Platform: {sys.platform}\n")

    asyncio.run(run_tracked_test())
    asyncio.run(test_actual_performance())
    asyncio.run(test_async_overhead())

    print("\n" + "=" * 80)
    print("CONCLUSION")
    print("=" * 80)
    print("\nIf you see 'SUSPICIOUS' messages above, the measurements might be getting swapped.")
    print("This could happen if:")
    print("1. The adapter configuration is changing between creation and use")
    print("2. There's a race condition in the test")
    print("3. The Python interpreter is optimizing/deoptimizing code")
    print("4. The test harness is interfering with measurements")


if __name__ == "__main__":
    main()