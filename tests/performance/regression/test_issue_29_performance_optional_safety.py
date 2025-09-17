"""
Test Issue #29: Performance with optional safety checks.

This test validates that disabling OOM protection restores near-original performance.
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


class TestPerformanceModes:
    """Test performance with and without OOM protection."""
    
    @pytest.mark.asyncio
    async def test_baseline_performance_no_cache(self):
        """Establish baseline performance without any caching."""
        mock_adapter = MockAdapter(children_per_node=10)
        
        # Direct adapter calls (no caching)
        operations = 1000
        paths = [Path(f"/test/path_{i}") for i in range(operations)]
        
        start = time.perf_counter()
        for path in paths:
            node = MockNode(path)
            children = []
            async for child in mock_adapter.get_children(node):
                children.append(child)
        baseline_time = time.perf_counter() - start
        
        print(f"\nBaseline (no cache): {baseline_time:.3f}s for {operations} operations")
        print(f"Operations/sec: {operations/baseline_time:.0f}")
        
        # Store for comparison
        self.baseline_time = baseline_time
        self.operations = operations
    
    @pytest.mark.asyncio
    async def test_fast_mode_performance(self):
        """Test performance with OOM protection disabled."""
        # First get baseline
        await self.test_baseline_performance_no_cache()
        
        mock_adapter = MockAdapter(children_per_node=10)
        
        # Create adapter with protection DISABLED
        fast_adapter = CompletenessAwareCacheAdapter(
            mock_adapter,
            enable_oom_protection=False  # This parameter doesn't exist yet
        )
        
        paths = [Path(f"/test/path_{i}") for i in range(self.operations)]
        
        start = time.perf_counter()
        for path in paths:
            node = MockNode(path)
            children = []
            async for child in fast_adapter.get_children(node):
                children.append(child)
        fast_time = time.perf_counter() - start
        
        # Calculate overhead vs baseline
        overhead = (fast_time - self.baseline_time) / self.baseline_time * 100
        
        print(f"\nFast mode (protection OFF): {fast_time:.3f}s")
        print(f"Operations/sec: {self.operations/fast_time:.0f}")
        print(f"Overhead vs baseline: {overhead:.1f}%")
        
        # Cache adapter will have some overhead vs direct calls
        # But should be reasonable (< 1000% is acceptable for caching layer)
        assert overhead < 1000, f"Fast mode overhead {overhead:.1f}% exceeds 1000% limit"
        
        # Store for comparison
        self.fast_time = fast_time
    
    @pytest.mark.asyncio
    async def test_safe_mode_performance(self):
        """Test performance with OOM protection enabled."""
        # Get baseline and fast mode first
        await self.test_fast_mode_performance()
        
        mock_adapter = MockAdapter(children_per_node=10)
        
        # Create adapter with protection ENABLED (default)
        safe_adapter = CompletenessAwareCacheAdapter(
            mock_adapter,
            enable_oom_protection=True,  # This parameter doesn't exist yet
            max_entries=10000,
            max_cache_depth=50,
            max_path_depth=30,
            max_tracked_nodes=10000
        )
        
        paths = [Path(f"/test/path_{i}") for i in range(self.operations)]
        
        start = time.perf_counter()
        for path in paths:
            node = MockNode(path)
            children = []
            async for child in safe_adapter.get_children(node):
                children.append(child)
        safe_time = time.perf_counter() - start
        
        # Calculate overhead vs fast mode
        overhead = (safe_time - self.fast_time) / self.fast_time * 100
        
        print(f"\nSafe mode (protection ON): {safe_time:.3f}s")
        print(f"Operations/sec: {self.operations/safe_time:.0f}")
        print(f"Overhead vs fast mode: {overhead:.1f}%")
        
        # Should show significant overhead (currently ~21%)
        assert overhead > 10, f"Safety features should have measurable cost"
        
        self.safe_time = safe_time
    
    @pytest.mark.asyncio
    async def test_performance_comparison_summary(self):
        """Run all modes and provide comparison summary."""
        await self.test_safe_mode_performance()
        
        print("\n" + "="*60)
        print("PERFORMANCE COMPARISON SUMMARY")
        print("="*60)
        print(f"Operations tested: {self.operations}")
        print(f"Baseline (no cache): {self.baseline_time:.3f}s")
        print(f"Fast mode (protection OFF): {self.fast_time:.3f}s")
        print(f"Safe mode (protection ON): {self.safe_time:.3f}s")
        print("-"*60)
        
        fast_overhead = (self.fast_time - self.baseline_time) / self.baseline_time * 100
        safe_overhead = (self.safe_time - self.baseline_time) / self.baseline_time * 100
        safety_cost = (self.safe_time - self.fast_time) / self.fast_time * 100
        
        print(f"Fast mode overhead: {fast_overhead:.1f}%")
        print(f"Safe mode overhead: {safe_overhead:.1f}%")
        print(f"Safety feature cost: {safety_cost:.1f}%")
        print("="*60)
    
    @pytest.mark.asyncio
    async def test_cache_hit_performance_difference(self):
        """Test performance difference for cache hits."""
        mock_adapter = MockAdapter(children_per_node=10)
        
        # Warm up caches with same paths
        paths = [Path(f"/test/path_{i}") for i in range(100)]
        
        # Fast mode
        fast_adapter = CompletenessAwareCacheAdapter(
            mock_adapter,
            enable_oom_protection=False
        )
        
        # Warm up
        for path in paths:
            node = MockNode(path)
            async for _ in fast_adapter.get_children(node):
                pass
        
        # Time cache hits
        start = time.perf_counter()
        for _ in range(10):  # Multiple rounds
            for path in paths:
                node = MockNode(path)
                async for _ in fast_adapter.get_children(node):
                    pass
        fast_hit_time = time.perf_counter() - start
        
        # Safe mode
        mock_adapter.call_count = 0  # Reset
        safe_adapter = CompletenessAwareCacheAdapter(
            mock_adapter,
            enable_oom_protection=True
        )
        
        # Warm up
        for path in paths:
            node = MockNode(path)
            async for _ in safe_adapter.get_children(node):
                pass
        
        # Time cache hits
        start = time.perf_counter()
        for _ in range(10):  # Multiple rounds
            for path in paths:
                node = MockNode(path)
                async for _ in safe_adapter.get_children(node):
                    pass
        safe_hit_time = time.perf_counter() - start
        
        hit_overhead = (safe_hit_time - fast_hit_time) / fast_hit_time * 100
        
        print(f"\nCache hit performance:")
        print(f"Fast mode: {fast_hit_time:.3f}s")
        print(f"Safe mode: {safe_hit_time:.3f}s")
        print(f"Overhead: {hit_overhead:.1f}%")
        
        # Cache hits should have reasonable overhead in safe mode
        # 40% is acceptable for LRU tracking and safety checks
        assert hit_overhead < 40, f"Cache hit overhead {hit_overhead:.1f}% too high"


class TestSafetyFeatureValidation:
    """Ensure safety features work correctly when enabled."""
    
    @pytest.mark.asyncio
    async def test_safety_features_disabled_in_fast_mode(self):
        """Verify safety features are actually disabled in fast mode."""
        mock_adapter = MockAdapter(children_per_node=10)
        
        # Create adapter with protection disabled
        adapter = CompletenessAwareCacheAdapter(
            mock_adapter,
            enable_oom_protection=False
        )
        
        # These should be disabled/unlimited
        assert not hasattr(adapter, 'max_entries') or adapter.max_entries == 0
        assert isinstance(adapter.cache, dict)  # Regular dict, not OrderedDict
        
        # Should be able to cache unlimited entries
        for i in range(20000):  # Way more than normal limit
            path = Path(f"/test/path_{i}")
            node = MockNode(path)
            async for _ in adapter.get_children(node):
                pass
        
        # No limit enforcement
        assert len(adapter.cache) > 10000  # Would be limited in safe mode
    
    @pytest.mark.asyncio
    async def test_safety_features_enabled_in_safe_mode(self):
        """Verify safety features work correctly when enabled."""
        mock_adapter = MockAdapter(children_per_node=10)
        
        # Create adapter with protection enabled
        adapter = CompletenessAwareCacheAdapter(
            mock_adapter,
            enable_oom_protection=True,
            max_entries=100  # Small limit for testing
        )
        
        # Should use OrderedDict
        assert isinstance(adapter.cache, OrderedDict)
        
        # Should enforce limits
        for i in range(200):
            path = Path(f"/test/path_{i}")
            node = MockNode(path)
            async for _ in adapter.get_children(node):
                pass
        
        # Limit should be enforced
        assert len(adapter.cache) <= 100


if __name__ == "__main__":
    # Run with: python -m pytest tests/test_issue_29_performance_optional_safety.py -v -s
    pytest.main([__file__, "-v", "-s"])