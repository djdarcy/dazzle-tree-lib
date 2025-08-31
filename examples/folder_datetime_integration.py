"""
Example integration showing how folder-datetime-fix can use DazzleTreeLib's
caching capabilities to achieve high performance.

This demonstrates:
1. Using CachingTreeAdapter for repeated scans
2. Custom traversal strategies
3. File filtering patterns
4. Progress tracking
"""

import asyncio
import time
from pathlib import Path
from typing import Optional, List, AsyncIterator
from datetime import datetime

from dazzletreelib.aio.caching import CachingTreeAdapter
from dazzletreelib.aio.adapters.fast_filesystem import FastAsyncFileSystemAdapter, FastAsyncFileSystemNode
from dazzletreelib.aio.core import AsyncTreeNode


class FolderDateTimeStrategy:
    """
    Example strategy for folder-datetime-fix operations.
    
    This shows how folder-datetime-fix can implement its own
    traversal strategies on top of DazzleTreeLib.
    """
    
    def __init__(self, 
                 root: Path,
                 cache_adapter: Optional[CachingTreeAdapter] = None,
                 max_depth: int = 999):
        """
        Initialize strategy.
        
        Args:
            root: Root path to process
            cache_adapter: Optional caching adapter for performance
            max_depth: Maximum depth to traverse
        """
        self.root = root
        self.max_depth = max_depth
        
        # Use caching adapter if provided, otherwise create one
        if cache_adapter:
            self.adapter = cache_adapter
        else:
            base = FastAsyncFileSystemAdapter()
            self.adapter = CachingTreeAdapter(base, max_size=50000, ttl=300)
        
        self.processed_count = 0
        self.skipped_count = 0
    
    async def find_folders_needing_update(self) -> AsyncIterator[Path]:
        """
        Find all folders that need datetime updates.
        
        This demonstrates how folder-datetime-fix can use
        DazzleTreeLib's traversal with custom filtering.
        """
        root_node = FastAsyncFileSystemNode(self.root)
        
        async for folder in self._traverse_folders(root_node, depth=0):
            # Check if folder needs update (custom logic)
            if await self._needs_datetime_fix(folder):
                yield folder.path
    
    async def _traverse_folders(self, 
                                node: AsyncTreeNode, 
                                depth: int) -> AsyncIterator[AsyncTreeNode]:
        """
        Traverse only folders, respecting max depth.
        """
        if depth > self.max_depth:
            return
        
        # Get children from cache if available
        async for child in self.adapter.get_children(node):
            if not child.is_leaf():  # It's a directory
                yield child
                # Recursively traverse subdirectories
                async for subfolder in self._traverse_folders(child, depth + 1):
                    yield subfolder
    
    async def _needs_datetime_fix(self, folder_node: AsyncTreeNode) -> bool:
        """
        Determine if a folder needs datetime correction.
        
        This is where folder-datetime-fix's specific logic would go.
        """
        # Example logic: check if folder has inconsistent timestamps
        if not hasattr(folder_node, 'path'):
            return False
        
        path = folder_node.path
        
        try:
            # Get folder's own mtime
            folder_mtime = path.stat().st_mtime
            
            # Check children's mtimes
            max_child_mtime = 0
            async for child in self.adapter.get_children(folder_node):
                if hasattr(child, 'path'):
                    child_mtime = child.path.stat().st_mtime
                    max_child_mtime = max(max_child_mtime, child_mtime)
            
            # Folder needs fix if any child is newer than folder
            return max_child_mtime > folder_mtime
            
        except (OSError, IOError):
            return False
    
    async def apply_datetime_fixes(self, folders: List[Path]) -> int:
        """
        Apply datetime fixes to specified folders.
        
        Returns:
            Number of folders successfully fixed
        """
        fixed_count = 0
        
        for folder in folders:
            try:
                # Get the maximum mtime from children
                folder_node = FastAsyncFileSystemNode(folder)
                max_mtime = 0
                
                async for child in self.adapter.get_children(folder_node):
                    if hasattr(child, 'path'):
                        child_mtime = child.path.stat().st_mtime
                        max_mtime = max(max_mtime, child_mtime)
                
                if max_mtime > 0:
                    # Apply the fix (set folder mtime to match newest child)
                    import os
                    os.utime(folder, (max_mtime, max_mtime))
                    fixed_count += 1
                    
            except Exception as e:
                print(f"Error fixing {folder}: {e}")
        
        return fixed_count
    
    def get_cache_stats(self) -> dict:
        """Get cache statistics from the adapter."""
        return self.adapter.get_cache_stats()


