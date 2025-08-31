"""Unit tests for traversal strategies and configuration.

Tests different traversal algorithms and configuration options,
focusing on depth filtering needed by folder-datetime-fix.
"""

import unittest
import tempfile
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dazzletreelib import (
    FileSystemNode,
    FileSystemAdapter,
    TraversalConfig,
    ExecutionPlan,
    TraversalStrategy,
    DataRequirement,
    traverse_tree,
)
from dazzletreelib.adapters.filesystem import FilteredFileSystemAdapter
from dazzletreelib.config import DepthConfig, FilterConfig, PerformanceConfig
from dazzletreelib.core.traverser import (
    BreadthFirstTraverser,
    DepthFirstPreOrderTraverser,
    DepthFirstPostOrderTraverser,
)


class TestTraversalStrategies(unittest.TestCase):
    """Test different traversal strategies."""
    
    def setUp(self):
        """Create a test tree structure."""
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        
        # Create a tree structure:
        #   root/
        #     a/
        #       a1.txt
        #       a2.txt
        #     b/
        #       b1/
        #         b1a.txt
        #       b2.txt
        #     c.txt
        
        (self.test_path / "a").mkdir()
        (self.test_path / "a" / "a1.txt").write_text("a1")
        (self.test_path / "a" / "a2.txt").write_text("a2")
        
        (self.test_path / "b").mkdir()
        (self.test_path / "b" / "b1").mkdir()
        (self.test_path / "b" / "b1" / "b1a.txt").write_text("b1a")
        (self.test_path / "b" / "b2.txt").write_text("b2")
        
        (self.test_path / "c.txt").write_text("c")
        
    def tearDown(self):
        """Clean up test directory."""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
        
    def test_breadth_first_traversal(self):
        """Test BFS traversal order."""
        adapter = FileSystemAdapter()
        traverser = BreadthFirstTraverser(adapter)
        root = FileSystemNode(self.test_path)
        
        nodes = []
        for node, depth in traverser.traverse(root):
            relative = node.path.relative_to(self.test_path) if node.path != self.test_path else Path(".")
            nodes.append((str(relative), depth))
        
        # BFS should visit all nodes at depth N before depth N+1
        # Check that all depth 0 nodes come before depth 1, etc.
        depths_seen = []
        for _, depth in nodes:
            if not depths_seen or depth != depths_seen[-1]:
                depths_seen.append(depth)
        
        # Depths should be in increasing order
        self.assertEqual(depths_seen, sorted(depths_seen))
        
    def test_depth_first_pre_order(self):
        """Test DFS pre-order traversal."""
        adapter = FileSystemAdapter()
        traverser = DepthFirstPreOrderTraverser(adapter)
        root = FileSystemNode(self.test_path)
        
        nodes = []
        for node, depth in traverser.traverse(root):
            relative = node.path.relative_to(self.test_path) if node.path != self.test_path else Path(".")
            nodes.append(str(relative))
        
        # Pre-order visits parent before children
        # Root should be first
        self.assertEqual(nodes[0], ".")
        
        # Parents should appear before their children
        a_index = nodes.index("a")
        if "a\\a1.txt" in nodes:  # Windows path
            a1_index = nodes.index("a\\a1.txt")
        else:  # Unix path
            a1_index = nodes.index("a/a1.txt")
        self.assertLess(a_index, a1_index)
        
    def test_depth_first_post_order(self):
        """Test DFS post-order traversal."""
        adapter = FileSystemAdapter()
        traverser = DepthFirstPostOrderTraverser(adapter)
        root = FileSystemNode(self.test_path)
        
        nodes = []
        for node, depth in traverser.traverse(root):
            relative = node.path.relative_to(self.test_path) if node.path != self.test_path else Path(".")
            nodes.append(str(relative))
        
        # Post-order visits children before parent
        # Root should be last
        self.assertEqual(nodes[-1], ".")
        
        # Children should appear before their parents
        if "a" in nodes and "a\\a1.txt" in nodes:  # Windows
            a_index = nodes.index("a")
            a1_index = nodes.index("a\\a1.txt")
            self.assertGreater(a_index, a1_index)
        elif "a" in nodes and "a/a1.txt" in nodes:  # Unix
            a_index = nodes.index("a")
            a1_index = nodes.index("a/a1.txt")
            self.assertGreater(a_index, a1_index)
            
    def test_max_depth_filtering(self):
        """Test maximum depth filtering."""
        adapter = FileSystemAdapter()
        traverser = BreadthFirstTraverser(adapter)
        root = FileSystemNode(self.test_path)
        
        # Traverse with max_depth=1
        nodes_depth1 = []
        for node, depth in traverser.traverse(root, max_depth=1):
            self.assertLessEqual(depth, 1)
            nodes_depth1.append(node)
        
        # Traverse with max_depth=2
        nodes_depth2 = []
        for node, depth in traverser.traverse(root, max_depth=2):
            self.assertLessEqual(depth, 2)
            nodes_depth2.append(node)
        
        # Should have more nodes with depth 2
        self.assertGreater(len(nodes_depth2), len(nodes_depth1))
        
    def test_min_depth_filtering(self):
        """Test minimum depth filtering."""
        adapter = FileSystemAdapter()
        traverser = BreadthFirstTraverser(adapter)
        root = FileSystemNode(self.test_path)
        
        # Traverse with min_depth=1 (skip root)
        nodes = []
        for node, depth in traverser.traverse(root, min_depth=1):
            self.assertGreaterEqual(depth, 1)
            nodes.append(node)
        
        # Root should not be in results
        root_in_results = any(n.path == self.test_path for n in nodes)
        self.assertFalse(root_in_results)
        
        # Should still have results
        self.assertGreater(len(nodes), 0)


