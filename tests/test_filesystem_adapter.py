"""Unit tests for FileSystem adapter.

Tests the FileSystemAdapter and FileSystemNode implementations,
focusing on functionality needed by folder-datetime-fix.
"""

import unittest
import tempfile
import os
import sys
from pathlib import Path
from datetime import datetime
import time

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dazzletreelib.sync import FileSystemNode, FileSystemAdapter
from dazzletreelib.sync.adapters.filesystem import FilteredFileSystemAdapter


class TestFileSystemNode(unittest.TestCase):
    """Test FileSystemNode functionality."""
    
    def setUp(self):
        """Create a temporary directory for testing."""
        self.test_dir = tempfile.mkdtemp()
        self.test_file = Path(self.test_dir) / "test.txt"
        self.test_file.write_text("test content")
        
    def tearDown(self):
        """Clean up test directory."""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
        
    def test_node_creation(self):
        """Test creating a FileSystemNode."""
        node = FileSystemNode(self.test_dir)
        self.assertIsNotNone(node)
        self.assertEqual(node.path, Path(self.test_dir))
        
    def test_node_identifier(self):
        """Test node identifier returns absolute path."""
        node = FileSystemNode(self.test_dir)
        identifier = node.identifier()
        self.assertTrue(os.path.isabs(identifier))
        self.assertEqual(identifier, str(Path(self.test_dir).absolute()))
        
    def test_is_leaf_directory(self):
        """Test is_leaf for directory."""
        node = FileSystemNode(self.test_dir)
        self.assertFalse(node.is_leaf())
        
    def test_is_leaf_file(self):
        """Test is_leaf for file."""
        node = FileSystemNode(self.test_file)
        self.assertTrue(node.is_leaf())
        
    def test_metadata_directory(self):
        """Test metadata for directory."""
        node = FileSystemNode(self.test_dir)
        metadata = node.metadata()
        
        self.assertIn('name', metadata)
        self.assertIn('path', metadata)
        self.assertIn('exists', metadata)
        self.assertIn('is_dir', metadata)
        self.assertIn('is_file', metadata)
        self.assertTrue(metadata['is_dir'])
        self.assertFalse(metadata['is_file'])
        self.assertTrue(metadata['exists'])
        
    def test_metadata_file(self):
        """Test metadata for file."""
        node = FileSystemNode(self.test_file)
        metadata = node.metadata()
        
        self.assertIn('size', metadata)
        self.assertIn('mtime', metadata)
        self.assertIn('mtime_dt', metadata)
        self.assertFalse(metadata['is_dir'])
        self.assertTrue(metadata['is_file'])
        self.assertEqual(metadata['size'], len("test content"))
        self.assertIsInstance(metadata['mtime_dt'], datetime)
        
    def test_metadata_caching(self):
        """Test that metadata is cached."""
        node = FileSystemNode(self.test_file)
        metadata1 = node.metadata()
        metadata2 = node.metadata()
        # Should be the same object (cached)
        self.assertIs(metadata1, metadata2)


