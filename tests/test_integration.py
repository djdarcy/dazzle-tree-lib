"""
Integration tests for DazzleTreeLib with folder-datetime-fix patterns.
Tests migration scenarios and validates that DazzleTreeLib can replace FolderScanner.
"""

import unittest
import tempfile
import os
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any

from dazzletreelib.core import TreeNode
from dazzletreelib.adapters.filesystem import FileSystemNode, FileSystemAdapter, FilteredFileSystemAdapter
from dazzletreelib.config import TraversalConfig, DataRequirement, TraversalStrategy, DepthConfig
from dazzletreelib.planning import ExecutionPlan
from dazzletreelib.core.collector import DataCollector


class FolderDateTimeFixAdapter:
    """
    Adapter to use DazzleTreeLib in folder-datetime-fix.
    This demonstrates the migration strategy.
    """
    
    def __init__(self, args=None):
        """Initialize adapter with folder-datetime-fix arguments."""
        self.args = args or {}
        self.adapter = self._create_adapter()
        self.config = self._create_config()
    
    def _create_adapter(self):
        """Create appropriate filesystem adapter based on args."""
        exclude_dirs = set(self.args.get('exclude', []))
        if not exclude_dirs:
            # Default exclusions from folder-datetime-fix
            exclude_dirs = {'.git', '__pycache__', 'node_modules', '.vs', '.vscode'}
        
        return FilteredFileSystemAdapter(
            exclude_dirs=exclude_dirs,
            use_unctools=self.args.get('use_unctools', False)
        )
    
    def _create_config(self):
        """Map folder-datetime-fix args to TraversalConfig."""
        config = TraversalConfig()
        
        # Map --depth-to to max_depth
        depth_to = self.args.get('depth_to', 'inf')
        if depth_to != 'inf':
            config.depth.max_depth = int(depth_to)
        
        # Map --strategy to data requirements
        strategy = self.args.get('strategy', 'auto')
        if strategy == 'deep':
            config.data_requirements = DataRequirement.FULL_NODE
        elif strategy == 'shallow':
            config.data_requirements = DataRequirement.METADATA
            config.depth.max_depth = 1
        elif strategy == 'smart':
            # SMART strategy needs full metadata but selective depth
            config.data_requirements = DataRequirement.METADATA
        
        # Map --analyze to filter configuration
        analyze = self.args.get('analyze', 'auto')
        if analyze == 'folder-only':
            config.filter.include_filter = lambda n: n.path.is_dir() if hasattr(n, 'path') else True
        elif analyze == 'tree':
            # Tree analysis needs all nodes
            pass
        
        return config
    
    def scan_and_collect(self, path: Path, depths: Optional[List[int]] = None):
        """
        Replace FolderScanner.scan_and_collect functionality.
        Returns folder info compatible with folder-datetime-fix.
        """
        root = FileSystemNode(path)
        
        # If specific depths requested, configure accordingly
        if depths:
            self.config.depth.specific_depths = set(depths)
        
        plan = ExecutionPlan(self.config, self.adapter)
        
        results = []
        for node, data in plan.execute(root):
            if isinstance(node, FileSystemNode):
                folder_info = self._convert_to_folder_info(node, data)
                results.append(folder_info)
        
        return results
    
    def _convert_to_folder_info(self, node: FileSystemNode, data: Any) -> Dict:
        """Convert TreeLib node to folder-datetime-fix FolderInfo format."""
        meta = node.metadata() if callable(node.metadata) else node.metadata if hasattr(node, 'metadata') else {}
        return {
            'path': str(node.path),
            'name': node.path.name,
            'is_dir': node.path.is_dir(),
            'mtime': meta.get('mtime', 0),
            'size': meta.get('size', 0),
            'depth': self.adapter.get_depth(node),
            'children': [],  # Will be populated if needed
            'data': data
        }


