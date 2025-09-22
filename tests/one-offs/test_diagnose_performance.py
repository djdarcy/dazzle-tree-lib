"""Diagnostic test to understand performance inconsistency."""

import asyncio
import time
from pathlib import Path
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dazzletreelib.aio.adapters.cache_completeness_adapter import CompletenessAwareCacheAdapter


class MockNode:
    def __init__(self, path):
        self.path = Path(path) if not isinstance(path, Path) else path


class MockAdapter:
    def __init__(self, children_per_node=10):
        self.children_per_node = children_per_node
        self.call_count = 0
    
    async def get_children(self, node):
        self.call_count += 1
        for i in range(self.children_per_node):
            yield MockNode(node.path / f"child_{i}")


async def diagnose_performance():
    """Run diagnostic tests to understand performance issues."""
    
    print("=== DIAGNOSTIC TEST FOR PERFORMANCE ISSUES ===\n")
    
    # Test 1: Check if methods are assigned correctly
    print("1. Checking method assignments...")
    
    safe_adapter = CompletenessAwareCacheAdapter(
        MockAdapter(),
        enable_oom_protection=True
    )
    
    fast_adapter = CompletenessAwareCacheAdapter(
        MockAdapter(),
        enable_oom_protection=False
    )
    
    print(f"Safe adapter cache type: {type(safe_adapter.cache)}")
    print(f"Fast adapter cache type: {type(fast_adapter.cache)}")
    print(f"Safe adapter _should_cache_impl: {safe_adapter._should_cache_impl.__name__ if hasattr(safe_adapter._should_cache_impl, '__name__') else 'lambda'}")
    print(f"Fast adapter _should_cache_impl: {fast_adapter._should_cache_impl.__name__ if hasattr(fast_adapter._should_cache_impl, '__name__') else 'lambda'}")
    print(f"Safe adapter _track_node_visit_impl: {safe_adapter._track_node_visit_impl.__name__ if hasattr(safe_adapter._track_node_visit_impl, '__name__') else 'lambda'}")
    print(f"Fast adapter _track_node_visit_impl: {fast_adapter._track_node_visit_impl.__name__ if hasattr(fast_adapter._track_node_visit_impl, '__name__') else 'lambda'}")
    
    # Test 2: Check if fast mode lambdas are actually no-ops
    print("\n2. Testing if fast mode methods are no-ops...")
    
    # Test _track_node_visit_impl
    safe_adapter.node_completeness.clear()
    fast_adapter.node_completeness.clear()
    
    safe_adapter._track_node_visit_impl("/test/path", 5)
    fast_adapter._track_node_visit_impl("/test/path", 5)
    
    print(f"Safe mode node_completeness after track: {len(safe_adapter.node_completeness)} entries")
    print(f"Fast mode node_completeness after track: {len(fast_adapter.node_completeness)} entries")
    
    # Test 3: Measure actual performance difference
    print("\n3. Measuring actual performance (100 iterations each)...")
    
    paths = [Path(f"/test/path_{i}") for i in range(100)]
    
    # Run multiple rounds to check consistency
    for round_num in range(5):
        # Safe mode
        mock_safe = MockAdapter(children_per_node=10)
        safe = CompletenessAwareCacheAdapter(mock_safe, enable_oom_protection=True)
        
        start = time.perf_counter()
        for path in paths:
            node = MockNode(path)
            async for _ in safe.get_children(node):
                pass
        safe_time = time.perf_counter() - start
        
        # Fast mode
        mock_fast = MockAdapter(children_per_node=10)
        fast = CompletenessAwareCacheAdapter(mock_fast, enable_oom_protection=False)
        
        start = time.perf_counter()
        for path in paths:
            node = MockNode(path)
            async for _ in fast.get_children(node):
                pass
        fast_time = time.perf_counter() - start
        
        improvement = (safe_time - fast_time) / safe_time * 100
        print(f"Round {round_num + 1}: Safe={safe_time:.4f}s, Fast={fast_time:.4f}s, Improvement={improvement:.1f}%")
    
    # Test 4: Check cache behavior
    print("\n4. Checking cache behavior...")
    
    mock = MockAdapter(children_per_node=5)
    adapter = CompletenessAwareCacheAdapter(mock, enable_oom_protection=False)
    
    node = MockNode("/test")
    
    # First call - should miss cache
    children1 = []
    async for child in adapter.get_children(node):
        children1.append(child)
    
    print(f"After first call - Hits: {adapter.hits}, Misses: {adapter.misses}")
    
    # Second call - should hit cache
    children2 = []
    async for child in adapter.get_children(node):
        children2.append(child)
    
    print(f"After second call - Hits: {adapter.hits}, Misses: {adapter.misses}")
    print(f"Cache size: {len(adapter.cache)}")
    print(f"Mock adapter calls: {mock.call_count}")
    
    # Test 5: Check if there's a degenerate case
    print("\n5. Testing edge cases...")
    
    # Empty children
    mock_empty = MockAdapter(children_per_node=0)
    adapter_empty = CompletenessAwareCacheAdapter(mock_empty, enable_oom_protection=False)
    
    empty_children = []
    async for child in adapter_empty.get_children(MockNode("/empty")):
        empty_children.append(child)
    
    print(f"Empty children test - Got {len(empty_children)} children")
    print(f"Cache after empty: {len(adapter_empty.cache)} entries")
    
    # Very deep path
    deep_path = "/".join(["level"] * 100)
    deep_node = MockNode(deep_path)
    
    mock_deep = MockAdapter(children_per_node=2)
    adapter_deep = CompletenessAwareCacheAdapter(
        mock_deep, 
        enable_oom_protection=True,
        max_path_depth=30  # Should reject deep paths
    )
    
    deep_children = []
    async for child in adapter_deep.get_children(deep_node):
        deep_children.append(child)
    
    print(f"Deep path test - Got {len(deep_children)} children")
    print(f"Cache after deep path: {len(adapter_deep.cache)} entries (should be 0 due to path limit)")
    
    print("\n=== DIAGNOSTIC COMPLETE ===")


if __name__ == "__main__":
    asyncio.run(diagnose_performance())