class TestTraversalConfig(unittest.TestCase):
    """Test TraversalConfig and related configuration classes."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = TraversalConfig()
        
        self.assertEqual(config.strategy, TraversalStrategy.BREADTH_FIRST)
        self.assertEqual(config.data_requirements, DataRequirement.METADATA)
        self.assertEqual(config.depth.min_depth, 0)
        self.assertIsNone(config.depth.max_depth)
        self.assertTrue(config.performance.lazy_evaluation)
        
    def test_shallow_scan_config(self):
        """Test shallow scan configuration helper."""
        config = TraversalConfig.shallow_scan(max_depth=2)
        
        self.assertEqual(config.strategy, TraversalStrategy.BREADTH_FIRST)
        self.assertEqual(config.depth.max_depth, 2)
        self.assertEqual(config.data_requirements, DataRequirement.METADATA)
        self.assertTrue(config.performance.lazy_evaluation)
        
    def test_deep_scan_config(self):
        """Test deep scan configuration helper."""
        config = TraversalConfig.deep_scan()
        
        self.assertEqual(config.strategy, TraversalStrategy.DEPTH_FIRST_POST)
        self.assertIsNone(config.depth.max_depth)  # No depth limit
        self.assertEqual(config.data_requirements, DataRequirement.METADATA)
        
    def test_memory_efficient_config(self):
        """Test memory efficient configuration helper."""
        config = TraversalConfig.memory_efficient(max_memory_mb=50)
        
        self.assertEqual(config.strategy, TraversalStrategy.DEPTH_FIRST_PRE)
        self.assertEqual(config.data_requirements, DataRequirement.IDENTIFIER_ONLY)
        self.assertEqual(config.performance.max_memory_mb, 50)
        self.assertTrue(config.performance.lazy_evaluation)
        
    def test_depth_config(self):
        """Test DepthConfig functionality."""
        depth = DepthConfig(min_depth=1, max_depth=3)
        
        # Test should_yield
        self.assertFalse(depth.should_yield(0))  # Below min
        self.assertTrue(depth.should_yield(1))   # At min
        self.assertTrue(depth.should_yield(2))   # In range
        self.assertTrue(depth.should_yield(3))   # At max
        self.assertFalse(depth.should_yield(4))  # Above max
        
        # Test should_explore
        self.assertTrue(depth.should_explore(0))   # Can go deeper
        self.assertTrue(depth.should_explore(2))   # Can go deeper
        self.assertFalse(depth.should_explore(3))  # At max, don't go deeper
        
    def test_specific_depths(self):
        """Test specific depth selection."""
        depth = DepthConfig(specific_depths={0, 2, 4})
        
        # Should only yield at specific depths
        self.assertTrue(depth.should_yield(0))
        self.assertFalse(depth.should_yield(1))
        self.assertTrue(depth.should_yield(2))
        self.assertFalse(depth.should_yield(3))
        self.assertTrue(depth.should_yield(4))
        
        # Should explore if there are deeper specific depths
        self.assertTrue(depth.should_explore(1))   # Need to reach depth 2, 4
        self.assertTrue(depth.should_explore(3))   # Need to reach depth 4
        self.assertFalse(depth.should_explore(5))  # No deeper depths needed
        
    def test_filter_config(self):
        """Test FilterConfig functionality."""
        def include_txt(node):
            return node.path.suffix == '.txt'
            
        def exclude_temp(node):
            return 'temp' in str(node.path)
        
        filter_config = FilterConfig(
            include_filter=include_txt,
            exclude_filter=exclude_temp,
            prune_on_exclude=True
        )
        
        # Create mock nodes
        class MockNode:
            def __init__(self, path):
                self.path = Path(path)
        
        txt_node = MockNode("file.txt")
        py_node = MockNode("file.py")
        temp_txt = MockNode("temp.txt")
        
        # Test filtering
        self.assertTrue(filter_config.should_include(txt_node))
        self.assertFalse(filter_config.should_include(py_node))
        self.assertFalse(filter_config.should_include(temp_txt))  # Excluded
        
    def test_performance_config(self):
        """Test PerformanceConfig functionality."""
        perf = PerformanceConfig(
            max_memory_mb=100,
            max_nodes=1000,
            lazy_evaluation=True
        )
        
        # Test memory limit check
        self.assertTrue(perf.check_memory_limit(50))
        self.assertTrue(perf.check_memory_limit(100))
        self.assertFalse(perf.check_memory_limit(101))
        
        # Test node limit check
        self.assertTrue(perf.check_node_limit(999))
        self.assertTrue(perf.check_node_limit(1000))
        self.assertFalse(perf.check_node_limit(1001))
        
    def test_config_validation(self):
        """Test configuration validation."""
        # Valid config
        valid_config = TraversalConfig()
        errors = valid_config.validate()
        self.assertEqual(len(errors), 0)
        
        # Invalid config - negative depth
        invalid_config = TraversalConfig()
        invalid_config.depth.min_depth = -1
        errors = invalid_config.validate()
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("min_depth" in e for e in errors))
        
        # Invalid config - max < min depth
        invalid_config2 = TraversalConfig()
        invalid_config2.depth.min_depth = 5
        invalid_config2.depth.max_depth = 3
        errors = invalid_config2.validate()
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("less than min_depth" in e for e in errors))


class TestExecutionPlan(unittest.TestCase):
    """Test ExecutionPlan validation and execution."""
    
    def setUp(self):
        """Create test directory."""
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        
        # Create simple structure
        (self.test_path / "file1.txt").write_text("content1")
        (self.test_path / "file2.txt").write_text("content2")
        (self.test_path / "subdir").mkdir()
        (self.test_path / "subdir" / "file3.txt").write_text("content3")
        
    def tearDown(self):
        """Clean up test directory."""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
        
    def test_plan_creation(self):
        """Test creating an execution plan."""
        config = TraversalConfig.shallow_scan(max_depth=1)
        adapter = FileSystemAdapter()
        
        plan = ExecutionPlan(config, adapter)
        
        self.assertIsNotNone(plan)
        self.assertEqual(plan.config, config)
        self.assertEqual(plan.adapter, adapter)
        self.assertIsNotNone(plan.traverser)
        self.assertIsNotNone(plan.collector)
        
    def test_plan_execution(self):
        """Test executing a plan."""
        config = TraversalConfig(
            strategy=TraversalStrategy.BREADTH_FIRST,
            data_requirements=DataRequirement.METADATA
        )
        adapter = FileSystemAdapter()
        plan = ExecutionPlan(config, adapter)
        
        root = FileSystemNode(self.test_path)
        results = list(plan.execute(root))
        
        # Should have results
        self.assertGreater(len(results), 0)
        
        # Each result should be (node, data) tuple
        for node, data in results:
            self.assertIsInstance(node, FileSystemNode)
            self.assertIsInstance(data, dict)  # Metadata
            
        # Check nodes were processed
        self.assertGreater(plan.nodes_processed, 0)
        
    def test_plan_with_depth_filter(self):
        """Test plan with depth filtering."""
        config = TraversalConfig()
        config.depth.max_depth = 1
        
        adapter = FileSystemAdapter()
        plan = ExecutionPlan(config, adapter)
        
        root = FileSystemNode(self.test_path)
        results = list(plan.execute(root))
        
        # Should not include file3.txt (depth 2)
        paths = [node.path.name for node, _ in results]
        self.assertNotIn("file3.txt", paths)
        
        # Should include immediate children
        self.assertIn("file1.txt", paths)
        self.assertIn("file2.txt", paths)
        
    def test_plan_with_node_filter(self):
        """Test plan with node filtering."""
        config = TraversalConfig()
        config.filter.include_filter = lambda n: n.path.suffix == '.txt' or n.path.is_dir()
        
        adapter = FileSystemAdapter()
        plan = ExecutionPlan(config, adapter)
        
        root = FileSystemNode(self.test_path)
        results = list(plan.execute(root))
        
        # All results should be .txt files or directories
        for node, _ in results:
            is_txt = node.path.suffix == '.txt'
            is_dir = node.path.is_dir()
            self.assertTrue(is_txt or is_dir)
            
    def test_plan_summary(self):
        """Test getting plan summary."""
        config = TraversalConfig(
            strategy=TraversalStrategy.DEPTH_FIRST_POST,
            data_requirements=DataRequirement.FULL_NODE
        )
        config.depth.max_depth = 5
        
        adapter = FileSystemAdapter()
        plan = ExecutionPlan(config, adapter)
        
        summary = plan.get_summary()
        
        self.assertEqual(summary['strategy'], 'dfs_post')
        self.assertEqual(summary['data_requirements'], 'full')
        self.assertEqual(summary['max_depth'], 5)
        self.assertEqual(summary['adapter'], 'FileSystemAdapter')
        
    def test_capability_validation(self):
        """Test that plan validates adapter capabilities."""
        config = TraversalConfig()
        config.data_requirements = DataRequirement.FULL_NODE
        
        # Create a mock adapter that doesn't support full data
        class LimitedAdapter(FileSystemAdapter):
            def supports_full_data(self):
                return False
        
        adapter = LimitedAdapter()
        
        # Should raise error about capability mismatch
        with self.assertRaises(Exception) as context:
            plan = ExecutionPlan(config, adapter)
        
        self.assertIn("cannot provide full node data", str(context.exception))


class TestFolderDateTimeFixScenarios(unittest.TestCase):
    """Test scenarios specific to folder-datetime-fix use cases."""
    
    def setUp(self):
        """Create directory structure similar to what folder-datetime-fix handles."""
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        
        # Create nested folder structure
        # project/
        #   src/
        #     main.py (newest)
        #     utils/
        #       helper.py (old)
        #   tests/
        #     test.py (medium)
        #   .git/
        #     config (should be excluded)
        
        import time
        
        (self.test_path / "src").mkdir()
        (self.test_path / "src" / "utils").mkdir()
        (self.test_path / "src" / "utils" / "helper.py").write_text("old")
        
        time.sleep(0.1)
        (self.test_path / "tests").mkdir()
        (self.test_path / "tests" / "test.py").write_text("medium")
        
        time.sleep(0.1)
        (self.test_path / "src" / "main.py").write_text("newest")
        
        (self.test_path / ".git").mkdir()
        (self.test_path / ".git" / "config").write_text("git")
        
    def tearDown(self):
        """Clean up test directory."""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
        
    def test_shallow_timestamp_calculation(self):
        """Test shallow timestamp calculation (immediate children only)."""
        from dazzletreelib import collect_tree_data
        
        # Use filtered adapter to exclude .git
        adapter = FilteredFileSystemAdapter(exclude_dirs={'.git'})
        root = FileSystemNode(self.test_path)
        
        # Shallow scan - max_depth=1
        config = TraversalConfig.shallow_scan(max_depth=1)
        plan = ExecutionPlan(config, adapter)
        
        mtimes = []
        for node, metadata in plan.execute(root):
            if 'mtime' in metadata and node.path != self.test_path:
                mtimes.append(metadata['mtime'])
        
        # Should only have immediate children mtimes
        # Not the nested files
        self.assertGreater(len(mtimes), 0)
        self.assertLess(len(mtimes), 10)  # Should be just a few
        
    def test_deep_timestamp_calculation(self):
        """Test deep timestamp calculation (all descendants)."""
        # Use filtered adapter to exclude .git
        adapter = FilteredFileSystemAdapter(exclude_dirs={'.git'})
        root = FileSystemNode(self.test_path)
        
        # Deep scan - no depth limit
        config = TraversalConfig.deep_scan()
        plan = ExecutionPlan(config, adapter)
        
        all_mtimes = []
        file_mtimes = []
        
        for node, metadata in plan.execute(root):
            if 'mtime' in metadata:
                all_mtimes.append(metadata['mtime'])
                if metadata.get('is_file'):
                    file_mtimes.append(metadata['mtime'])
        
        # Should have found all files (excluding .git)
        self.assertGreater(len(file_mtimes), 2)  # At least 3 files
        
        # Maximum should be from main.py (newest)
        if file_mtimes:
            max_mtime = max(file_mtimes)
            main_py_mtime = FileSystemNode(self.test_path / "src" / "main.py").metadata()['mtime']
            self.assertAlmostEqual(max_mtime, main_py_mtime, places=2)
            
    def test_exclude_patterns(self):
        """Test excluding patterns like .git, __pycache__, etc."""
        # Common exclusions for folder-datetime-fix
        adapter = FilteredFileSystemAdapter(
            exclude_dirs={'.git', '__pycache__', 'node_modules'},
            exclude_extensions={'.pyc', '.pyo', '.pyd'}
        )
        
        root = FileSystemNode(self.test_path)
        config = TraversalConfig()
        plan = ExecutionPlan(config, adapter)
        
        paths = []
        for node, _ in plan.execute(root):
            relative = node.path.relative_to(self.test_path) if node.path != self.test_path else Path(".")
            paths.append(str(relative))
        
        # Should not include .git
        self.assertFalse(any('.git' in p for p in paths))
        
        # Should include other directories
        self.assertTrue(any('src' in p for p in paths))
        self.assertTrue(any('tests' in p for p in paths))
        
    def test_depth_to_functionality(self):
        """Test --depth-to equivalent functionality."""
        adapter = FileSystemAdapter()
        root = FileSystemNode(self.test_path)
        
        # Test different depth limits
        for max_depth in [0, 1, 2, 3]:
            config = TraversalConfig()
            config.depth.max_depth = max_depth
            
            plan = ExecutionPlan(config, adapter)
            results = list(plan.execute(root))
            
            # All results should be within depth limit
            for node, _ in results:
                # Calculate relative depth
                if node.path == self.test_path:
                    depth = 0
                else:
                    relative = node.path.relative_to(self.test_path)
                    depth = len(relative.parts)
                
                self.assertLessEqual(depth, max_depth)


if __name__ == '__main__':
    unittest.main()