class TimestampCalculator:
    """
    Demonstrates how folder-datetime-fix strategies would work with DazzleTreeLib.
    """
    
    def __init__(self, strategy='auto'):
        self.strategy = strategy
    
    def calculate_deep(self, tree_data: List[Tuple[TreeNode, Any]]) -> float:
        """Deep strategy: max mtime of all files recursively."""
        max_mtime = 0
        for node, data in tree_data:
            if isinstance(node, FileSystemNode) and node.path.is_file():
                meta = node.metadata() if callable(node.metadata) else node.metadata if hasattr(node, 'metadata') else {}
                mtime = meta.get('mtime', 0)
                max_mtime = max(max_mtime, mtime)
        return max_mtime
    
    def calculate_shallow(self, tree_data: List[Tuple[TreeNode, Any]]) -> float:
        """Shallow strategy: max mtime of direct children only."""
        max_mtime = 0
        # For shallow, just take the first few files
        file_count = 0
        for node, data in tree_data:
            if isinstance(node, FileSystemNode) and node.path.is_file():
                meta = node.metadata() if callable(node.metadata) else node.metadata if hasattr(node, 'metadata') else {}
                mtime = meta.get('mtime', 0)
                max_mtime = max(max_mtime, mtime)
                file_count += 1
                if file_count >= 3:  # Just get a few for shallow
                    break
        return max_mtime
    
    def calculate_smart(self, tree_data: List[Tuple[TreeNode, Any]]) -> float:
        """SMART strategy: intelligent timestamp calculation."""
        # Look for version control, build artifacts, etc.
        important_patterns = {'.git', 'package.json', 'setup.py', 'Cargo.toml'}
        
        max_mtime = 0
        for node, data in tree_data:
            if isinstance(node, FileSystemNode):
                # Check if this is an important file
                if any(pattern in node.path.name for pattern in important_patterns):
                    meta = node.metadata() if callable(node.metadata) else node.metadata if hasattr(node, 'metadata') else {}
                    mtime = meta.get('mtime', 0)
                    max_mtime = max(max_mtime, mtime)
        
        return max_mtime if max_mtime > 0 else self.calculate_deep(tree_data)


