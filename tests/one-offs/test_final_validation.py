#!/usr/bin/env python3
"""Final validation test for DazzleTreeLib optimizations."""

import asyncio
from pathlib import Path
from dazzletreelib.aio import traverse_tree_async


async def test_default_fast_adapter():
    """Test that the fast adapter works as default."""
    test_dir = Path("C:/code/DazzleTreeLib")
    
    # Test with default (fast adapter)
    count_fast = 0
    async for node in traverse_tree_async(test_dir, max_depth=2):
        count_fast += 1
    
    print(f"[PASS] Fast adapter (default): Traversed {count_fast} nodes")
    
    # Test with explicit old adapter
    count_old = 0
    async for node in traverse_tree_async(test_dir, max_depth=2, use_fast_adapter=False):
        count_old += 1
    
    print(f"[PASS] Old adapter (explicit): Traversed {count_old} nodes")
    
    # Should find same number of nodes
    assert count_fast == count_old, f"Node count mismatch: {count_fast} != {count_old}"
    print(f"[PASS] Both adapters found same nodes: {count_fast}")
    
    return True


if __name__ == "__main__":
    success = asyncio.run(test_default_fast_adapter())
    if success:
        print("\n[SUCCESS] Final validation passed - ready to commit!")
    else:
        print("\n[FAIL] Validation failed")