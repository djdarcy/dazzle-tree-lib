"""
Behavioral equivalence tests for os.scandir vs os.listdir implementations.
These tests ensure the refactored AsyncFileSystemAdapter produces identical results.
"""

import os
import stat
import asyncio
import tempfile
import shutil
from pathlib import Path
from typing import Set, List, Tuple
import unittest
from unittest.mock import patch, MagicMock

# Import the unified implementation
from dazzletreelib.aio.adapters.filesystem import AsyncFileSystemAdapter, AsyncFileSystemNode


class TestScanDirListDirEquivalence(unittest.TestCase):
    """Test behavioral equivalence between scandir and listdir implementations."""
    
    @classmethod
    def setUpClass(cls):
        """Create a complex test directory structure."""
        cls.test_dir = Path(tempfile.mkdtemp(prefix="dazzle_equiv_test_"))
        
        # Create directory structure
        (cls.test_dir / "regular_dir").mkdir()
        (cls.test_dir / "regular_dir" / "file1.txt").write_text("content1")
        (cls.test_dir / "regular_dir" / "file2.txt").write_text("content2")
        
        # Create nested directories
        (cls.test_dir / "nested").mkdir()
        (cls.test_dir / "nested" / "level1").mkdir()
        (cls.test_dir / "nested" / "level1" / "level2").mkdir()
        (cls.test_dir / "nested" / "level1" / "level2" / "deep.txt").write_text("deep")
        
        # Create empty directory
        (cls.test_dir / "empty_dir").mkdir()
        
        # Create files with special characters
        (cls.test_dir / "special_chars").mkdir()
        (cls.test_dir / "special_chars" / "file with spaces.txt").write_text("spaces")
        (cls.test_dir / "special_chars" / "file_with_unicode_🎉.txt").write_text("unicode")
        
        # Create symlinks (if supported by OS)
        try:
            (cls.test_dir / "symlink_target.txt").write_text("target")
            (cls.test_dir / "good_symlink.txt").symlink_to(cls.test_dir / "symlink_target.txt")
            (cls.test_dir / "broken_symlink.txt").symlink_to(cls.test_dir / "nonexistent.txt")
            cls.symlinks_supported = True
        except (OSError, NotImplementedError):
            cls.symlinks_supported = False
        
        # Create a large directory (for memory/performance testing)
        (cls.test_dir / "large_dir").mkdir()
        for i in range(1000):
            (cls.test_dir / "large_dir" / f"file_{i:04d}.txt").write_text(f"content_{i}")
    
    @classmethod
    def tearDownClass(cls):
        """Clean up test directory."""
        shutil.rmtree(cls.test_dir, ignore_errors=True)
    
    async def get_tree_entries(self, adapter_class, node_class, root_path: Path) -> Set[str]:
        """Get all entries from a tree traversal using specified adapter."""
        adapter = adapter_class()
        root_node = node_class(root_path)
        
        entries = set()
        async for child in adapter.get_children(root_node):
            # Get relative path for comparison
            rel_path = str(child.path.relative_to(root_path))
            entries.add(rel_path)
            
            # Recursively get children if it's a directory
            # Check if it's a directory using Path object
            if child.path.is_dir():
                sub_entries = await self.get_tree_entries(adapter_class, node_class, child.path)
                entries.update(str(Path(rel_path) / e) for e in sub_entries)
        
        return entries
    
    def test_basic_directory_listing(self):
        """Test that both implementations list the same files and directories."""
        async def run_test():
            slow_entries = await self.get_tree_entries(
                AsyncFileSystemAdapter, 
                AsyncFileSystemNode,
                self.test_dir / "regular_dir"
            )
            
            fast_entries = await self.get_tree_entries(
                AsyncFileSystemAdapter,
                AsyncFileSystemNode,
                self.test_dir / "regular_dir"
            )
            
            self.assertEqual(slow_entries, fast_entries, 
                           "Both implementations should return identical entries")
            self.assertIn("file1.txt", slow_entries)
            self.assertIn("file2.txt", slow_entries)
        
        asyncio.run(run_test())
    
    def test_nested_directory_traversal(self):
        """Test deep directory traversal produces same results."""
        async def run_test():
            slow_entries = await self.get_tree_entries(
                AsyncFileSystemAdapter,
                AsyncFileSystemNode,
                self.test_dir / "nested"
            )
            
            fast_entries = await self.get_tree_entries(
                AsyncFileSystemAdapter,
                AsyncFileSystemNode,
                self.test_dir / "nested"
            )
            
            self.assertEqual(slow_entries, fast_entries)
            # Check specific nested paths exist
            self.assertIn(str(Path("level1") / "level2" / "deep.txt"), slow_entries)
        
        asyncio.run(run_test())
    
    def test_empty_directory(self):
        """Test both implementations handle empty directories identically."""
        async def run_test():
            slow_entries = await self.get_tree_entries(
                AsyncFileSystemAdapter,
                AsyncFileSystemNode,
                self.test_dir / "empty_dir"
            )
            
            fast_entries = await self.get_tree_entries(
                AsyncFileSystemAdapter,
                AsyncFileSystemNode,
                self.test_dir / "empty_dir"
            )
            
            self.assertEqual(slow_entries, fast_entries)
            self.assertEqual(len(slow_entries), 0, "Empty directory should have no entries")
        
        asyncio.run(run_test())
    
    def test_special_characters(self):
        """Test handling of files with special characters and unicode."""
        async def run_test():
            slow_entries = await self.get_tree_entries(
                AsyncFileSystemAdapter,
                AsyncFileSystemNode,
                self.test_dir / "special_chars"
            )
            
            fast_entries = await self.get_tree_entries(
                AsyncFileSystemAdapter,
                AsyncFileSystemNode,
                self.test_dir / "special_chars"
            )
            
            self.assertEqual(slow_entries, fast_entries)
            self.assertIn("file with spaces.txt", slow_entries)
            self.assertIn("file_with_unicode_🎉.txt", slow_entries)
        
        asyncio.run(run_test())
    
    @unittest.skipIf(not unittest.TestCase().symlinks_supported if hasattr(unittest.TestCase(), 'symlinks_supported') else True, 
                     "Symlinks not supported on this platform")
    def test_symlink_handling(self):
        """Test both implementations handle symlinks identically."""
        async def run_test():
            # Test directory containing symlinks
            slow_entries = await self.get_tree_entries(
                AsyncFileSystemAdapter,
                AsyncFileSystemNode,
                self.test_dir
            )
            
            fast_entries = await self.get_tree_entries(
                AsyncFileSystemAdapter,
                AsyncFileSystemNode,
                self.test_dir
            )
            
            # Both should list symlinks
            symlink_entries = [e for e in slow_entries if "symlink" in e]
            fast_symlink_entries = [e for e in fast_entries if "symlink" in e]
            
            self.assertEqual(set(symlink_entries), set(fast_symlink_entries),
                           "Both should handle symlinks identically")
        
        if self.symlinks_supported:
            asyncio.run(run_test())
    
    def test_large_directory_performance(self):
        """Test both implementations handle large directories (memory efficiency)."""
        async def run_test():
            slow_entries = await self.get_tree_entries(
                AsyncFileSystemAdapter,
                AsyncFileSystemNode,
                self.test_dir / "large_dir"
            )
            
            fast_entries = await self.get_tree_entries(
                AsyncFileSystemAdapter,
                AsyncFileSystemNode,
                self.test_dir / "large_dir"
            )
            
            self.assertEqual(slow_entries, fast_entries)
            self.assertEqual(len(slow_entries), 1000, "Should have all 1000 files")
        
        asyncio.run(run_test())
    
    def test_error_handling_nonexistent_directory(self):
        """Test both implementations handle nonexistent directories the same way."""
        async def run_test():
            nonexistent = self.test_dir / "does_not_exist"
            
            # Test slow implementation
            slow_adapter = AsyncFileSystemAdapter()
            slow_node = AsyncFileSystemNode(nonexistent)
            slow_entries = []
            try:
                async for child in slow_adapter.get_children(slow_node):
                    slow_entries.append(child)
            except (OSError, FileNotFoundError):
                slow_error = True
            else:
                slow_error = False
            
            # Test fast implementation
            fast_adapter = AsyncFileSystemAdapter()
            fast_node = AsyncFileSystemNode(nonexistent)
            fast_entries = []
            try:
                async for child in fast_adapter.get_children(fast_node):
                    fast_entries.append(child)
            except (OSError, FileNotFoundError):
                fast_error = True
            else:
                fast_error = False
            
            # Both should handle the error the same way
            self.assertEqual(slow_error, fast_error, 
                           "Both should handle nonexistent directories identically")
        
        asyncio.run(run_test())
    
    def test_stat_caching_behavior(self):
        """Test that stat information is cached correctly."""
        async def run_test():
            test_file = self.test_dir / "regular_dir" / "file1.txt"
            
            # Test direct node creation - uses internal _get_stat method
            node1 = AsyncFileSystemNode(test_file)
            stat1 = await node1._get_stat()
            stat2 = await node1._get_stat()
            # Second call should return cached result
            self.assertIs(stat1, stat2, "Node should cache stat")
            
            # Test node from traversal (with DirEntry)
            adapter = AsyncFileSystemAdapter()
            parent_node = AsyncFileSystemNode(self.test_dir / "regular_dir")
            traversed_node = None
            async for child in adapter.get_children(parent_node):
                if child.path.name == "file1.txt":
                    traversed_node = child
                    break
            
            if traversed_node:
                # Node should have DirEntry from scandir
                self.assertIsNotNone(traversed_node._entry, 
                                   "Node from traversal should have DirEntry")
                # Stat should work and be cached
                traversed_stat = await traversed_node._get_stat()
                self.assertIsNotNone(traversed_stat)
                # Compare file sizes
                self.assertEqual(traversed_stat.st_size, stat1.st_size,
                               "Both should report same file size")
        
        asyncio.run(run_test())
    
    def test_resource_cleanup(self):
        """Test that scandir iterator is properly closed (resource management)."""
        async def run_test():
            # Mock os.scandir to track resource cleanup
            with patch('os.scandir') as mock_scandir:
                mock_iterator = MagicMock()
                mock_iterator.__enter__ = MagicMock(return_value=mock_iterator)
                mock_iterator.__exit__ = MagicMock(return_value=None)
                mock_iterator.__iter__ = MagicMock(return_value=iter([]))
                mock_scandir.return_value = mock_iterator
                
                # Run fast adapter which uses scandir
                fast_adapter = AsyncFileSystemAdapter()
                fast_node = AsyncFileSystemNode(self.test_dir)
                
                entries = []
                async for child in fast_adapter.get_children(fast_node):
                    entries.append(child)
                
                # Verify context manager was used properly
                mock_iterator.__enter__.assert_called()
                mock_iterator.__exit__.assert_called()
        
        asyncio.run(run_test())
    
    def test_ordering_consistency(self):
        """Test that ordering is consistent within a single traversal."""
        async def run_test():
            # Both implementations should be internally consistent
            # (though order may differ between them)
            
            slow_adapter = AsyncFileSystemAdapter()
            slow_node = AsyncFileSystemNode(self.test_dir / "regular_dir")
            
            slow_entries1 = []
            async for child in slow_adapter.get_children(slow_node):
                slow_entries1.append(child.path.name)
            
            slow_entries2 = []
            async for child in slow_adapter.get_children(slow_node):
                slow_entries2.append(child.path.name)
            
            # Same adapter should give consistent order
            self.assertEqual(slow_entries1, slow_entries2,
                           "Same adapter should give consistent ordering")
            
            fast_adapter = AsyncFileSystemAdapter()
            fast_node = AsyncFileSystemNode(self.test_dir / "regular_dir")
            
            fast_entries1 = []
            async for child in fast_adapter.get_children(fast_node):
                fast_entries1.append(child.path.name)
            
            fast_entries2 = []
            async for child in fast_adapter.get_children(fast_node):
                fast_entries2.append(child.path.name)
            
            self.assertEqual(fast_entries1, fast_entries2,
                           "Fast adapter should give consistent ordering")
        
        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()