async def progressive_depth_scan_example(root: Path):
    """
    Example of progressive depth scanning pattern.
    
    This shows how folder-datetime-fix can leverage caching
    for its progressive depth scanning pattern.
    """
    print("\n" + "=" * 60)
    print("Progressive Depth Scanning with Caching")
    print("=" * 60)
    
    # Create a shared caching adapter
    base_adapter = FastAsyncFileSystemAdapter()
    cache_adapter = CachingTreeAdapter(base_adapter, max_size=100000, ttl=600)
    
    depths = [1, 2, 3, 5, 999]
    
    for target_depth in depths:
        print(f"\nScanning to depth {target_depth}...")
        
        strategy = FolderDateTimeStrategy(
            root=root,
            cache_adapter=cache_adapter,  # Reuse same cache
            max_depth=target_depth
        )
        
        start = time.perf_counter()
        folders_needing_fix = []
        
        async for folder in strategy.find_folders_needing_update():
            folders_needing_fix.append(folder)
        
        elapsed = time.perf_counter() - start
        
        print(f"  Found {len(folders_needing_fix)} folders needing fixes")
        print(f"  Time: {elapsed:.3f}s")
        
        # Show cache effectiveness
        stats = cache_adapter.get_cache_stats()
        print(f"  Cache hit rate: {stats['hit_rate']:.1%}")
        print(f"  Cache size: {stats['cache_size']}")
    
    print("\n" + "=" * 60)
    print("Progressive scanning complete!")
    print("Notice how later scans are much faster due to caching.")
    print("=" * 60)


async def batch_processing_example(root: Path):
    """
    Example of batch processing with cache warming.
    
    Shows how folder-datetime-fix can warm the cache
    before processing batches of folders.
    """
    print("\n" + "=" * 60)
    print("Batch Processing with Cache Warming")
    print("=" * 60)
    
    strategy = FolderDateTimeStrategy(root)
    
    # Phase 1: Warm the cache by scanning everything
    print("\n1. Warming cache...")
    start = time.perf_counter()
    all_folders = []
    async for folder in strategy.find_folders_needing_update():
        all_folders.append(folder)
    warm_time = time.perf_counter() - start
    print(f"   Found {len(all_folders)} folders in {warm_time:.3f}s")
    
    # Phase 2: Process in batches (cache is warm)
    print("\n2. Processing in batches...")
    batch_size = 10
    total_fixed = 0
    
    for i in range(0, len(all_folders), batch_size):
        batch = all_folders[i:i+batch_size]
        print(f"   Processing batch {i//batch_size + 1} ({len(batch)} folders)...")
        
        start = time.perf_counter()
        fixed = await strategy.apply_datetime_fixes(batch)
        batch_time = time.perf_counter() - start
        
        total_fixed += fixed
        print(f"     Fixed {fixed} folders in {batch_time:.3f}s")
    
    # Show final statistics
    stats = strategy.get_cache_stats()
    print(f"\n3. Final Statistics:")
    print(f"   Total folders fixed: {total_fixed}")
    print(f"   Cache hits: {stats['cache_hits']}")
    print(f"   Cache misses: {stats['cache_misses']}")
    print(f"   Hit rate: {stats['hit_rate']:.1%}")


async def main():
    """Run integration examples."""
    
    # Use current directory or a test directory
    test_root = Path.cwd()
    
    print("Folder-DateTime-Fix Integration Examples")
    print("=========================================")
    print(f"Using root: {test_root}")
    
    # Example 1: Progressive depth scanning
    await progressive_depth_scan_example(test_root)
    
    # Example 2: Batch processing
    # Uncomment to run (modifies file timestamps!)
    # await batch_processing_example(test_root)
    
    print("\nIntegration examples complete!")


if __name__ == "__main__":
    asyncio.run(main())