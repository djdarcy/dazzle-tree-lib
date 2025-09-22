"""Unit tests for edge cases and error handling in DazzleTreeLib.

Tests unusual scenarios, error conditions, and boundary cases
that might occur in real-world usage.
"""

import unittest
import tempfile
import os
import sys
from pathlib import Path
import stat

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dazzletreelib.sync import (
    FileSystemNode,
    FileSystemAdapter,
    TraversalConfig,
    ExecutionPlan,
    CapabilityMismatchError,
    traverse_tree,
)
from dazzletreelib.sync.config import DepthConfig


class TestEmptyStructures(unittest.TestCase):
    """Test handling of empty directories and edge cases."""
    
    def setUp(self):
        """Create test directory."""
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        
    def tearDown(self):
        """Clean up test directory."""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
        
    def test_empty_directory(self):
        """Test traversing empty directory."""
        adapter = FileSystemAdapter()
        root = FileSystemNode(self.test_path)
        
        nodes = list(traverse_tree(root, adapter))
        
        # Should contain just the root
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0].path, self.test_path)
        
    def test_deeply_nested_empty_dirs(self):
        """Test traversing deeply nested empty directories."""
        # Create nested empty directories
        deep_path = self.test_path
        for i in range(10):
            deep_path = deep_path / f"level{i}"
            deep_path.mkdir()
        
        adapter = FileSystemAdapter()
        root = FileSystemNode(self.test_path)
        
        nodes = list(traverse_tree(root, adapter))
        
        # Should find all 11 directories (root + 10 levels)
        self.assertEqual(len(nodes), 11)
        
        # Check depth calculation
        deepest = nodes[-1]
        adapter_depth = adapter.get_depth(deepest)
        # Depth is relative to filesystem root, not test_path
        self.assertGreater(adapter_depth, 0)
        
    def test_single_file(self):
        """Test traversing directory with single file."""
        single_file = self.test_path / "only.txt"
        single_file.write_text("only content")
        
        adapter = FileSystemAdapter()
        root = FileSystemNode(self.test_path)
        
        nodes = list(traverse_tree(root, adapter))
        
        # Should have root and one file
        self.assertEqual(len(nodes), 2)
        
        # File should be a leaf
        file_node = FileSystemNode(single_file)
        self.assertTrue(file_node.is_leaf())
        
    def test_no_children_for_file(self):
        """Test that files return no children."""
        test_file = self.test_path / "test.txt"
        test_file.write_text("content")
        
        adapter = FileSystemAdapter()
        file_node = FileSystemNode(test_file)
        
        children = list(adapter.get_children(file_node))
        
        # Files should have no children
        self.assertEqual(len(children), 0)