class TestFileSystemAdapter(unittest.TestCase):
    """Test FileSystemAdapter functionality."""
    
    def setUp(self):
        """Create a test directory structure."""
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        
        # Create structure:
        # test_dir/
        #   file1.txt
        #   file2.py
        #   .hidden.txt
        #   subdir1/
        #     file3.txt
        #     subdir2/
        #       file4.txt
        #   emptydir/
        
        (self.test_path / "file1.txt").write_text("content1")
        (self.test_path / "file2.py").write_text("# python")
        (self.test_path / ".hidden.txt").write_text("hidden")
        
        (self.test_path / "subdir1").mkdir()
        (self.test_path / "subdir1" / "file3.txt").write_text("content3")
        
        (self.test_path / "subdir1" / "subdir2").mkdir()
        (self.test_path / "subdir1" / "subdir2" / "file4.txt").write_text("content4")
        
        (self.test_path / "emptydir").mkdir()
        
    def tearDown(self):
        """Clean up test directory."""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
        
    def test_adapter_creation(self):
        """Test creating a FileSystemAdapter."""
        adapter = FileSystemAdapter()
        self.assertIsNotNone(adapter)
        self.assertFalse(adapter.follow_symlinks)
        self.assertTrue(adapter.include_hidden)
        
    def test_get_children_directory(self):
        """Test getting children of a directory."""
        adapter = FileSystemAdapter()
        node = FileSystemNode(self.test_path)
        
        children = list(adapter.get_children(node))
        child_names = {child.path.name for child in children}
        
        # Should include all items including hidden
        self.assertIn("file1.txt", child_names)
        self.assertIn("file2.py", child_names)
        self.assertIn(".hidden.txt", child_names)
        self.assertIn("subdir1", child_names)
        self.assertIn("emptydir", child_names)
        
    def test_get_children_file(self):
        """Test getting children of a file (should be empty)."""
        adapter = FileSystemAdapter()
        node = FileSystemNode(self.test_path / "file1.txt")
        
        children = list(adapter.get_children(node))
        self.assertEqual(len(children), 0)
        
    def test_get_children_empty_directory(self):
        """Test getting children of empty directory."""
        adapter = FileSystemAdapter()
        node = FileSystemNode(self.test_path / "emptydir")
        
        children = list(adapter.get_children(node))
        self.assertEqual(len(children), 0)
        
    def test_exclude_hidden_files(self):
        """Test excluding hidden files."""
        adapter = FileSystemAdapter(include_hidden=False)
        node = FileSystemNode(self.test_path)
        
        children = list(adapter.get_children(node))
        child_names = {child.path.name for child in children}
        
        # Should not include hidden files
        self.assertNotIn(".hidden.txt", child_names)
        self.assertIn("file1.txt", child_names)
        
    def test_get_parent_subdirectory(self):
        """Test getting parent of subdirectory."""
        adapter = FileSystemAdapter()
        child_node = FileSystemNode(self.test_path / "subdir1")
        
        parent = adapter.get_parent(child_node)
        self.assertIsNotNone(parent)
        self.assertEqual(parent.path, self.test_path)
        
    def test_get_parent_root(self):
        """Test getting parent of root returns None."""
        adapter = FileSystemAdapter()
        # Use root of current drive
        root_path = Path(self.test_path).anchor
        root_node = FileSystemNode(root_path)
        
        parent = adapter.get_parent(root_node)
        self.assertIsNone(parent)
        
    def test_get_depth(self):
        """Test calculating depth of nodes."""
        adapter = FileSystemAdapter()
        
        # Create nodes at different depths
        root = FileSystemNode(self.test_path)
        subdir1 = FileSystemNode(self.test_path / "subdir1")
        subdir2 = FileSystemNode(self.test_path / "subdir1" / "subdir2")
        file4 = FileSystemNode(self.test_path / "subdir1" / "subdir2" / "file4.txt")
        
        # Test depth calculation
        # Note: depths are relative to filesystem root, not test_path
        depth_root = adapter.get_depth(root)
        depth_sub1 = adapter.get_depth(subdir1)
        depth_sub2 = adapter.get_depth(subdir2)
        depth_file = adapter.get_depth(file4)
        
        # Check relative depths
        self.assertEqual(depth_sub1 - depth_root, 1)
        self.assertEqual(depth_sub2 - depth_sub1, 1)
        self.assertEqual(depth_file - depth_sub2, 1)
        
    def test_supports_capabilities(self):
        """Test adapter capability flags."""
        adapter = FileSystemAdapter()
        
        self.assertTrue(adapter.supports_full_data())
        self.assertTrue(adapter.supports_random_access())
        self.assertFalse(adapter.supports_async())
        self.assertFalse(adapter.supports_modification())