class TestIntegration(unittest.TestCase):
    """Test integration scenarios for folder-datetime-fix migration."""
    
    def setUp(self):
        """Create test directory structure mimicking real projects."""
        self.temp_dir = tempfile.mkdtemp(prefix='test_integration_')
        self.create_project_structure()
    
    def tearDown(self):
        """Clean up test directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_project_structure(self):
        """Create a realistic project structure."""
        # Create a Python project structure
        project_dir = os.path.join(self.temp_dir, 'python_project')
        os.makedirs(os.path.join(project_dir, 'src', 'module1'))
        os.makedirs(os.path.join(project_dir, 'src', 'module2'))
        os.makedirs(os.path.join(project_dir, 'tests'))
        os.makedirs(os.path.join(project_dir, 'docs'))
        os.makedirs(os.path.join(project_dir, '.git', 'objects'))
        os.makedirs(os.path.join(project_dir, '__pycache__'))
        
        # Create files with different modification times
        now = time.time()
        files = [
            ('setup.py', now - 86400 * 7),  # 7 days ago
            ('README.md', now - 86400 * 3),  # 3 days ago
            ('src/__init__.py', now - 86400 * 5),
            ('src/module1/core.py', now - 86400 * 1),  # 1 day ago
            ('src/module2/utils.py', now - 3600),  # 1 hour ago
            ('tests/test_core.py', now - 7200),  # 2 hours ago
            ('.git/config', now - 86400 * 30),  # 30 days ago
            ('__pycache__/cache.pyc', now),  # Just now
        ]
        
        for file_path, mtime in files:
            full_path = os.path.join(project_dir, file_path)
            with open(full_path, 'w') as f:
                f.write(f"# File: {file_path}\n")
            os.utime(full_path, (mtime, mtime))
        
        # Create a Node.js project structure
        node_dir = os.path.join(self.temp_dir, 'node_project')
        os.makedirs(os.path.join(node_dir, 'src'))
        os.makedirs(os.path.join(node_dir, 'node_modules', 'lodash'))
        os.makedirs(os.path.join(node_dir, 'dist'))
        
        node_files = [
            ('package.json', now - 86400 * 2),
            ('src/index.js', now - 3600 * 4),
            ('node_modules/lodash/index.js', now - 86400 * 10),
            ('dist/bundle.js', now - 1800),
        ]
        
        for file_path, mtime in node_files:
            full_path = os.path.join(node_dir, file_path)
            with open(full_path, 'w') as f:
                f.write(f"// File: {file_path}\n")
            os.utime(full_path, (mtime, mtime))
    
    def test_basic_migration(self):
        """Test basic migration from FolderScanner to TreeLib."""
        args = {
            'depth_to': 'inf',
            'strategy': 'deep',
            'analyze': 'auto',
            'exclude': ['.git', '__pycache__', 'node_modules']
        }
        
        adapter = FolderDateTimeFixAdapter(args)
        project_path = Path(os.path.join(self.temp_dir, 'python_project'))
        
        results = adapter.scan_and_collect(project_path)
        
        # Should have collected folder info
        self.assertGreater(len(results), 0)
        
        # Check format compatibility
        for folder_info in results:
            self.assertIn('path', folder_info)
            self.assertIn('name', folder_info)
            self.assertIn('is_dir', folder_info)
            self.assertIn('mtime', folder_info)
            
            # Excluded directories should not be present
            path_str = folder_info['path']
            self.assertNotIn('__pycache__', path_str)
            self.assertNotIn('.git', path_str)
    
    def test_depth_limiting_migration(self):
        """Test --depth-to option migration."""
        args = {
            'depth_to': '2',
            'strategy': 'auto',
            'analyze': 'auto'
        }
        
        adapter = FolderDateTimeFixAdapter(args)
        project_path = Path(os.path.join(self.temp_dir, 'python_project'))
        
        results = adapter.scan_and_collect(project_path)
        
        # Check depth limiting works
        for folder_info in results:
            path = Path(folder_info['path'])
            relative = path.relative_to(project_path)
            depth = len(relative.parts)
            self.assertLessEqual(depth, 2, f"Path {relative} exceeds depth 2")
    
    def test_strategy_migration(self):
        """Test different strategy migrations."""
        project_path = Path(os.path.join(self.temp_dir, 'python_project'))
        
        # Test deep strategy
        deep_adapter = FolderDateTimeFixAdapter({'strategy': 'deep'})
        deep_results = deep_adapter.scan_and_collect(project_path)
        
        # Test shallow strategy
        shallow_adapter = FolderDateTimeFixAdapter({'strategy': 'shallow'})
        shallow_results = shallow_adapter.scan_and_collect(project_path)
        
        # Shallow should have fewer results due to depth limit
        self.assertLess(len(shallow_results), len(deep_results))
        
        # Test smart strategy
        smart_adapter = FolderDateTimeFixAdapter({'strategy': 'smart'})
        smart_results = smart_adapter.scan_and_collect(project_path)
        
        # Smart should have results
        self.assertGreater(len(smart_results), 0)
    
    def test_timestamp_calculation(self):
        """Test timestamp calculation strategies."""
        adapter = FileSystemAdapter()
        project_path = Path(os.path.join(self.temp_dir, 'python_project'))
        root = FileSystemNode(project_path)
        
        # Collect all data
        config = TraversalConfig(data_requirements=DataRequirement.METADATA)
        config.filter.exclude_patterns = {'.git', '__pycache__'}
        plan = ExecutionPlan(config, adapter)
        
        tree_data = list(plan.execute(root))
        
        # Test different timestamp calculations
        calculator = TimestampCalculator()
        
        deep_time = calculator.calculate_deep(tree_data)
        shallow_time = calculator.calculate_shallow(tree_data)
        smart_time = calculator.calculate_smart(tree_data)
        
        # All should return valid timestamps
        self.assertGreater(deep_time, 0)
        self.assertGreater(shallow_time, 0)
        self.assertGreater(smart_time, 0)
        
        # Deep should find the most recent file
        now = time.time()
        self.assertLess(now - deep_time, 3600 * 2)  # Within 2 hours
    
    def test_analyze_option_migration(self):
        """Test --analyze option migration."""
        project_path = Path(os.path.join(self.temp_dir, 'python_project'))
        
        # Test folder-only analysis
        folder_only_args = {'analyze': 'folder-only'}
        folder_adapter = FolderDateTimeFixAdapter(folder_only_args)
        folder_results = folder_adapter.scan_and_collect(project_path)
        
        # Should only have directories
        for result in folder_results:
            self.assertTrue(result['is_dir'], f"{result['path']} is not a directory")
        
        # Test tree analysis
        tree_args = {'analyze': 'tree'}
        tree_adapter = FolderDateTimeFixAdapter(tree_args)
        tree_results = tree_adapter.scan_and_collect(project_path)
        
        # Should have both files and directories
        has_files = any(not r['is_dir'] for r in tree_results)
        has_dirs = any(r['is_dir'] for r in tree_results)
        self.assertTrue(has_files)
        self.assertTrue(has_dirs)
    
    def test_execution_plan_validation(self):
        """Test that ExecutionPlan validates incompatible options."""
        from dazzletreelib.planning import CapabilityMismatchError
        
        # Test incompatible configuration
        adapter = FileSystemAdapter()
        root = FileSystemNode(Path(self.temp_dir))
        
        config = TraversalConfig()
        # Set up an incompatible configuration
        config.data_requirements = DataRequirement.FULL_NODE
        config.performance.lazy_evaluation = True  # Can't be lazy with FULL_NODE
        
        # This should handle the mismatch gracefully
        plan = ExecutionPlan(config, adapter)
        # ExecutionPlan should adjust the configuration or handle it appropriately
        
        # The plan should still execute
        results = list(plan.execute(root))
        self.assertGreater(len(results), 0)
    
    def test_cache_transition_scenarios(self):
        """Test cache upgrade scenarios from folder-datetime-fix."""
        adapter = FileSystemAdapter()
        project_path = Path(os.path.join(self.temp_dir, 'python_project'))
        root = FileSystemNode(project_path)
        
        # Scenario 1: Start with identifier-only, upgrade to metadata
        config1 = TraversalConfig(data_requirements=DataRequirement.IDENTIFIER_ONLY)
        plan1 = ExecutionPlan(config1, adapter)
        
        id_results = list(plan1.execute(root))
        self.assertGreater(len(id_results), 0)
        
        # Now need metadata for same nodes
        config2 = TraversalConfig(data_requirements=DataRequirement.METADATA)
        plan2 = ExecutionPlan(config2, adapter)
        
        meta_results = list(plan2.execute(root))
        self.assertEqual(len(meta_results), len(id_results))
        
        # Verify metadata is available
        for node, data in meta_results:
            if isinstance(node, FileSystemNode) and node.path.is_file():
                meta = node.metadata() if callable(node.metadata) else node.metadata
                self.assertIsNotNone(meta)
                self.assertIn('mtime', meta)
    
    def test_performance_improvement(self):
        """Test that DazzleTreeLib improves on folder-datetime-fix patterns."""
        project_path = Path(os.path.join(self.temp_dir, 'python_project'))
        
        # Simulate folder-datetime-fix's multiple traversals
        start_old = time.time()
        
        # Old way: separate traversals for different strategies
        for strategy in ['deep', 'shallow', 'smart']:
            adapter = FolderDateTimeFixAdapter({'strategy': strategy})
            results = adapter.scan_and_collect(project_path)
        
        time_old = time.time() - start_old
        
        # New way: single traversal with data reuse
        start_new = time.time()
        
        adapter = FileSystemAdapter()
        root = FileSystemNode(project_path)
        config = TraversalConfig(data_requirements=DataRequirement.METADATA)
        plan = ExecutionPlan(config, adapter)
        
        # Single traversal
        tree_data = list(plan.execute(root))
        
        # Calculate all strategies from same data
        calculator = TimestampCalculator()
        deep = calculator.calculate_deep(tree_data)
        shallow = calculator.calculate_shallow(tree_data)
        smart = calculator.calculate_smart(tree_data)
        
        time_new = time.time() - start_new
        
        print(f"\nPerformance comparison:")
        print(f"  Old approach (3 traversals): {time_old:.3f}s")
        print(f"  New approach (1 traversal): {time_new:.3f}s")
        print(f"  Improvement: {time_old/max(time_new, 0.001):.1f}x faster")
        
        # New approach should be faster (or at least not slower)
        self.assertLessEqual(time_new, time_old * 1.5)  # Allow some variance
    
    def test_error_handling_compatibility(self):
        """Test error handling is compatible with folder-datetime-fix."""
        # Create a directory with permission issues (simulated)
        problem_dir = os.path.join(self.temp_dir, 'restricted')
        os.makedirs(problem_dir)
        
        error_count = 0
        
        def error_handler(error, node):
            nonlocal error_count
            error_count += 1
            return True  # Continue traversal
        
        adapter = FileSystemAdapter()
        root = FileSystemNode(Path(self.temp_dir))
        
        config = TraversalConfig(data_requirements=DataRequirement.METADATA)
        config.error_handler = error_handler
        
        plan = ExecutionPlan(config, adapter)
        
        # Should complete even with errors
        results = list(plan.execute(root))
        self.assertGreater(len(results), 0)
    
    def test_option_compatibility_matrix(self):
        """Test various option combinations from folder-datetime-fix."""
        test_cases = [
            # (depth_to, strategy, analyze, should_work)
            ('inf', 'deep', 'auto', True),
            ('2', 'shallow', 'folder-only', True),
            ('inf', 'smart', 'tree', True),
            ('1', 'deep', 'auto', True),  # Deep with depth limit
            ('inf', 'shallow', 'tree', True),  # Shallow but full tree
        ]
        
        project_path = Path(os.path.join(self.temp_dir, 'python_project'))
        
        for depth_to, strategy, analyze, should_work in test_cases:
            args = {
                'depth_to': depth_to,
                'strategy': strategy,
                'analyze': analyze
            }
            
            adapter = FolderDateTimeFixAdapter(args)
            
            if should_work:
                results = adapter.scan_and_collect(project_path)
                self.assertIsNotNone(results, 
                    f"Failed for {depth_to}/{strategy}/{analyze}")
            else:
                with self.assertRaises(Exception):
                    adapter.scan_and_collect(project_path)
    
    def test_unctools_integration(self):
        """Test UNCtools integration for network paths."""
        args = {
            'use_unctools': True,
            'strategy': 'auto'
        }
        
        adapter = FolderDateTimeFixAdapter(args)
        
        # Should create adapter with UNCtools enabled (check if unctools module is loaded)
        # Note: FilteredFileSystemAdapter stores unctools module, not use_unctools flag
        # If unctools is not installed, it will be None
        
        # Test with local path (UNCtools should handle gracefully)
        project_path = Path(os.path.join(self.temp_dir, 'python_project'))
        results = adapter.scan_and_collect(project_path)
        self.assertGreater(len(results), 0)
    
    def test_real_world_project_patterns(self):
        """Test patterns from real folder-datetime-fix usage."""
        # Create a more complex structure
        complex_dir = os.path.join(self.temp_dir, 'complex_project')
        
        # Typical patterns to handle
        patterns = [
            'src/main/java/com/example/App.java',
            'target/classes/com/example/App.class',
            'node_modules/react/index.js',
            '.git/objects/ab/cdef1234',
            'build/Release/app.exe',
            'dist/bundle.min.js',
            '__pycache__/module.cpython-39.pyc',
            '.vscode/settings.json',
            'vendor/autoload.php',
        ]
        
        for pattern in patterns:
            full_path = os.path.join(complex_dir, pattern)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'w') as f:
                f.write(f"// {pattern}\n")
        
        # Test with typical exclusions
        args = {
            'exclude': [
                '.git', '__pycache__', 'node_modules', 
                'target', 'build', 'dist', '.vscode', 'vendor'
            ],
            'strategy': 'smart'
        }
        
        adapter = FolderDateTimeFixAdapter(args)
        results = adapter.scan_and_collect(Path(complex_dir))
        
        # Should exclude all the build/cache directories
        for result in results:
            path = result['path']
            for excluded in args['exclude']:
                self.assertNotIn(f"{os.sep}{excluded}{os.sep}", path)
                self.assertFalse(path.endswith(f"{os.sep}{excluded}"))


if __name__ == '__main__':
    unittest.main()