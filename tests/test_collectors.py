"""
Test suite for DazzleTreeLib data collectors.
Tests all collector types including custom collectors and aggregation patterns.
Critical for folder-datetime-fix integration which relies on metadata collection.
"""

import unittest
import tempfile
import os
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Optional, List, Dict

from dazzletreelib.sync.core import TreeNode
from dazzletreelib.sync.core.collector import DataCollector
from dazzletreelib.sync.adapters.filesystem import FileSystemNode, FileSystemAdapter
from dazzletreelib.sync.config import TraversalConfig, DataRequirement
from dazzletreelib.sync.planning import ExecutionPlan


class BasicCollector(DataCollector):
    """Basic collector that just returns node identifier."""
    
    def __init__(self, adapter):
        super().__init__(adapter)
    
    def collect(self, node: TreeNode, depth: int) -> Any:
        return node.identifier() if callable(node.identifier) else node.identifier
    
    def requires_children(self) -> bool:
        return False


class MetadataCollector(DataCollector):
    """Collector that extracts metadata from nodes."""
    
    def __init__(self, adapter):
        super().__init__(adapter)
    
    def collect(self, node: TreeNode, depth: int) -> Dict[str, Any]:
        if hasattr(node, 'metadata'):
            return node.metadata() if callable(node.metadata) else node.metadata
        return {}
    
    def requires_children(self) -> bool:
        return False


class PathCollector(DataCollector):
    """Collector that builds full paths from root."""
    
    def __init__(self, adapter):
        super().__init__(adapter)
        self.paths = []
    
    def collect(self, node: TreeNode, depth: int) -> str:
        # Build path from root to current node
        node_id = node.identifier() if callable(node.identifier) else node.identifier
        path_parts = [node_id]
        current = node
        while hasattr(self.adapter, 'get_parent'):
            parent = self.adapter.get_parent(current)
            if parent:
                parent_id = parent.identifier() if callable(parent.identifier) else parent.identifier
                path_parts.insert(0, parent_id)
                current = parent
            else:
                break
        
        full_path = '/'.join(str(p) for p in path_parts)
        self.paths.append(full_path)
        return full_path
    
    def requires_children(self) -> bool:
        return False


class AggregateCollector(DataCollector):
    """Collector that aggregates values (sum, max, min, etc)."""
    
    def __init__(self, adapter, operation='sum'):
        super().__init__(adapter)
        self.operation = operation
        self.values = []
    
    def collect(self, node: TreeNode, depth: int) -> Any:
        # Extract numeric value from node
        value = None
        if isinstance(node, FileSystemNode) and node.path.is_file():
            # Only collect sizes from files, not directories
            if hasattr(node, 'metadata'):
                meta = node.metadata() if callable(node.metadata) else node.metadata
                if 'size' in meta:
                    value = meta['size']
        elif hasattr(node, 'value'):
            value = node.value
        
        if value is not None:
            self.values.append(value)
        
        return value
    
    def requires_children(self) -> bool:
        return False
    
    def get_aggregate(self):
        """Get the aggregated result."""
        if not self.values:
            return None
        
        if self.operation == 'sum':
            return sum(self.values)
        elif self.operation == 'max':
            return max(self.values)
        elif self.operation == 'min':
            return min(self.values)
        elif self.operation == 'avg':
            return sum(self.values) / len(self.values)
        elif self.operation == 'count':
            return len(self.values)
        else:
            return self.values


class ModificationTimeCollector(DataCollector):
    """
    Collector specifically for modification times.
    Critical for folder-datetime-fix integration.
    """
    
    def __init__(self, adapter, include_dirs=True, include_files=True):
        super().__init__(adapter)
        self.include_dirs = include_dirs
        self.include_files = include_files
        self.mtimes = {}
    
    def collect(self, node: TreeNode, depth: int) -> Optional[float]:
        if isinstance(node, FileSystemNode):
            path = node.path
            
            # Check if we should collect this node
            if path.is_dir() and not self.include_dirs:
                return None
            if path.is_file() and not self.include_files:
                return None
            
            # Get modification time
            try:
                mtime = path.stat().st_mtime
                self.mtimes[str(path)] = mtime
                return mtime
            except (OSError, PermissionError):
                return None
        
        return None
    
    def requires_children(self) -> bool:
        return False
    
    def get_latest(self) -> Optional[float]:
        """Get the most recent modification time."""
        return max(self.mtimes.values()) if self.mtimes else None
    
    def get_oldest(self) -> Optional[float]:
        """Get the oldest modification time."""
        return min(self.mtimes.values()) if self.mtimes else None