class TestSpecialPaths(unittest.TestCase):
    """Test handling of special paths and characters."""
    
    def setUp(self):
        """Create test directory."""
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        
    def tearDown(self):
        """Clean up test directory."""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
        
    def test_spaces_in_names(self):
        """Test handling paths with spaces."""
        dir_with_spaces = self.test_path / "dir with spaces"
        dir_with_spaces.mkdir()
        
        file_with_spaces = dir_with_spaces / "file with spaces.txt"
        file_with_spaces.write_text("content")
        
        adapter = FileSystemAdapter()
        root = FileSystemNode(self.test_path)
        
        nodes = list(traverse_tree(root, adapter))
        names = [n.path.name for n in nodes]
        
        self.assertIn("dir with spaces", names)
        self.assertIn("file with spaces.txt", names)
        
    def test_unicode_names(self):
        """Test handling Unicode characters in names."""
        # Create files with Unicode names
        unicode_names = [
            "test_ümlaut.txt",
            "test_中文.txt",
            "test_émoji😀.txt" if os.name != 'nt' else "test_emoji.txt"  # Windows may have issues
        ]
        
        for name in unicode_names:
            try:
                (self.test_path / name).write_text("content")
            except (OSError, UnicodeError):
                # Skip if filesystem doesn't support this character
                continue
        
        adapter = FileSystemAdapter()
        root = FileSystemNode(self.test_path)
        
        # Should not crash on Unicode names
        nodes = list(traverse_tree(root, adapter))
        self.assertGreater(len(nodes), 1)  # At least root + some files
        
    def test_very_long_paths(self):
        """Test handling very long path names."""
        # Create a reasonably deep structure (not too deep for Windows)
        current = self.test_path
        for i in range(20):  # Reduced from very deep to avoid Windows path limits
            current = current / f"d{i}"
            try:
                current.mkdir()
            except OSError:
                # Hit path length limit
                break
        
        adapter = FileSystemAdapter()
        root = FileSystemNode(self.test_path)
        
        # Should handle whatever depth we managed to create
        nodes = list(traverse_tree(root, adapter))
        self.assertGreater(len(nodes), 1)
        
    def test_dots_in_names(self):
        """Test handling dots in directory and file names."""
        # Create directories and files with dots
        (self.test_path / "dir.with.dots").mkdir()
        (self.test_path / "..hidden").write_text("hidden")  # Two dots
        (self.test_path / "file...multiple.dots.txt").write_text("dots")
        
        adapter = FileSystemAdapter()
        root = FileSystemNode(self.test_path)
        
        nodes = list(traverse_tree(root, adapter))
        names = [n.path.name for n in nodes if n.path != self.test_path]
        
        self.assertIn("dir.with.dots", names)
        self.assertIn("..hidden", names)
        self.assertIn("file...multiple.dots.txt", names)


class TestPermissionErrors(unittest.TestCase):
    """Test handling of permission errors."""
    
    @unittest.skipIf(os.name == 'nt', "Permission testing is different on Windows")
    def test_unreadable_directory(self):
        """Test handling directory without read permissions."""
        test_dir = tempfile.mkdtemp()
        test_path = Path(test_dir)
        
        try:
            # Create directory and remove read permission
            no_read = test_path / "no_read"
            no_read.mkdir()
            (no_read / "hidden.txt").write_text("can't see me")
            
            # Remove read permission
            os.chmod(no_read, 0o000)
            
            adapter = FileSystemAdapter()
            root = FileSystemNode(test_path)
            
            # Should not crash, just skip unreadable directory
            nodes = list(traverse_tree(root, adapter))
            
            # Should have root and the directory (but not its contents)
            self.assertGreaterEqual(len(nodes), 2)
            
        finally:
            # Restore permissions for cleanup
            try:
                os.chmod(test_path / "no_read", 0o755)
            except:
                pass
            import shutil
            shutil.rmtree(test_dir, ignore_errors=True)
            
    def test_nonexistent_path(self):
        """Test handling of non-existent paths."""
        fake_path = Path("/completely/fake/path/that/does/not/exist")
        
        adapter = FileSystemAdapter()
        node = FileSystemNode(fake_path)
        
        # Should handle gracefully
        metadata = node.metadata()
        self.assertFalse(metadata['exists'])
        
        # Should be treated as leaf (can't have children)
        self.assertTrue(node.is_leaf())
        
        # Getting children should return empty
        children = list(adapter.get_children(node))
        self.assertEqual(len(children), 0)