class TestFilteredFileSystemAdapter(unittest.TestCase):
    """Test FilteredFileSystemAdapter functionality."""
    
    def setUp(self):
        """Create test directory structure."""
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        
        # Create structure with various file types
        (self.test_path / "script.py").write_text("# python")
        (self.test_path / "data.txt").write_text("data")
        (self.test_path / "cache.pyc").write_bytes(b"bytecode")
        
        (self.test_path / ".git").mkdir()
        (self.test_path / ".git" / "config").write_text("git config")
        
        (self.test_path / "__pycache__").mkdir()
        (self.test_path / "__pycache__" / "module.pyc").write_bytes(b"bytecode")
        
        (self.test_path / "src").mkdir()
        (self.test_path / "src" / "main.py").write_text("# main")
        
    def tearDown(self):
        """Clean up test directory."""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
        
    def test_filter_directories(self):
        """Test filtering specific directories."""
        adapter = FilteredFileSystemAdapter(
            exclude_dirs={'.git', '__pycache__'}
        )
        node = FileSystemNode(self.test_path)
        
        children = list(adapter.get_children(node))
        child_names = {child.path.name for child in children}
        
        # Should exclude .git and __pycache__
        self.assertNotIn('.git', child_names)
        self.assertNotIn('__pycache__', child_names)
        
        # Should include other items
        self.assertIn('script.py', child_names)
        self.assertIn('src', child_names)
        
    def test_filter_extensions(self):
        """Test filtering specific file extensions."""
        adapter = FilteredFileSystemAdapter(
            exclude_extensions={'.pyc'}
        )
        node = FileSystemNode(self.test_path)
        
        children = list(adapter.get_children(node))
        child_names = {child.path.name for child in children}
        
        # Should exclude .pyc files
        self.assertNotIn('cache.pyc', child_names)
        
        # Should include other files
        self.assertIn('script.py', child_names)
        self.assertIn('data.txt', child_names)
        
    def test_combined_filters(self):
        """Test combining directory and extension filters."""
        adapter = FilteredFileSystemAdapter(
            exclude_dirs={'.git', '__pycache__'},
            exclude_extensions={'.pyc', '.tmp'}
        )
        node = FileSystemNode(self.test_path)
        
        children = list(adapter.get_children(node))
        child_names = {child.path.name for child in children}
        
        # Should only have clean files and directories
        self.assertIn('script.py', child_names)
        self.assertIn('data.txt', child_names)
        self.assertIn('src', child_names)
        self.assertNotIn('.git', child_names)
        self.assertNotIn('__pycache__', child_names)
        self.assertNotIn('cache.pyc', child_names)


class TestModificationTimeTracking(unittest.TestCase):
    """Test modification time tracking for folder-datetime-fix use case."""
    
    def setUp(self):
        """Create test directory with known modification times."""
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        
        # Create files with different modification times
        self.old_file = self.test_path / "old.txt"
        self.old_file.write_text("old content")
        time.sleep(0.1)  # Ensure different timestamps
        
        self.new_file = self.test_path / "new.txt"
        self.new_file.write_text("new content")
        
        # Create subdirectory with files
        self.subdir = self.test_path / "subdir"
        self.subdir.mkdir()
        
        self.subfile = self.subdir / "subfile.txt"
        self.subfile.write_text("sub content")
        
    def tearDown(self):
        """Clean up test directory."""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
        
    def test_file_modification_times(self):
        """Test getting modification times from files."""
        old_node = FileSystemNode(self.old_file)
        new_node = FileSystemNode(self.new_file)
        
        old_mtime = old_node.metadata()['mtime']
        new_mtime = new_node.metadata()['mtime']
        
        # New file should have later modification time
        self.assertGreater(new_mtime, old_mtime)
        
    def test_directory_modification_time(self):
        """Test getting modification time of directory."""
        dir_node = FileSystemNode(self.subdir)
        metadata = dir_node.metadata()
        
        self.assertIn('mtime', metadata)
        self.assertIn('mtime_dt', metadata)
        self.assertIsInstance(metadata['mtime'], float)
        self.assertIsInstance(metadata['mtime_dt'], datetime)
        
    def test_collect_all_mtimes_in_tree(self):
        """Test collecting all modification times in a tree (for deep scan)."""
        from dazzletreelib.sync import traverse_tree, collect_tree_data
        from dazzletreelib.sync import DataRequirement
        
        adapter = FileSystemAdapter()
        root = FileSystemNode(self.test_path)
        
        # Collect all modification times
        mtimes = []
        for node, metadata in collect_tree_data(
            root, adapter,
            data_requirement=DataRequirement.METADATA
        ):
            if 'mtime' in metadata:
                mtimes.append(metadata['mtime'])
        
        # Should have collected mtimes for all files and directories
        self.assertGreater(len(mtimes), 0)
        
        # Maximum mtime should be from the newest file
        max_mtime = max(mtimes)
        new_file_mtime = FileSystemNode(self.new_file).metadata()['mtime']
        
        # The max mtime in tree should include the new file's mtime
        self.assertGreaterEqual(max_mtime, new_file_mtime)
        
    def test_shallow_vs_deep_scan(self):
        """Test difference between shallow and deep timestamp calculation."""
        from dazzletreelib.sync import traverse_tree
        
        adapter = FileSystemAdapter()
        root = FileSystemNode(self.test_path)
        
        # Shallow scan - only immediate children
        shallow_mtimes = []
        for node in traverse_tree(root, adapter, max_depth=1):
            metadata = node.metadata()
            if 'mtime' in metadata:
                shallow_mtimes.append(metadata['mtime'])
        
        # Deep scan - all descendants
        deep_mtimes = []
        for node in traverse_tree(root, adapter):
            metadata = node.metadata()
            if 'mtime' in metadata:
                deep_mtimes.append(metadata['mtime'])
        
        # Deep scan should find more files
        self.assertGreater(len(deep_mtimes), len(shallow_mtimes))
        
        # Both should include the root and immediate children
        self.assertGreater(len(shallow_mtimes), 0)


