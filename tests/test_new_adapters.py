#!/usr/bin/env python3
"""
Test the new adapters created for folder_datetime_fix integration.
"""

import asyncio
import tempfile
import shutil
import os
from pathlib import Path
from datetime import datetime, timedelta
import time

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from dazzletreelib.aio import (
    AsyncFileSystemNode,
    AsyncFileSystemAdapter,
    TimestampCalculationAdapter,
    CompletenessAwareCacheAdapter,
    CacheCompleteness,
    traverse_post_order_with_depth,
    traverse_tree_bottom_up,
    collect_by_level_bottom_up,
)


def create_test_tree(base_path: Path):
    """Create a test directory tree."""
    # Clean and create
    if base_path.exists():
        shutil.rmtree(base_path)
    base_path.mkdir(parents=True)
    
    # Create structure
    (base_path / "file_root.txt").write_text("root")
    
    dir1 = base_path / "dir1"
    dir1.mkdir()
    (dir1 / "file1.txt").write_text("content1")
    
    dir2 = base_path / "dir2"
    dir2.mkdir()
    (dir2 / "file2.txt").write_text("content2")
    
    subdir = dir1 / "subdir"
    subdir.mkdir()
    (subdir / "file3.txt").write_text("content3")
    
    # Make dir2 older
    old_time = time.time() - (10 * 24 * 60 * 60)  # 10 days ago
    os.utime(dir2, (old_time, old_time))
    
    return base_path


async def test_timestamp_adapter():
    """Test TimestampCalculationAdapter."""
    print("\n" + "="*60)
    print("Testing TimestampCalculationAdapter")
    print("="*60)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        test_path = Path(temp_dir) / "test_tree"
        create_test_tree(test_path)
        
        base_adapter = AsyncFileSystemAdapter()
        
        # Test shallow strategy
        print("\n1. Testing shallow timestamp strategy...")
        shallow_adapter = TimestampCalculationAdapter(base_adapter, strategy='shallow')
        
        dir1_node = AsyncFileSystemNode(test_path / "dir1")
        timestamp = await shallow_adapter.calculate_timestamp(dir1_node)
        print(f"   dir1 shallow timestamp: {timestamp}")
        assert timestamp is not None
        
        # Test deep strategy
        print("\n2. Testing deep timestamp strategy...")
        deep_adapter = TimestampCalculationAdapter(base_adapter, strategy='deep')
        
        timestamp_deep = await deep_adapter.calculate_timestamp(dir1_node)
        print(f"   dir1 deep timestamp: {timestamp_deep}")
        assert timestamp_deep is not None
        
        # Test smart strategy
        print("\n3. Testing smart timestamp strategy...")
        smart_adapter = TimestampCalculationAdapter(base_adapter, strategy='smart')
        
        # Recent folder - should use shallow
        dir1_timestamp = await smart_adapter.calculate_timestamp(dir1_node)
        print(f"   dir1 (recent) smart timestamp: {dir1_timestamp}")
        
        # Old folder - should use deep
        dir2_node = AsyncFileSystemNode(test_path / "dir2")
        dir2_timestamp = await smart_adapter.calculate_timestamp(dir2_node)
        print(f"   dir2 (old) smart timestamp: {dir2_timestamp}")
        
        print("\n[PASS] TimestampCalculationAdapter tests passed!")


