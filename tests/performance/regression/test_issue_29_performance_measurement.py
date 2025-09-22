"""
Test Issue #29: Precise performance measurement for optional OOM protection.

This test provides exact measurements showing the performance difference
between safe mode (with OOM protection) and fast mode (without protection).
"""

import pytest
import time
import asyncio
from pathlib import Path
from typing import AsyncIterator, Any
import statistics

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
        
    async def get_children(self, node: Any) -> AsyncIterator[Any]:
        """Generate mock children."""
        self.call_count += 1
        path = node.path if hasattr(node, 'path') else Path(str(node))
        
        for i in range(self.children_per_node):
            child_path = path / f"child_{i}"
            yield MockNode(child_path)


class TestPerformanceMeasurement:
    """Measure exact performance impact of OOM protection."""
    
    @pytest.mark.asyncio
    async def test_performance_impact_measurement(self):
        """Measure the exact performance impact of OOM protection."""
        print("\n" + "="*70)
        print("ISSUE #29: PERFORMANCE IMPACT MEASUREMENT")
        print("="*70)
        
        # Test parameters
        operations = 1000
        runs = 5  # Multiple runs for stable measurements
        
        # Measure safe mode performance
        safe_times = []
        for run in range(runs):
            mock_adapter = MockAdapter(children_per_node=10)
            safe_adapter = CompletenessAwareCacheAdapter(
                mock_adapter,
                enable_oom_protection=True,  # Safety ON
                max_entries=10000,
                max_cache_depth=50
            )
            
            paths = [Path(f"/test/path_{i}") for i in range(operations)]
            
            start = time.perf_counter()
            for path in paths:
                node = MockNode(path)
                children = []
                async for child in safe_adapter.get_children(node):
                    children.append(child)
            safe_time = time.perf_counter() - start
            safe_times.append(safe_time)
        
        avg_safe_time = statistics.mean(safe_times)
        std_safe_time = statistics.stdev(safe_times) if len(safe_times) > 1 else 0
        
        # Measure fast mode performance  
        fast_times = []
        for run in range(runs):
            mock_adapter = MockAdapter(children_per_node=10)
            fast_adapter = CompletenessAwareCacheAdapter(
                mock_adapter,
                enable_oom_protection=False  # Safety OFF
            )
            
            paths = [Path(f"/test/path_{i}") for i in range(operations)]
            
            start = time.perf_counter()
            for path in paths:
                node = MockNode(path)
                children = []
                async for child in fast_adapter.get_children(node):
                    children.append(child)
            fast_time = time.perf_counter() - start
            fast_times.append(fast_time)
        
        avg_fast_time = statistics.mean(fast_times)
        std_fast_time = statistics.stdev(fast_times) if len(fast_times) > 1 else 0
        
        # Calculate performance improvement
        improvement = (avg_safe_time - avg_fast_time) / avg_safe_time * 100
        speedup = avg_safe_time / avg_fast_time
        
        # Print detailed results
        print(f"\nTest Configuration:")
        print(f"  Operations: {operations}")
        print(f"  Runs per mode: {runs}")
        print(f"  Children per node: 10")
        
        print(f"\nSafe Mode (OOM Protection ENABLED):")
        print(f"  Average time: {avg_safe_time:.3f}s ± {std_safe_time:.3f}s")
        print(f"  Operations/sec: {operations/avg_safe_time:.0f}")
        print(f"  Individual runs: {[f'{t:.3f}s' for t in safe_times]}")
        
        print(f"\nFast Mode (OOM Protection DISABLED):")
        print(f"  Average time: {avg_fast_time:.3f}s ± {std_fast_time:.3f}s")
        print(f"  Operations/sec: {operations/avg_fast_time:.0f}")
        print(f"  Individual runs: {[f'{t:.3f}s' for t in fast_times]}")
        
        print(f"\nPerformance Impact:")
        print(f"  Improvement: {improvement:.1f}%")
        print(f"  Speedup factor: {speedup:.2f}x")
        print(f"  Time saved per 1000 ops: {(avg_safe_time - avg_fast_time):.3f}s")
        
        print("\n" + "="*70)
        
        # Assert that fast mode is actually faster
        assert avg_fast_time < avg_safe_time, "Fast mode should be faster than safe mode"
        
        # We expect at least 5% improvement (conservative)
        assert improvement > 5, f"Expected >5% improvement, got {improvement:.1f}%"
        
        return improvement, speedup
    
    @pytest.mark.asyncio
    async def test_cache_hit_performance_impact(self):
        """Measure performance difference for cache hits specifically."""
        print("\n" + "="*70)
        print("CACHE HIT PERFORMANCE IMPACT")
        print("="*70)
        
        mock_adapter = MockAdapter(children_per_node=10)
        paths = [Path(f"/test/path_{i}") for i in range(100)]
        
        # Test safe mode cache hits
        safe_adapter = CompletenessAwareCacheAdapter(
            mock_adapter,
            enable_oom_protection=True
        )
        
        # Warm up cache
        for path in paths:
            node = MockNode(path)
            async for _ in safe_adapter.get_children(node):
                pass
        
        # Measure cache hits
        runs = 10
        start = time.perf_counter()
        for _ in range(runs):
            for path in paths:
                node = MockNode(path)
                async for _ in safe_adapter.get_children(node):
                    pass
        safe_hit_time = time.perf_counter() - start
        
        # Test fast mode cache hits
        mock_adapter.call_count = 0
        fast_adapter = CompletenessAwareCacheAdapter(
            mock_adapter,
            enable_oom_protection=False
        )
        
        # Warm up cache
        for path in paths:
            node = MockNode(path)
            async for _ in fast_adapter.get_children(node):
                pass
        
        # Measure cache hits
        start = time.perf_counter()
        for _ in range(runs):
            for path in paths:
                node = MockNode(path)
                async for _ in fast_adapter.get_children(node):
                    pass
        fast_hit_time = time.perf_counter() - start
        
        improvement = (safe_hit_time - fast_hit_time) / safe_hit_time * 100
        
        print(f"\nCache Hit Performance (100 paths × {runs} runs):")
        print(f"  Safe mode: {safe_hit_time:.3f}s")
        print(f"  Fast mode: {fast_hit_time:.3f}s")
        print(f"  Improvement: {improvement:.1f}%")
        print(f"  Speedup: {safe_hit_time/fast_hit_time:.2f}x")
        
        print("\n" + "="*70)
        
        # Note: For cache hits, OrderedDict.move_to_end() can provide better cache locality
        # than plain dict, so we allow fast mode to be within 10% of safe mode
        assert fast_hit_time <= safe_hit_time * 1.1, \
            f"Fast mode cache hits should be comparable to safe mode (within 10%)"
        
        return improvement


if __name__ == "__main__":
    # Run with: python -m pytest tests/test_issue_29_performance_measurement.py -v -s
    pytest.main([__file__, "-v", "-s"])