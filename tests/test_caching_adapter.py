"""
Test suite for CachingTreeAdapter with focus on concurrent access patterns.

Tests the caching layer's ability to:
1. Prevent duplicate concurrent scans
2. Share results between waiting tasks
3. Handle cache invalidation correctly
4. Provide performance benefits
"""

import asyncio
import os
import tempfile
import time
from pathlib import Path
from typing import List, Set, Optional
import pytest

from dazzletreelib.aio.caching import CachingTreeAdapter, FilesystemCachingAdapter
from dazzletreelib.aio.adapters import AsyncFileSystemAdapter, AsyncFileSystemNode
from dazzletreelib.aio.core import AsyncTreeNode


class MockSlowAdapter:
    """Mock adapter that simulates slow I/O operations."""
    
    def __init__(self, delay: float = 0.1):
        self.delay = delay
        self.scan_count = 0
        self.scanned_paths: List[Path] = []
        self.semaphore = asyncio.Semaphore(100)
    
    async def get_children(self, node: AsyncTreeNode):
        """Simulate slow I/O with tracking."""
        self.scan_count += 1
        self.scanned_paths.append(node.path if hasattr(node, 'path') else node)
        
        # Simulate slow I/O
        await asyncio.sleep(self.delay)
        
        # Yield mock children
        if hasattr(node, 'path'):
            for i in range(3):
                yield AsyncFileSystemNode(node.path / f"child_{i}")
    
    async def get_parent(self, node: AsyncTreeNode) -> Optional[AsyncTreeNode]:
        """Mock parent retrieval."""
        if hasattr(node, 'path') and node.path.parent != node.path:
            return AsyncFileSystemNode(node.path.parent)
        return None
    
    async def get_depth(self, node: AsyncTreeNode) -> int:
        """Mock depth calculation."""
        if hasattr(node, 'path'):
            return len(node.path.parts) - 1
        return 0


async def collect_children(adapter, node):
    """Helper to collect all children from async iterator."""
    children = []
    async for child in adapter.get_children(node):
        children.append(child)
    return children


@pytest.mark.asyncio
async def test_concurrent_access_prevention():
    """Test that concurrent scans of the same path are prevented."""
    mock_adapter = MockSlowAdapter(delay=0.1)
    cached_adapter = CachingTreeAdapter(mock_adapter)
    
    test_node = AsyncFileSystemNode(Path("/test"))
    
    # Start 5 concurrent tasks requesting the same path
    tasks = [
        asyncio.create_task(collect_children(cached_adapter, test_node))
        for _ in range(5)
    ]
    
    # Wait for all tasks to complete
    results = await asyncio.gather(*tasks)
    
    # All tasks should get the same result
    first_result = results[0]
    for result in results[1:]:
        assert len(result) == len(first_result)
        for i, child in enumerate(result):
            assert child.path == first_result[i].path
    
    # Only one actual scan should have occurred
    assert mock_adapter.scan_count == 1
    
    # Check that concurrent waits were tracked
    assert cached_adapter.concurrent_waits == 4  # 4 tasks waited for the first


@pytest.mark.asyncio
async def test_cache_hit_performance():
    """Test that cache hits are significantly faster than cache misses."""
    mock_adapter = MockSlowAdapter(delay=0.05)
    cached_adapter = CachingTreeAdapter(mock_adapter, ttl=10.0)
    
    test_node = AsyncFileSystemNode(Path("/test"))
    
    # First call - cache miss
    start = time.perf_counter()
    result1 = await collect_children(cached_adapter, test_node)
    miss_time = time.perf_counter() - start
    
    # Second call - cache hit
    start = time.perf_counter()
    result2 = await collect_children(cached_adapter, test_node)
    hit_time = time.perf_counter() - start
    
    # Results should be the same
    assert len(result1) == len(result2)
    for i, child in enumerate(result1):
        assert child.path == result2[i].path
    
    # Cache hit should be at least 10x faster
    assert hit_time < miss_time / 10
    
    # Verify statistics
    assert cached_adapter.cache_hits == 1
    assert cached_adapter.cache_misses == 1


