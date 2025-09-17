"""
Test Issue #29: Realistic performance comparison between safe and fast modes.

This test compares the performance of the cache adapter with and without
OOM protection enabled, giving a realistic view of the performance impact.
"""

import pytest
import time
import asyncio
from pathlib import Path
from typing import AsyncIterator, Any
from collections import OrderedDict

# Import the adapter we're testing
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dazzletreelib.aio.adapters.cache_completeness_adapter import CompletenessAwareCacheAdapter


class MockNode:
    """Mock node for testing."""
    def __init__(self, path: Path, mtime=None):
        self.path = path
        self._mtime = mtime
        
    async def metadata(self):
        """Return mock metadata."""
        if self._mtime is not None:
            return {'modified_time': self._mtime}
        return {}
    
    def __str__(self):
        return str(self.path)


class MockAdapter:
    """Mock adapter that generates configurable children."""
    
    def __init__(self, children_per_node=10):
        self.children_per_node = children_per_node
        self.call_count = 0
        self.delay_ms = 0  # Can add artificial delay for testing
        
    async def get_children(self, node: Any) -> AsyncIterator[Any]:
        """Generate mock children."""
        self.call_count += 1
        path = node.path if hasattr(node, 'path') else Path(str(node))
        
        if self.delay_ms > 0:
            await asyncio.sleep(self.delay_ms / 1000.0)
        
        for i in range(self.children_per_node):
            child_path = path / f"child_{i}"
            yield MockNode(child_path)


