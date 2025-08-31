#!/usr/bin/env python3
"""
Real-world example: Fix directory modification times to match their newest content.

This example demonstrates:
- Depth-first post-order traversal (process deepest first)
- Directory timestamp manipulation
- Real production use case from folder-datetime-fix project
"""

import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

# Add parent directory to path for development
sys.path.insert(0, str(Path(__file__).parent.parent))

from dazzletreelib.aio import traverse_tree_async


async def get_newest_timestamp(dir_path: Path) -> Optional[float]:
    """Get the newest modification time from direct children of a directory."""
    newest_time = 0.0
    
    try:
        # Check all direct children
        for item in dir_path.iterdir():
            stat = item.stat()
            newest_time = max(newest_time, stat.st_mtime)
    except (OSError, PermissionError) as e:
        print(f"  Warning: Cannot read {dir_path}: {e}")
        return None
    
    return newest_time if newest_time > 0 else None


async def fix_directory_timestamps(root_path: Path, dry_run: bool = True) -> Dict[str, int]:
    """
    Fix directory modification times to match their newest content.
    
    This is the core algorithm from folder-datetime-fix project,
    now powered by DazzleTreeLib's async traversal.
    """
    print(f"Scanning directory tree: {root_path}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE UPDATE'}")
    print("-" * 60)
    
    directories = []
    stats = {"scanned": 0, "updated": 0, "skipped": 0, "errors": 0}
    
    # Collect all directories using depth-first post-order
    # This ensures we process child directories before their parents
    async for node in traverse_tree_async(root_path, strategy='dfs_post'):
        if node.path.is_dir():
            directories.append(node.path)
            stats["scanned"] += 1
    
    print(f"Found {len(directories)} directories to process")
    print("-" * 60)
    
    # Process directories from deepest to shallowest
    for dir_path in reversed(directories):
        # Get newest timestamp from directory contents
        newest_time = await get_newest_timestamp(dir_path)
        
        if newest_time is None:
            stats["errors"] += 1
            continue
        
        # Get current directory timestamp
        try:
            current_stat = dir_path.stat()
            current_time = current_stat.st_mtime
        except (OSError, PermissionError) as e:
            print(f"  Error reading {dir_path}: {e}")
            stats["errors"] += 1
            continue
        
        # Check if update is needed
        if abs(current_time - newest_time) > 1:  # 1 second tolerance
            if dry_run:
                print(f"  Would update: {dir_path}")
                print(f"    Current: {datetime.fromtimestamp(current_time)}")
                print(f"    New:     {datetime.fromtimestamp(newest_time)}")
            else:
                try:
                    # Update directory timestamp
                    os.utime(dir_path, (newest_time, newest_time))
                    print(f"  Updated: {dir_path}")
                    stats["updated"] += 1
                except (OSError, PermissionError) as e:
                    print(f"  Error updating {dir_path}: {e}")
                    stats["errors"] += 1
        else:
            stats["skipped"] += 1
    
    return stats


async def main():
    """Run the folder datetime fix utility."""
    # Parse command line arguments
    if len(sys.argv) < 2:
        print("Usage: python folder_datetime_fix.py <directory> [--live]")
        print("  Add --live to actually update timestamps (default is dry run)")
        sys.exit(1)
    
    root_path = Path(sys.argv[1])
    dry_run = "--live" not in sys.argv
    
    if not root_path.exists():
        print(f"Error: Directory not found: {root_path}")
        sys.exit(1)
    
    if not root_path.is_dir():
        print(f"Error: Not a directory: {root_path}")
        sys.exit(1)
    
    print("DazzleTreeLib - Folder DateTime Fix Example")
    print("=" * 60)
    
    # Run the fix
    start_time = asyncio.get_event_loop().time()
    stats = await fix_directory_timestamps(root_path, dry_run)
    elapsed = asyncio.get_event_loop().time() - start_time
    
    # Print summary
    print("\n" + "=" * 60)
    print("Summary:")
    print(f"  Directories scanned: {stats['scanned']:,}")
    print(f"  Directories updated: {stats['updated']:,}")
    print(f"  Directories skipped: {stats['skipped']:,}")
    print(f"  Errors encountered:  {stats['errors']:,}")
    print(f"  Time elapsed: {elapsed:.2f} seconds")
    
    if dry_run and stats['updated'] > 0:
        print("\n⚠️  This was a DRY RUN. Use --live to actually update timestamps.")


if __name__ == "__main__":
    asyncio.run(main())