@pytest.mark.asyncio
async def test_different_paths_independent():
    """Test that different paths are cached independently."""
    mock_adapter = MockSlowAdapter(delay=0.01)
    cached_adapter = CachingTreeAdapter(mock_adapter)
    
    paths = [Path(f"/test{i}") for i in range(5)]
    nodes = [AsyncFileSystemNode(p) for p in paths]
    
    # Request all different paths
    results = []
    for node in nodes:
        children = await collect_children(cached_adapter, node)
        results.append(children)
    
    # Each path should have triggered a separate scan
    assert mock_adapter.scan_count == 5
    assert len(set(mock_adapter.scanned_paths)) == 5
    
    # No concurrent waits should have occurred
    assert cached_adapter.concurrent_waits == 0


@pytest.mark.asyncio
async def test_mixed_concurrent_patterns():
    """Test mixed patterns of concurrent and sequential access."""
    mock_adapter = MockSlowAdapter(delay=0.05)
    cached_adapter = CachingTreeAdapter(mock_adapter)
    
    # Create test nodes
    node_a = AsyncFileSystemNode(Path("/a"))
    node_b = AsyncFileSystemNode(Path("/b"))
    
    # Pattern: A1, A2, B1 start concurrently
    # Then A3 starts after A1/A2 complete
    # Then B2 starts after B1 completes
    
    async def access_pattern():
        # Concurrent access to A
        task_a1 = asyncio.create_task(collect_children(cached_adapter, node_a))
        task_a2 = asyncio.create_task(collect_children(cached_adapter, node_a))
        
        # Concurrent access to B
        task_b1 = asyncio.create_task(collect_children(cached_adapter, node_b))
        
        # Wait for A tasks
        await task_a1
        await task_a2
        
        # Sequential access to A (should hit cache)
        await collect_children(cached_adapter, node_a)
        
        # Wait for B task
        await task_b1
        
        # Sequential access to B (should hit cache)
        await collect_children(cached_adapter, node_b)
    
    await access_pattern()
    
    # Should have 2 actual scans (one for A, one for B)
    assert mock_adapter.scan_count == 2
    
    # Should have 1 concurrent wait (A2 waiting for A1)
    assert cached_adapter.concurrent_waits == 1
    
    # Should have 2 cache hits (A3 and B2)
    assert cached_adapter.cache_hits == 2