async def test_cache_completeness():
    """Test CompletenessAwareCacheAdapter."""
    print("\n" + "="*60)
    print("Testing CompletenessAwareCacheAdapter")
    print("="*60)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        test_path = Path(temp_dir) / "test_tree"
        create_test_tree(test_path)
        
        base_adapter = AsyncFileSystemAdapter()
        cache_adapter = CompletenessAwareCacheAdapter(base_adapter, max_memory_mb=1)
        
        # Test cache completeness levels
        print("\n1. Testing completeness levels...")
        assert CacheCompleteness.from_depth(1) == CacheCompleteness.SHALLOW
        assert CacheCompleteness.from_depth(3) == CacheCompleteness.PARTIAL_3
        assert CacheCompleteness.from_depth(None) == CacheCompleteness.COMPLETE
        print("   [PASS] Completeness levels correct")
        
        # Test cache operations
        print("\n2. Testing cache operations...")
        
        async def compute_func():
            return {"data": "computed", "timestamp": datetime.now()}
        
        # First call - cache miss
        result1, was_cached1 = await cache_adapter.get_or_compute(
            test_path / "dir1",
            compute_func,
            depth=2
        )
        assert not was_cached1
        print("   [PASS] Cache miss on first call")
        
        # Second call with same depth - cache hit
        result2, was_cached2 = await cache_adapter.get_or_compute(
            test_path / "dir1",
            compute_func,
            depth=2
        )
        assert was_cached2
        print("   [PASS] Cache hit on second call")
        
        # Third call with deeper depth - cache upgrade
        result3, was_cached3 = await cache_adapter.get_or_compute(
            test_path / "dir1",
            compute_func,
            depth=5
        )
        assert not was_cached3  # Should recompute for deeper depth
        print("   [PASS] Cache upgrade for deeper depth")
        
        # Check stats
        stats = cache_adapter.get_stats()
        print(f"\n3. Cache statistics:")
        print(f"   Hits: {stats['hits']}")
        print(f"   Misses: {stats['misses']}")
        print(f"   Upgrades: {stats['upgrades']}")
        print(f"   Hit rate: {stats['hit_rate']:.1%}")
        
        print("\n[PASS] CompletenessAwareCacheAdapter tests passed!")


async def test_post_order_traversal():
    """Test post-order (bottom-up) traversal."""
    print("\n" + "="*60)
    print("Testing Post-Order Traversal")
    print("="*60)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        test_path = Path(temp_dir) / "test_tree"
        create_test_tree(test_path)
        
        # Test post-order with depth
        print("\n1. Testing post-order traversal with depth...")
        nodes_visited = []
        
        async for node, depth in traverse_post_order_with_depth(test_path):
            if hasattr(node, 'path'):
                rel_path = node.path.relative_to(test_path.parent)
                nodes_visited.append((str(rel_path), depth))
                print(f"   Depth {depth}: {rel_path}")
        
        # In post-order, children come before parents
        # So subdir should come before dir1
        paths = [p for p, d in nodes_visited]
        assert any("subdir" in p for p in paths)
        assert any("dir1" in p for p in paths)
        
        # Find indices
        subdir_idx = next(i for i, p in enumerate(paths) if "subdir" in p)
        dir1_idx = next(i for i, p in enumerate(paths) if p.endswith("dir1"))
        
        assert subdir_idx < dir1_idx, "Subdir should be visited before dir1 in post-order"
        print("   [PASS] Post-order correct: children before parents")
        
        # Test bottom-up directory traversal
        print("\n2. Testing bottom-up directory-only traversal...")
        dirs_visited = []
        
        async for node in traverse_tree_bottom_up(
            test_path,
            process_directories_only=True
        ):
            rel_path = node.path.relative_to(test_path.parent)
            dirs_visited.append(str(rel_path))
            print(f"   {rel_path}")
        
        # Should only have directories
        assert all(Path(test_path.parent / p).is_dir() for p in dirs_visited)
        print("   [PASS] Only directories visited")
        
        # Test collect by level bottom-up
        print("\n3. Testing collect by level (bottom-up)...")
        
        async for depth, nodes in collect_by_level_bottom_up(test_path, max_depth=2):
            print(f"   Level {depth}: {len(nodes)} nodes")
            for node in nodes[:3]:  # Show first 3
                if hasattr(node, 'path'):
                    print(f"     - {node.path.name}")
        
        print("\n[PASS] Post-order traversal tests passed!")


async def main():
    """Run all adapter tests."""
    print("Testing New DazzleTreeLib Adapters")
    print("=" * 60)
    
    await test_timestamp_adapter()
    await test_cache_completeness()
    await test_post_order_traversal()
    
    print("\n" + "=" * 60)
    print("ALL ADAPTER TESTS PASSED! [PASS]")
    print("=" * 60)
    print("\nDazzleTreeLib is now ready for folder_datetime_fix integration!")
    print("New capabilities added:")
    print("  - Timestamp calculation (shallow/deep/smart)")
    print("  - Cache completeness tracking")
    print("  - Post-order (bottom-up) traversal")
    print("  - Memory-bounded caching with LRU eviction")


if __name__ == "__main__":
    import os
    asyncio.run(main())