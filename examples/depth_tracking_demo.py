#!/usr/bin/env python3
"""Demo script for depth tracking functionality in DazzleTreeLib.

This script demonstrates how to use the new depth-aware traversal
functions to process trees based on depth information.
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional

# Add parent directory to path for development
sys.path.insert(0, str(Path(__file__).parent.parent))

from dazzletreelib.aio import (
    traverse_with_depth,
    traverse_tree_by_level,
    filter_by_depth,
)


async def demo_basic_depth_tracking(root: Path):
    """Show basic depth tracking during traversal."""
    print("\n=== Basic Depth Tracking ===")
    print(f"Traversing: {root}\n")
    
    # Track max depth and count at each level
    depth_counts = {}
    
    async for node, depth in traverse_with_depth(root, max_depth=3):
        # Count nodes at each depth
        depth_counts[depth] = depth_counts.get(depth, 0) + 1
        
        # Show indented tree structure
        indent = "  " * depth
        name = node.path.name or str(node.path)
        node_type = "[D]" if node.path.is_dir() else "[F]"
        print(f"{indent}{node_type} {name} (depth: {depth})")
    
    print("\nDepth statistics:")
    for depth in sorted(depth_counts.keys()):
        print(f"  Depth {depth}: {depth_counts[depth]} nodes")


async def demo_level_order_traversal(root: Path):
    """Show level-order traversal with batch processing."""
    print("\n=== Level-Order Traversal ===")
    print(f"Processing levels in: {root}\n")
    
    async for depth, nodes in traverse_tree_by_level(root, max_depth=3):
        print(f"Level {depth}: {len(nodes)} nodes")
        
        # Process all nodes at this level
        dirs = [n for n in nodes if n.path.is_dir()]
        files = [n for n in nodes if n.path.is_file()]
        
        if dirs:
            print(f"  [D] {len(dirs)} directories")
        if files:
            print(f"  [F] {len(files)} files")
            
        # Show first few names at this level
        names = [n.path.name or "root" for n in nodes[:5]]
        if len(nodes) > 5:
            names.append(f"... and {len(nodes) - 5} more")
        print(f"  Names: {', '.join(names)}")


async def demo_depth_filtering(root: Path):
    """Show filtering by depth criteria."""
    print("\n=== Depth-Based Filtering ===")
    print(f"Filtering nodes in: {root}\n")
    
    # Get nodes at exact depth 2
    depth_2_nodes = await filter_by_depth(root, exact_depth=2)
    print(f"Nodes at depth 2: {len(depth_2_nodes)}")
    for path in depth_2_nodes[:5]:
        print(f"  - {path.relative_to(root.parent)}")
    if len(depth_2_nodes) > 5:
        print(f"  ... and {len(depth_2_nodes) - 5} more")
    
    # Get nodes between depth 1 and 3
    print("\nNodes at depth 1-3:")
    range_nodes = await filter_by_depth(root, min_depth=1, max_depth=3)
    print(f"  Total: {len(range_nodes)} nodes")
    
    # Get deep nodes only
    print("\nDeep nodes (depth >= 3):")
    deep_nodes = await filter_by_depth(root, min_depth=3)
    print(f"  Total: {len(deep_nodes)} nodes")


async def demo_depth_based_processing(root: Path):
    """Show how depth tracking helps with folder_datetime_fix use case."""
    print("\n=== Depth-Based Processing (folder_datetime_fix use case) ===")
    print(f"Processing: {root}\n")
    
    # Example: Process only directories at specific depths
    # This is useful for folder_datetime_fix which needs to
    # operate at arbitrary depths
    
    directories_by_depth = {}
    
    async for node, depth in traverse_with_depth(root, max_depth=4):
        if node.path.is_dir():
            if depth not in directories_by_depth:
                directories_by_depth[depth] = []
            directories_by_depth[depth].append(node.path)
    
    print("Directory structure by depth:")
    for depth in sorted(directories_by_depth.keys()):
        dirs = directories_by_depth[depth]
        print(f"\nDepth {depth}: {len(dirs)} directories")
        
        # Show how we could apply different rules at different depths
        if depth == 0:
            print("  -> Root: Skip processing")
        elif depth == 1:
            print("  -> Top-level: Apply broad timestamp rules")
        elif depth == 2:
            print("  -> Mid-level: Apply project-specific rules")
        else:
            print("  -> Deep: Apply fine-grained rules")
        
        # Show first few directories
        for dir_path in dirs[:3]:
            rel_path = dir_path.relative_to(root.parent) if dir_path != root else "."
            print(f"    {rel_path}")
        if len(dirs) > 3:
            print(f"    ... and {len(dirs) - 3} more")


async def demo_performance_comparison(root: Path):
    """Compare performance of depth tracking vs recalculation."""
    print("\n=== Performance Comparison ===")
    print(f"Comparing depth tracking performance on: {root}\n")
    
    import time
    
    # Method 1: With depth tracking (O(1) per node)
    start = time.perf_counter()
    depth_sum = 0
    node_count = 0
    
    async for node, depth in traverse_with_depth(root):
        depth_sum += depth
        node_count += 1
    
    time_with_tracking = time.perf_counter() - start
    avg_depth = depth_sum / node_count if node_count > 0 else 0
    
    print(f"With depth tracking:")
    print(f"  Time: {time_with_tracking:.4f}s")
    print(f"  Nodes: {node_count}")
    print(f"  Average depth: {avg_depth:.2f}")
    
    # Method 2: Without depth tracking (would need O(depth) recalculation)
    # For demo purposes, we'll simulate the cost
    from dazzletreelib.aio import traverse_tree_async
    
    start = time.perf_counter()
    depth_sum_calc = 0
    node_count_calc = 0
    
    async for node in traverse_tree_async(root):
        # Simulate depth calculation (O(depth) operation)
        depth = len(node.path.relative_to(root).parts)
        depth_sum_calc += depth
        node_count_calc += 1
    
    time_without_tracking = time.perf_counter() - start
    
    print(f"\nWithout depth tracking (simulated):")
    print(f"  Time: {time_without_tracking:.4f}s")
    print(f"  Nodes: {node_count_calc}")
    
    if time_without_tracking > 0:
        speedup = time_without_tracking / time_with_tracking
        print(f"\nSpeedup with depth tracking: {speedup:.2f}x")


async def main():
    """Run all demonstrations."""
    # Get directory to traverse from command line or use current directory
    if len(sys.argv) > 1:
        root = Path(sys.argv[1])
    else:
        root = Path.cwd()
    
    if not root.exists():
        print(f"Error: {root} does not exist")
        sys.exit(1)
    
    print(f"DazzleTreeLib Depth Tracking Demo")
    print(f"{'=' * 50}")
    
    # Run demonstrations
    await demo_basic_depth_tracking(root)
    await demo_level_order_traversal(root)
    await demo_depth_filtering(root)
    await demo_depth_based_processing(root)
    await demo_performance_comparison(root)
    
    print(f"\n{'=' * 50}")
    print("Demo complete!")


if __name__ == "__main__":
    asyncio.run(main())