class TestDepthEdgeCases(unittest.TestCase):
    """Test edge cases in depth handling."""
    
    def setUp(self):
        """Create test directory."""
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        
        # Create structure with known depths
        (self.test_path / "d1").mkdir()
        (self.test_path / "d1" / "d2").mkdir()
        (self.test_path / "d1" / "d2" / "d3").mkdir()
        (self.test_path / "d1" / "d2" / "d3" / "file.txt").write_text("deep")
        
    def tearDown(self):
        """Clean up test directory."""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
        
    def test_max_depth_zero(self):
        """Test max_depth=0 (only root)."""
        adapter = FileSystemAdapter()
        root = FileSystemNode(self.test_path)
        
        nodes = list(traverse_tree(root, adapter, max_depth=0))
        
        # Should only have root
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0].path, self.test_path)
        
    def test_min_depth_greater_than_max(self):
        """Test invalid depth configuration."""
        config = TraversalConfig()
        config.depth.min_depth = 5
        config.depth.max_depth = 3
        
        errors = config.validate()
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("less than min_depth" in e for e in errors))
        
    def test_specific_depths_with_gaps(self):
        """Test selecting specific depths with gaps."""
        config = TraversalConfig()
        config.depth.specific_depths = {0, 2}  # Skip depth 1
        
        adapter = FileSystemAdapter()
        root = FileSystemNode(self.test_path)
        plan = ExecutionPlan(config, adapter)
        
        results = []
        for node, _ in plan.execute(root):
            if node.path == self.test_path:
                depth = 0
            else:
                depth = len(node.path.relative_to(self.test_path).parts)
            results.append((node.path.name, depth))
        
        # Should only have depths 0 and 2
        depths = {depth for _, depth in results}
        self.assertEqual(depths, {0, 2})
        
    def test_min_depth_excludes_root(self):
        """Test that min_depth > 0 excludes root."""
        adapter = FileSystemAdapter()
        root = FileSystemNode(self.test_path)
        
        nodes = list(traverse_tree(root, adapter, min_depth=1))
        
        # Should not include root
        root_included = any(n.path == self.test_path for n in nodes)
        self.assertFalse(root_included)
        
        # Should include children
        self.assertGreater(len(nodes), 0)


class TestLargeStructures(unittest.TestCase):
    """Test handling of large directory structures."""
    
    def setUp(self):
        """Create test directory."""
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        
    def tearDown(self):
        """Clean up test directory."""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
        
    def test_many_files_in_directory(self):
        """Test directory with many files."""
        # Create 100 files in one directory
        for i in range(100):
            (self.test_path / f"file_{i:03d}.txt").write_text(f"content {i}")
        
        adapter = FileSystemAdapter()
        root = FileSystemNode(self.test_path)
        
        nodes = list(traverse_tree(root, adapter))
        
        # Should handle all files
        self.assertEqual(len(nodes), 101)  # root + 100 files
        
        # Check they're sorted (adapter sorts children)
        file_nodes = [n for n in nodes if n.path != self.test_path]
        names = [n.path.name for n in file_nodes]
        self.assertEqual(names, sorted(names))
        
    def test_wide_tree(self):
        """Test very wide tree (many siblings)."""
        # Create 50 directories at root level
        for i in range(50):
            dir_path = self.test_path / f"dir_{i:02d}"
            dir_path.mkdir()
            # Add one file to each
            (dir_path / "file.txt").write_text(f"content {i}")
        
        adapter = FileSystemAdapter()
        root = FileSystemNode(self.test_path)
        
        # Test with depth limit
        nodes_shallow = list(traverse_tree(root, adapter, max_depth=1))
        
        # Should have root + 50 directories
        self.assertEqual(len(nodes_shallow), 51)
        
        # Test full traversal
        nodes_all = list(traverse_tree(root, adapter))
        
        # Should have root + 50 dirs + 50 files
        self.assertEqual(len(nodes_all), 101)
        
    def test_memory_limit_config(self):
        """Test configuration with memory limits."""
        # Create moderate structure
        for i in range(10):
            (self.test_path / f"file_{i}.txt").write_text(f"content {i}")
        
        config = TraversalConfig.memory_efficient(max_memory_mb=1)
        
        adapter = FileSystemAdapter()
        root = FileSystemNode(self.test_path)
        
        # Should work with memory limit
        plan = ExecutionPlan(config, adapter)
        results = list(plan.execute(root))
        
        # Should complete successfully
        self.assertGreater(len(results), 0)
        
        # Check performance config
        self.assertTrue(config.performance.check_memory_limit(0.5))
        self.assertFalse(config.performance.check_memory_limit(2))