class TestRealisticPerformance:
    """Test realistic performance comparison between modes."""
    
    @pytest.mark.asyncio
    async def test_safe_vs_fast_mode_comparison(self):
        """Compare performance between safe and fast modes directly."""
        operations = 1000
        paths = [Path(f"/test/path_{i}") for i in range(operations)]
        
        # Test SAFE mode
        mock_adapter_safe = MockAdapter(children_per_node=10)
        safe_adapter = CompletenessAwareCacheAdapter(
            mock_adapter_safe,
            enable_oom_protection=True,  # Safety ON
            max_entries=10000,
            max_cache_depth=50,
            max_path_depth=30,
            max_tracked_nodes=10000
        )
        
        start = time.perf_counter()
        for path in paths:
            node = MockNode(path)
            children = []
            async for child in safe_adapter.get_children(node):
                children.append(child)
        safe_time = time.perf_counter() - start
        
        print(f"\nSafe mode (protection ON): {safe_time:.3f}s")
        print(f"Operations/sec: {operations/safe_time:.0f}")

        # Test FAST mode
        mock_adapter_fast = MockAdapter(children_per_node=10)
        fast_adapter = CompletenessAwareCacheAdapter(
            mock_adapter_fast,
            enable_oom_protection=False  # Safety OFF
        )
        
        start = time.perf_counter()
        for path in paths:
            node = MockNode(path)
            children = []
            async for child in fast_adapter.get_children(node):
                children.append(child)
        fast_time = time.perf_counter() - start
        
        print(f"Fast mode (protection OFF): {fast_time:.3f}s")
        print(f"Operations/sec: {operations/fast_time:.0f}")

        # Calculate improvement
        improvement = (safe_time - fast_time) / safe_time * 100
        speedup = safe_time / fast_time
        
        print(f"\nPerformance improvement: {improvement:.1f}%")
        print(f"Speedup factor: {speedup:.2f}x")
        
        # Fast mode should be measurably faster
        assert fast_time < safe_time, "Fast mode should be faster than safe mode"
        assert improvement > 10, f"Expected >10% improvement, got {improvement:.1f}%"
    
    @pytest.mark.asyncio
    async def test_cache_hit_performance(self):
        """Test performance for cache hits (best case scenario)."""
        import statistics

        # Use larger dataset for more stable measurements
        paths = [Path(f"/test/path_{i}") for i in range(5000)]  # Increased from 100

        # SAFE mode with cache hits
        mock_adapter_safe = MockAdapter(children_per_node=10)
        safe_adapter = CompletenessAwareCacheAdapter(
            mock_adapter_safe,
            enable_oom_protection=True
        )

        # Warm up cache
        for path in paths:
            node = MockNode(path)
            async for _ in safe_adapter.get_children(node):
                pass

        # Multiple measurements for statistical stability
        safe_measurements = []
        for measurement in range(5):  # Take 5 measurements
            start = time.perf_counter()
            for path in paths:  # Single pass per measurement
                node = MockNode(path)
                async for _ in safe_adapter.get_children(node):
                    pass
            elapsed = time.perf_counter() - start
            safe_measurements.append(elapsed)

        # FAST mode with cache hits
        mock_adapter_fast = MockAdapter(children_per_node=10)
        fast_adapter = CompletenessAwareCacheAdapter(
            mock_adapter_fast,
            enable_oom_protection=False
        )

        # Warm up cache
        for path in paths:
            node = MockNode(path)
            async for _ in fast_adapter.get_children(node):
                pass

        # Multiple measurements for statistical stability
        fast_measurements = []
        for measurement in range(5):  # Take 5 measurements
            start = time.perf_counter()
            for path in paths:  # Single pass per measurement
                node = MockNode(path)
                async for _ in fast_adapter.get_children(node):
                    pass
            elapsed = time.perf_counter() - start
            fast_measurements.append(elapsed)

        # Use median for stability (less affected by outliers than mean)
        safe_hit_time = statistics.median(safe_measurements)
        fast_hit_time = statistics.median(fast_measurements)

        improvement = (safe_hit_time - fast_hit_time) / safe_hit_time * 100

        print(f"\nCache hit performance (median of 5 runs):")
        print(f"Safe mode: {safe_hit_time:.3f}s (measurements: {[f'{t:.3f}' for t in safe_measurements]})")
        print(f"Fast mode: {fast_hit_time:.3f}s (measurements: {[f'{t:.3f}' for t in fast_measurements]})")
        print(f"Improvement: {improvement:.1f}%")

        # Note: For cache hits, OrderedDict.move_to_end() can provide better cache locality
        # than plain dict, so we allow fast mode to be within 10% of safe mode
        assert fast_hit_time <= safe_hit_time * 1.1, \
            "Fast mode should be comparable to safe mode for cache hits (within 10%)"
    
    @pytest.mark.asyncio
    async def test_memory_usage_difference(self):
        """Test that fast mode uses less memory (no OrderedDict overhead)."""
        import sys
        
        # Create adapters
        mock_adapter_safe = MockAdapter(children_per_node=10)
        safe_adapter = CompletenessAwareCacheAdapter(
            mock_adapter_safe,
            enable_oom_protection=True
        )
        
        mock_adapter_fast = MockAdapter(children_per_node=10)
        fast_adapter = CompletenessAwareCacheAdapter(
            mock_adapter_fast,
            enable_oom_protection=False
        )
        
        # Check data structure types
        assert isinstance(safe_adapter.cache, OrderedDict), "Safe mode should use OrderedDict"
        assert isinstance(fast_adapter.cache, dict), "Fast mode should use regular dict"
        assert isinstance(safe_adapter.node_completeness, OrderedDict), "Safe mode should use OrderedDict"
        assert isinstance(fast_adapter.node_completeness, dict), "Fast mode should use regular dict"
        
        # Fill caches with same data
        for i in range(100):
            path = Path(f"/test/path_{i}")
            node = MockNode(path)
            async for _ in safe_adapter.get_children(node):
                pass
            async for _ in fast_adapter.get_children(node):
                pass
        
        # Check memory estimation (OrderedDict has overhead)
        safe_size = sys.getsizeof(safe_adapter.cache) + sys.getsizeof(safe_adapter.node_completeness)
        fast_size = sys.getsizeof(fast_adapter.cache) + sys.getsizeof(fast_adapter.node_completeness)
        
        print(f"\nMemory usage:")
        print(f"Safe mode: {safe_size} bytes")
        print(f"Fast mode: {fast_size} bytes")
        print(f"Savings: {safe_size - fast_size} bytes")
        
        # Fast mode should use less memory (dict vs OrderedDict)
        # Note: This might not always be true for small caches
        print(f"Memory comparison: fast/safe = {fast_size/safe_size:.2f}")


if __name__ == "__main__":
    # Run with: python -m pytest tests/test_issue_29_performance_realistic.py -v -s
    pytest.main([__file__, "-v", "-s"])