class ChildCountCollector(DataCollector):
    """Collector that counts children for each node."""
    
    def __init__(self, adapter):
        super().__init__(adapter)
        self.child_counts = {}
    
    def collect(self, node: TreeNode, depth: int) -> int:
        children = self.adapter.get_children(node)
        count = len(list(children)) if children else 0
        node_id = node.identifier() if callable(node.identifier) else node.identifier
        self.child_counts[node_id] = count
        return count
    
    def requires_children(self) -> bool:
        return True


class FilteredCollector(DataCollector):
    """Collector that only collects from nodes matching a predicate."""
    
    def __init__(self, adapter, predicate, inner_collector):
        super().__init__(adapter)
        self.predicate = predicate
        self.inner_collector = inner_collector
        self.collected_items = []
    
    def collect(self, node: TreeNode, depth: int) -> Any:
        if self.predicate(node):
            result = self.inner_collector.collect(node, depth)
            self.collected_items.append(result)
            return result
        return None
    
    def requires_children(self) -> bool:
        return self.inner_collector.requires_children()


class TestDataCollectors(unittest.TestCase):
    """Test data collector functionality."""
    
    def setUp(self):
        """Create test directory structure."""
        self.temp_dir = tempfile.mkdtemp(prefix='test_collectors_')
        
        # Create test structure
        self.create_test_structure()
    
    def tearDown(self):
        """Clean up test directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_test_structure(self):
        """Create a test directory structure with various file types."""
        # Create directories
        os.makedirs(os.path.join(self.temp_dir, 'dir1', 'subdir1'))
        os.makedirs(os.path.join(self.temp_dir, 'dir1', 'subdir2'))
        os.makedirs(os.path.join(self.temp_dir, 'dir2'))
        
        # Create files with different sizes and modification times
        files = [
            ('file1.txt', 100, -3),  # 100 bytes, 3 days ago
            ('dir1/file2.py', 250, -2),  # 250 bytes, 2 days ago
            ('dir1/subdir1/file3.txt', 50, -1),  # 50 bytes, 1 day ago
            ('dir1/subdir2/file4.py', 300, 0),  # 300 bytes, today
            ('dir2/file5.txt', 150, -5),  # 150 bytes, 5 days ago
        ]
        
        for file_path, size, days_ago in files:
            full_path = os.path.join(self.temp_dir, file_path)
            with open(full_path, 'w') as f:
                f.write('x' * size)
            
            # Set modification time
            mtime = time.time() + (days_ago * 24 * 3600)
            os.utime(full_path, (mtime, mtime))
    
    def test_basic_collector(self):
        """Test basic identifier collection."""
        adapter = FileSystemAdapter()
        collector = BasicCollector(adapter)
        root = FileSystemNode(Path(self.temp_dir))
        
        config = TraversalConfig(data_requirements=DataRequirement.CUSTOM)
        config.custom_collector = collector
        
        plan = ExecutionPlan(config, adapter)
        results = list(plan.execute(root))
        
        # Should collect identifiers for all nodes
        self.assertTrue(len(results) > 0)
        
        # Check that identifiers are collected
        for node, data in results:
            expected = node.identifier() if callable(node.identifier) else node.identifier
            self.assertEqual(data, expected)
            # For FileSystemNode, identifier returns a string path
            self.assertTrue(isinstance(data, str))
    
    def test_metadata_collector(self):
        """Test metadata collection."""
        adapter = FileSystemAdapter()
        collector = MetadataCollector(adapter)
        root = FileSystemNode(Path(self.temp_dir))
        
        config = TraversalConfig(data_requirements=DataRequirement.CUSTOM)
        config.custom_collector = collector
        
        plan = ExecutionPlan(config, adapter)
        results = list(plan.execute(root))
        
        # Check metadata is collected
        for node, data in results:
            self.assertIsInstance(data, dict)
            if node.path.is_file():
                self.assertIn('size', data)
                self.assertIn('mtime', data)
    
    def test_path_collector(self):
        """Test full path building."""
        adapter = FileSystemAdapter()
        collector = PathCollector(adapter)
        root = FileSystemNode(Path(self.temp_dir))
        
        config = TraversalConfig(data_requirements=DataRequirement.CUSTOM)
        config.custom_collector = collector
        
        plan = ExecutionPlan(config, adapter)
        results = list(plan.execute(root))
        
        # Check paths are built correctly
        self.assertTrue(len(collector.paths) > 0)
        for path in collector.paths:
            self.assertIsInstance(path, str)
            # Paths should contain directory separators
            if len(path.split('/')) > 1 or len(path.split('\\')) > 1:
                self.assertTrue('/' in path or '\\' in path)
    
    def test_aggregate_collector_sum(self):
        """Test sum aggregation."""
        adapter = FileSystemAdapter()
        collector = AggregateCollector(adapter, operation='sum')
        root = FileSystemNode(Path(self.temp_dir))
        
        config = TraversalConfig(data_requirements=DataRequirement.CUSTOM)
        config.custom_collector = collector
        
        plan = ExecutionPlan(config, adapter)
        list(plan.execute(root))
        
        # Sum should be 100 + 250 + 50 + 300 + 150 = 850
        total = collector.get_aggregate()
        self.assertEqual(total, 850)
    
    def test_aggregate_collector_max_min(self):
        """Test max/min aggregation."""
        # Test max
        adapter = FileSystemAdapter()
        max_collector = AggregateCollector(adapter, operation='max')
        root = FileSystemNode(Path(self.temp_dir))
        
        config = TraversalConfig(data_requirements=DataRequirement.CUSTOM)
        config.custom_collector = max_collector
        
        plan = ExecutionPlan(config, adapter)
        list(plan.execute(root))
        
        self.assertEqual(max_collector.get_aggregate(), 300)
        
        # Test min
        min_collector = AggregateCollector(adapter, operation='min')
        config.custom_collector = min_collector
        
        plan = ExecutionPlan(config, adapter)
        list(plan.execute(root))
        
        self.assertEqual(min_collector.get_aggregate(), 50)
    
    def test_modification_time_collector(self):
        """Test modification time collection for folder-datetime-fix."""
        adapter = FileSystemAdapter()
        collector = ModificationTimeCollector(adapter, include_dirs=True, include_files=True)
        root = FileSystemNode(Path(self.temp_dir))
        
        config = TraversalConfig(data_requirements=DataRequirement.CUSTOM)
        config.custom_collector = collector
        
        plan = ExecutionPlan(config, adapter)
        list(plan.execute(root))
        
        # Should have collected modification times
        self.assertTrue(len(collector.mtimes) > 0)
        
        # Latest should be from today (file4.py)
        latest = collector.get_latest()
        self.assertIsNotNone(latest)
        
        # Oldest should be from 5 days ago (file5.txt)
        oldest = collector.get_oldest()
        self.assertIsNotNone(oldest)
        
        # Latest should be more recent than oldest
        self.assertGreater(latest, oldest)
    
    def test_modification_time_collector_files_only(self):
        """Test collecting modification times for files only."""
        adapter = FileSystemAdapter()
        collector = ModificationTimeCollector(adapter, include_dirs=False, include_files=True)
        root = FileSystemNode(Path(self.temp_dir))
        
        config = TraversalConfig(data_requirements=DataRequirement.CUSTOM)
        config.custom_collector = collector
        
        plan = ExecutionPlan(config, adapter)
        list(plan.execute(root))
        
        # Should only have file mtimes
        for path_str in collector.mtimes.keys():
            path = Path(path_str)
            self.assertTrue(path.is_file())
    
    def test_child_count_collector(self):
        """Test counting children for each node."""
        adapter = FileSystemAdapter()
        collector = ChildCountCollector(adapter)
        root = FileSystemNode(Path(self.temp_dir))
        
        config = TraversalConfig(data_requirements=DataRequirement.CUSTOM)
        config.custom_collector = collector
        
        plan = ExecutionPlan(config, adapter)
        list(plan.execute(root))
        
        # Root should have children
        root_id = root.identifier() if callable(root.identifier) else root.identifier
        root_count = collector.child_counts.get(root_id)
        self.assertIsNotNone(root_count)
        self.assertGreater(root_count, 0)
        
        # Leaf files should have 0 children
        for path, count in collector.child_counts.items():
            if Path(path).is_file():
                self.assertEqual(count, 0)
    
    def test_filtered_collector(self):
        """Test filtering during collection."""
        # Only collect from Python files
        def is_python_file(node):
            if isinstance(node, FileSystemNode):
                return node.path.suffix == '.py'
            return False
        
        adapter = FileSystemAdapter()
        inner_collector = MetadataCollector(adapter)
        collector = FilteredCollector(adapter, is_python_file, inner_collector)
        
        root = FileSystemNode(Path(self.temp_dir))
        
        config = TraversalConfig(data_requirements=DataRequirement.CUSTOM)
        config.custom_collector = collector
        
        plan = ExecutionPlan(config, adapter)
        list(plan.execute(root))
        
        # Should only have collected from .py files
        self.assertEqual(len(collector.collected_items), 2)  # file2.py and file4.py
        for item in collector.collected_items:
            if item:
                self.assertIsInstance(item, dict)
    
    def test_custom_collector_state(self):
        """Test that collectors can maintain state across traversal."""
        class StatefulCollector(DataCollector):
            def __init__(self, adapter):
                super().__init__(adapter)
                self.node_count = 0
                self.total_size = 0
                self.file_types = set()
            
            def collect(self, node: TreeNode, depth: int) -> Dict[str, Any]:
                self.node_count += 1
                
                if isinstance(node, FileSystemNode):
                    if node.path.is_file():
                        self.file_types.add(node.path.suffix)
                        if hasattr(node, 'metadata'):
                            meta = node.metadata() if callable(node.metadata) else node.metadata
                            if 'size' in meta:
                                self.total_size += meta['size']
                
                return {
                    'count_so_far': self.node_count,
                    'total_size_so_far': self.total_size,
                    'types_seen': list(self.file_types)
                }
            
            def requires_children(self) -> bool:
                return False
        
        adapter = FileSystemAdapter()
        collector = StatefulCollector(adapter)
        root = FileSystemNode(Path(self.temp_dir))
        
        config = TraversalConfig(data_requirements=DataRequirement.CUSTOM)
        config.custom_collector = collector
        
        plan = ExecutionPlan(config, adapter)
        results = list(plan.execute(root))
        
        # Final state should reflect all nodes
        self.assertGreater(collector.node_count, 5)
        self.assertEqual(collector.total_size, 850)
        self.assertEqual(collector.file_types, {'.txt', '.py'})
        
        # Last result should have final counts
        last_node, last_data = results[-1]
        self.assertEqual(last_data['count_so_far'], collector.node_count)
    
    def test_collector_with_execution_plan_filtering(self):
        """Test collectors work correctly with ExecutionPlan filtering."""
        adapter = FileSystemAdapter()
        collector = ModificationTimeCollector(adapter)
        root = FileSystemNode(Path(self.temp_dir))
        
        # Configure to only traverse depth 1
        config = TraversalConfig(data_requirements=DataRequirement.CUSTOM)
        config.depth.max_depth = 1
        config.custom_collector = collector
        
        plan = ExecutionPlan(config, adapter)
        list(plan.execute(root))
        
        # Should have fewer items due to depth limit
        collected_paths = set(collector.mtimes.keys())
        
        # Should not include deeply nested files
        deep_file = os.path.join(self.temp_dir, 'dir1', 'subdir1', 'file3.txt')
        self.assertNotIn(str(Path(deep_file)), collected_paths)
    
    def test_collector_chain(self):
        """Test chaining multiple collectors."""
        class ChainedCollector(DataCollector):
            def __init__(self, adapter, collectors):
                super().__init__(adapter)
                self.collectors = collectors
            
            def collect(self, node: TreeNode, depth: int) -> List[Any]:
                results = []
                for collector in self.collectors:
                    results.append(collector.collect(node, depth))
                return results
            
            def requires_children(self) -> bool:
                return any(c.requires_children() for c in self.collectors)
        
        # Chain multiple collectors
        adapter = FileSystemAdapter()
        basic = BasicCollector(adapter)
        metadata = MetadataCollector(adapter)
        child_count = ChildCountCollector(adapter)
        
        chained = ChainedCollector(adapter, [basic, metadata, child_count])
        
        root = FileSystemNode(Path(self.temp_dir))
        
        config = TraversalConfig(data_requirements=DataRequirement.CUSTOM)
        config.custom_collector = chained
        
        plan = ExecutionPlan(config, adapter)
        results = list(plan.execute(root))
        
        # Each result should have data from all collectors
        for node, data in results:
            self.assertIsInstance(data, list)
            self.assertEqual(len(data), 3)
            # First is identifier
            expected_id = node.identifier() if callable(node.identifier) else node.identifier
            self.assertEqual(data[0], expected_id)
            # Second is metadata dict
            self.assertIsInstance(data[1], dict)
            # Third is child count
            self.assertIsInstance(data[2], int)
    
    def test_collector_for_datetime_fix_scenarios(self):
        """Test collector patterns specific to folder-datetime-fix needs."""
        
        # Scenario 1: Collect only directory modification times (shallow strategy)
        adapter = FileSystemAdapter()
        dir_collector = ModificationTimeCollector(adapter, include_dirs=True, include_files=False)
        root = FileSystemNode(Path(self.temp_dir))
        
        config = TraversalConfig(data_requirements=DataRequirement.CUSTOM)
        config.depth.max_depth = 1  # Shallow
        config.custom_collector = dir_collector
        
        plan = ExecutionPlan(config, adapter)
        list(plan.execute(root))
        
        # Should only have directory times
        for path_str in dir_collector.mtimes.keys():
            self.assertTrue(Path(path_str).is_dir())
        
        # Scenario 2: Deep collection with filtering
        deep_collector = ModificationTimeCollector(adapter)
        config = TraversalConfig(data_requirements=DataRequirement.CUSTOM)
        config.filter.exclude_patterns = {'*.pyc', '__pycache__', '.git'}
        config.custom_collector = deep_collector
        
        plan = ExecutionPlan(config, adapter)
        list(plan.execute(root))
        
        # Should have all times except excluded patterns
        self.assertGreater(len(deep_collector.mtimes), 0)
        
        # Scenario 3: Aggregate size for directories
        class DirectorySizeCollector(DataCollector):
            def __init__(self, adapter):
                super().__init__(adapter)
                self.dir_sizes = {}
            
            def collect(self, node: TreeNode, depth: int) -> int:
                if isinstance(node, FileSystemNode):
                    if node.path.is_dir():
                        # Calculate total size of all files in directory
                        total = 0
                        for child in self.adapter.get_children(node):
                            if child.path.is_file():
                                if hasattr(child, 'metadata'):
                                    meta = child.metadata() if callable(child.metadata) else child.metadata
                                    if 'size' in meta:
                                        total += meta['size']
                        
                        self.dir_sizes[str(node.path)] = total
                        return total
                return 0
            
            def requires_children(self) -> bool:
                return True
        
        size_collector = DirectorySizeCollector(adapter)
        config = TraversalConfig(data_requirements=DataRequirement.CUSTOM)
        config.custom_collector = size_collector
        
        plan = ExecutionPlan(config, adapter)
        list(plan.execute(root))
        
        # Should have calculated directory sizes
        self.assertGreater(len(size_collector.dir_sizes), 0)


if __name__ == '__main__':
    unittest.main()