class TestPathFiltering(unittest.TestCase):
    """Test path filtering for include/exclude patterns."""
    
    def setUp(self):
        """Create test directory structure."""
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        
        # Create structure with patterns to filter
        (self.test_path / "include_me.txt").write_text("include")
        (self.test_path / "exclude_me.txt").write_text("exclude")
        (self.test_path / "README.md").write_text("readme")
        
        (self.test_path / "src").mkdir()
        (self.test_path / "src" / "main.py").write_text("main")
        
        (self.test_path / "tests").mkdir()
        (self.test_path / "tests" / "test.py").write_text("test")
        
        (self.test_path / "temp").mkdir()
        (self.test_path / "temp" / "cache.tmp").write_text("temp")
        
    def tearDown(self):
        """Clean up test directory."""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
        
    def test_include_filter(self):
        """Test including only specific patterns."""
        from dazzletreelib.sync import traverse_tree
        
        adapter = FileSystemAdapter()
        root = FileSystemNode(self.test_path)
        
        # Include only .py files and directories
        def include_python(node):
            return node.path.suffix == '.py' or node.path.is_dir()
        
        nodes = list(traverse_tree(root, adapter, include_filter=include_python))
        
        # Check that only Python files and directories are included
        for node in nodes:
            is_python = node.path.suffix == '.py'
            is_dir = node.path.is_dir()
            self.assertTrue(is_python or is_dir)
            
    def test_exclude_filter(self):
        """Test excluding specific patterns."""
        from dazzletreelib.sync import traverse_tree
        
        adapter = FileSystemAdapter()
        root = FileSystemNode(self.test_path)
        
        # Exclude temp directory and .tmp files
        def exclude_temp(node):
            return node.path.name == 'temp' or node.path.suffix == '.tmp'
        
        nodes = list(traverse_tree(root, adapter, exclude_filter=exclude_temp))
        node_names = {node.path.name for node in nodes}
        
        # Should not include temp directory or .tmp files
        self.assertNotIn('temp', node_names)
        self.assertNotIn('cache.tmp', node_names)
        
        # Should include other files
        self.assertIn('src', node_names)
        self.assertIn('main.py', node_names)
        
    def test_combined_include_exclude(self):
        """Test combining include and exclude filters."""
        from dazzletreelib.sync import traverse_tree
        
        adapter = FileSystemAdapter()
        root = FileSystemNode(self.test_path)
        
        # Include only text files but exclude those with "exclude" in name
        def include_txt(node):
            return node.path.suffix == '.txt' or node.path.is_dir()
            
        def exclude_pattern(node):
            return 'exclude' in node.path.name
        
        nodes = list(traverse_tree(
            root, adapter,
            include_filter=include_txt,
            exclude_filter=exclude_pattern
        ))
        
        # Collect just the .txt files (not directories)
        txt_files = [n for n in nodes if n.path.suffix == '.txt']
        txt_names = {f.path.name for f in txt_files}
        
        # Should have include_me.txt but not exclude_me.txt
        self.assertIn('include_me.txt', txt_names)
        self.assertNotIn('exclude_me.txt', txt_names)


if __name__ == '__main__':
    unittest.main()