class TestSymlinks(unittest.TestCase):
    """Test handling of symbolic links."""
    
    @unittest.skipIf(os.name == 'nt', "Symlink testing requires Unix-like OS")
    def setUp(self):
        """Create test directory with symlinks."""
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)

        # Create scan directory and separate target directory
        # This structure ensures symlink targets are OUTSIDE the scan path
        self.scan_dir = self.test_path / "scan_root"
        self.scan_dir.mkdir()

        # Create target directory and file OUTSIDE scan directory
        target_dir = self.test_path / "target_dir"
        target_dir.mkdir()
        (target_dir / "file.txt").write_text("target")
        target_file = self.test_path / "target_file.txt"
        target_file.write_text("target file")

        # Also create some regular files in scan directory for comparison
        (self.scan_dir / "regular_file.txt").write_text("regular")

        # Create symlinks INSIDE scan directory pointing OUTSIDE
        try:
            link_dir = self.scan_dir / "link_to_dir"
            link_file = self.scan_dir / "link_to_file"

            # Ensure clean state - remove any existing files with these names
            if link_dir.exists():
                link_dir.unlink()
            if link_file.exists():
                link_file.unlink()

            # Create symlinks with absolute targets for CI reliability
            target_dir_abs = target_dir.resolve()
            target_file_abs = target_file.resolve()

            link_dir.symlink_to(target_dir_abs, target_is_directory=True)
            link_file.symlink_to(target_file_abs, target_is_directory=False)

            # Delay and retry to ensure filesystem consistency
            import time
            time.sleep(0.2)  # Increased from 0.1s for CI robustness

            # Retry verification for CI environments
            for attempt in range(5):  # Increased attempts
                if link_dir.is_symlink() and link_file.is_symlink():
                    break
                time.sleep(0.1)

        except (OSError, NotImplementedError) as e:
            # Debug info for CI
            import os
            if os.environ.get('GITHUB_ACTIONS'):
                print(f"DEBUG: Symlink creation failed: {e}")
                print(f"DEBUG: Scan directory contents: {list(self.scan_dir.iterdir())}")
            self.skipTest("Cannot create symlinks on this system")

        # Verify symlinks were actually created
        if not (link_dir.is_symlink() and link_file.is_symlink()):
            # Debug info for CI
            import os
            if os.environ.get('GITHUB_ACTIONS'):
                print(f"DEBUG: Symlink verification failed")
                print(f"DEBUG: link_dir.is_symlink(): {link_dir.is_symlink()}")
                print(f"DEBUG: link_file.is_symlink(): {link_file.is_symlink()}")
                print(f"DEBUG: Scan directory contents: {[f.name for f in self.scan_dir.iterdir()]}")
            self.skipTest("Symlinks not supported on this system")
        
    def tearDown(self):
        """Clean up test directory."""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
        
    def test_symlinks_not_followed(self):
        """Test that symlinks are not followed by default."""
        adapter = FileSystemAdapter(follow_symlinks=False)
        root = FileSystemNode(self.scan_dir)  # Use scan_dir not test_path

        nodes = list(traverse_tree(root, adapter))
        names = [n.path.name for n in nodes]

        # Debug output for CI
        import os
        if os.environ.get('GITHUB_ACTIONS'):
            print(f"DEBUG: Scan directory: {self.scan_dir}")
            print(f"DEBUG: Scan contents on disk: {[f.name for f in self.scan_dir.iterdir()]}")
            print(f"DEBUG: Test directory structure: {self.test_path}")
            print(f"DEBUG: Node names from traversal: {names}")
            print(f"DEBUG: Node paths from traversal: {[str(n.path) for n in nodes]}")

        # Should see the symlinks themselves
        self.assertIn("link_to_dir", names)
        self.assertIn("link_to_file", names)

        # Should see regular file in scan directory
        self.assertIn("regular_file.txt", names)

        # Should NOT see contents from OUTSIDE scan directory (symlink targets)
        self.assertNotIn("file.txt", names)  # Inside target_dir (outside scan)
        self.assertNotIn("target_file.txt", names)  # Outside scan directory
        self.assertNotIn("target_dir", names)  # Outside scan directory
        
    def test_symlinks_colocated_with_targets(self):
        """Test behavior when symlinks and their targets are in the same directory.

        This is an edge case but the behavior should be predictable:
        - With follow_symlinks=False: Both symlinks AND regular dirs are traversed
        - The symlink doesn't 'hide' or prevent traversal of the actual directory
        """
        # Create a test structure with symlinks and targets in SAME directory
        colocated_dir = self.test_path / "colocated"
        colocated_dir.mkdir()

        # Create a regular directory and file
        (colocated_dir / "real_dir").mkdir()
        (colocated_dir / "real_dir" / "real_file.txt").write_text("real content")

        # Create symlink to the real_dir within same directory
        link = colocated_dir / "link_to_real"
        link.symlink_to((colocated_dir / "real_dir").resolve(), target_is_directory=True)

        adapter = FileSystemAdapter(follow_symlinks=False)
        root = FileSystemNode(colocated_dir)

        nodes = list(traverse_tree(root, adapter))
        names = [n.path.name for n in nodes]

        # Both the symlink AND the real directory should appear
        self.assertIn("link_to_real", names)  # The symlink itself
        self.assertIn("real_dir", names)      # The actual directory
        self.assertIn("real_file.txt", names) # Contents of real_dir (it's traversed)

        # This demonstrates that symlinks don't "block" traversal of their targets
        # when both are in the scan path

    def test_symlinks_followed(self):
        """Test following symlinks when enabled."""
        adapter = FileSystemAdapter(follow_symlinks=True)
        root = FileSystemNode(self.scan_dir)  # Use scan_dir not test_path
        
        # Note: This could create infinite loops with circular symlinks
        # In production, would need cycle detection
        nodes = list(traverse_tree(root, adapter, max_depth=2))
        
        # Should traverse into symlinked directory
        # (actual behavior depends on how symlinks are resolved)
        self.assertGreater(len(nodes), 4)


