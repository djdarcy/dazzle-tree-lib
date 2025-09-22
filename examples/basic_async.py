#!/usr/bin/env python3
"""
Basic async traversal example showing the simplicity and speed of DazzleTreeLib.

This example demonstrates:
- Simple async tree traversal
- File size filtering
- Handling of file metadata
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for development
sys.path.insert(0, str(Path(__file__).parent.parent))

from dazzletreelib.aio import traverse_tree_async


async def main():
    """Demonstrate basic async tree traversal."""
    # Get the root path from command line or use current directory
    root_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    
    print(f"Traversing: {root_path}")
    print("-" * 50)
    
    file_count = 0
    dir_count = 0
    total_size = 0
    large_files = []
    
    # Traverse the tree asynchronously
    async for node in traverse_tree_async(root_path, max_depth=3):
        if node.path.is_file():
            file_count += 1
            # Get file size asynchronously
            size = await node.size()
            if size:
                total_size += size
                # Track files larger than 1MB
                if size > 1_000_000:
                    large_files.append((node.path, size))
        else:
            dir_count += 1
    
    # Print summary
    print(f"\nTraversal Summary:")
    print(f"  Directories: {dir_count:,}")
    print(f"  Files: {file_count:,}")
    print(f"  Total Size: {total_size / 1024 / 1024:.1f} MB")
    
    if large_files:
        print(f"\nLarge Files (>1MB):")
        # Sort by size and show top 5
        large_files.sort(key=lambda x: x[1], reverse=True)
        for path, size in large_files[:5]:
            print(f"  {size / 1024 / 1024:.1f} MB: {path.name}")


if __name__ == "__main__":
    print("DazzleTreeLib - Basic Async Traversal Example")
    print("=" * 50)
    asyncio.run(main())