@pytest.mark.asyncio
@pytest.mark.skipif(os.name == 'nt', reason="Windows doesn't always update directory mtime on file addition")
async def test_filesystem_mtime_invalidation():
    """Test mtime-based cache invalidation for filesystem."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir) / "test"
        test_dir.mkdir()
        
        # Create initial files
        (test_dir / "file1.txt").touch()
        (test_dir / "file2.txt").touch()
        
        # Create adapters
        base_adapter = AsyncFileSystemAdapter()
        cached_adapter = FilesystemCachingAdapter(base_adapter)
        
        test_node = AsyncFileSystemNode(test_dir)
        
        # First scan
        children1 = await collect_children(cached_adapter, test_node)
        assert len(children1) == 2
        
        # Second scan (should hit cache)
        children2 = await collect_children(cached_adapter, test_node)
        assert len(children2) == 2
        assert cached_adapter.cache_hits == 1
        
        # Modify directory by adding a file
        new_file = test_dir / "file3.txt"
        new_file.write_text("test content")

        # Force directory mtime to update on Windows
        # Windows sometimes doesn't update directory mtime when files are added
        import os
        os.utime(test_dir, None)  # Touch the directory itself

        # Small delay to ensure mtime changes and file is visible
        await asyncio.sleep(0.2)

        # Verify the file was actually created
        assert new_file.exists(), f"New file {new_file} was not created"
        
        # Third scan (should detect change and rescan)
        children3 = await collect_children(cached_adapter, test_node)
        assert len(children3) == 3
        
        # Should have had a cache miss due to mtime change
        assert cached_adapter.cache_misses == 2  # Initial + after modification


@pytest.mark.asyncio
async def test_cache_statistics():
    """Test cache statistics tracking."""
    mock_adapter = MockSlowAdapter(delay=0.01)
    cached_adapter = CachingTreeAdapter(mock_adapter, max_size=10, ttl=5.0)
    
    # Perform various operations
    nodes = [AsyncFileSystemNode(Path(f"/test{i}")) for i in range(5)]
    
    # First pass - all misses
    for node in nodes:
        await collect_children(cached_adapter, node)
    
    # Second pass - all hits
    for node in nodes:
        await collect_children(cached_adapter, node)
    
    # Get statistics
    stats = cached_adapter.get_cache_stats()
    
    assert stats['cache_hits'] == 5
    assert stats['cache_misses'] == 5
    assert stats['hit_rate'] == 0.5
    assert stats['cache_size'] == 5
    assert stats['max_size'] == 10
    assert stats['ttl'] == 5.0


@pytest.mark.asyncio
async def test_cache_clear():
    """Test cache clearing functionality."""
    mock_adapter = MockSlowAdapter(delay=0.01)
    cached_adapter = CachingTreeAdapter(mock_adapter)
    
    test_node = AsyncFileSystemNode(Path("/test"))
    
    # Populate cache
    await collect_children(cached_adapter, test_node)
    assert cached_adapter.cache_misses == 1
    
    # Verify cache hit
    await collect_children(cached_adapter, test_node)
    assert cached_adapter.cache_hits == 1
    
    # Clear cache
    cached_adapter.clear_cache()
    
    # Statistics should be reset
    assert cached_adapter.cache_hits == 0
    assert cached_adapter.cache_misses == 0
    
    # Next access should be a miss
    await collect_children(cached_adapter, test_node)
    assert cached_adapter.cache_misses == 1


@pytest.mark.asyncio
async def test_exception_handling_in_concurrent_access():
    """Test that exceptions are properly propagated in concurrent access."""
    
    class FailingAdapter:
        def __init__(self):
            self.semaphore = asyncio.Semaphore(100)
            
        async def get_children(self, node):
            await asyncio.sleep(0.05)
            raise ValueError("Simulated failure")
            # Make it a generator
            yield  # pragma: no cover
        
        async def get_parent(self, node):
            return None
        
        async def get_depth(self, node):
            return 0
    
    failing_adapter = FailingAdapter()
    cached_adapter = CachingTreeAdapter(failing_adapter)
    
    test_node = AsyncFileSystemNode(Path("/test"))
    
    # Start concurrent tasks
    tasks = [
        asyncio.create_task(collect_children(cached_adapter, test_node))
        for _ in range(3)
    ]
    
    # All tasks should fail with the same exception
    exceptions = []
    for task in tasks:
        try:
            await task
        except ValueError as e:
            exceptions.append(e)
    
    assert len(exceptions) == 3
    assert all(str(e) == "Simulated failure" for e in exceptions)


@pytest.mark.asyncio
async def test_stress_test_many_concurrent_paths():
    """Stress test with many concurrent accesses to different paths."""
    mock_adapter = MockSlowAdapter(delay=0.001)
    cached_adapter = CachingTreeAdapter(mock_adapter, max_size=1000)
    
    # Create 100 different paths
    paths = [Path(f"/test/{i // 10}/{i}") for i in range(100)]
    nodes = [AsyncFileSystemNode(p) for p in paths]
    
    # Access all paths concurrently
    tasks = [
        asyncio.create_task(collect_children(cached_adapter, node))
        for node in nodes
    ]
    
    results = await asyncio.gather(*tasks)
    
    # Should have scanned each unique path once
    assert mock_adapter.scan_count == 100
    
    # Now access them all again (should all hit cache)
    for node in nodes:
        await collect_children(cached_adapter, node)
    
    assert cached_adapter.cache_hits == 100
    assert cached_adapter.cache_misses == 100


@pytest.mark.asyncio
async def test_ttl_expiration():
    """Test that TTL expiration works correctly."""
    mock_adapter = MockSlowAdapter(delay=0.01)
    cached_adapter = CachingTreeAdapter(mock_adapter, ttl=0.1)  # 100ms TTL
    
    test_node = AsyncFileSystemNode(Path("/test"))
    
    # First access - cache miss
    await collect_children(cached_adapter, test_node)
    assert cached_adapter.cache_misses == 1
    
    # Immediate second access - cache hit
    await collect_children(cached_adapter, test_node)
    assert cached_adapter.cache_hits == 1
    
    # Wait for TTL to expire
    await asyncio.sleep(0.15)
    
    # Third access - should be cache miss due to TTL
    await collect_children(cached_adapter, test_node)
    assert cached_adapter.cache_misses == 2


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])