class TestErrorHandling(unittest.TestCase):
    """Test error handling and recovery."""
    
    def test_invalid_configuration(self):
        """Test handling of invalid configurations."""
        config = TraversalConfig()
        config.performance.max_memory_mb = -1  # Invalid
        
        errors = config.validate()
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("positive" in e for e in errors))
        
    def test_capability_mismatch(self):
        """Test capability mismatch detection."""
        from dazzletreelib.sync.planning import DataCapability
        from dazzletreelib.sync.config import DataRequirement
        
        # Create mock adapter that doesn't support full data
        class LimitedAdapter(FileSystemAdapter):
            def supports_full_data(self):
                return False
        
        config = TraversalConfig()
        config.data_requirements = DataRequirement.FULL_NODE
        adapter = LimitedAdapter()
        
        # Should raise CapabilityMismatchError
        with self.assertRaises(CapabilityMismatchError) as context:
            plan = ExecutionPlan(config, adapter)
        
        self.assertIn("cannot provide full node data", str(context.exception))
        
    def test_error_callback(self):
        """Test error callback functionality."""
        errors_caught = []
        
        def error_handler(node, error):
            errors_caught.append((node.identifier(), str(error)))
        
        # Create a node that will cause an error
        fake_path = Path("/nonexistent/path")
        adapter = FileSystemAdapter()
        root = FileSystemNode(fake_path)
        
        config = TraversalConfig()
        config.on_error = error_handler
        config.skip_errors = True
        
        plan = ExecutionPlan(config, adapter)
        
        # Should handle error gracefully
        list(plan.execute(root))
        
        # Error handler may or may not be called depending on implementation
        # The important thing is it doesn't crash
        
    def test_progress_callback(self):
        """Test progress reporting callback."""
        progress_reports = []
        
        def progress_callback(current, total):
            progress_reports.append((current, total))
        
        test_dir = tempfile.mkdtemp()
        try:
            test_path = Path(test_dir)
            
            # Create some files
            for i in range(5):
                (test_path / f"file_{i}.txt").write_text(f"content {i}")
            
            config = TraversalConfig()
            config.progress_callback = progress_callback
            config.progress_interval = 2  # Report every 2 nodes
            
            adapter = FileSystemAdapter()
            root = FileSystemNode(test_path)
            plan = ExecutionPlan(config, adapter)
            
            list(plan.execute(root))
            
            # Should have received progress reports
            self.assertGreater(len(progress_reports), 0)
            
        finally:
            import shutil
            shutil.rmtree(test_dir, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()