"""
Test suite for DazzleTreeLib performance validation.
Tests memory usage, traversal speed, and scalability with large trees.
"""

import unittest
import tempfile
import os
import time
import sys
import gc
import psutil
from pathlib import Path
from typing import Dict, Any, List
import random
import string

from dazzletreelib.core import TreeNode
from dazzletreelib.adapters.filesystem import FileSystemNode, FileSystemAdapter
from dazzletreelib.config import (
    TraversalConfig, DataRequirement, TraversalStrategy, 
    PerformanceConfig, DepthConfig
)
from dazzletreelib.planning import ExecutionPlan


class PerformanceMetrics:
    """Helper class to track performance metrics."""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.start_memory = None
        self.end_memory = None
        self.node_count = 0
        self.process = psutil.Process()
    
    def start(self):
        """Start tracking metrics."""
        gc.collect()  # Force garbage collection
        self.start_time = time.time()
        self.start_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        self.node_count = 0
    
    def end(self):
        """End tracking and calculate results."""
        self.end_time = time.time()
        gc.collect()  # Force garbage collection
        self.end_memory = self.process.memory_info().rss / 1024 / 1024  # MB
    
    def increment_nodes(self, count=1):
        """Increment node counter."""
        self.node_count += count
    
    @property
    def elapsed_time(self):
        """Get elapsed time in seconds."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0
    
    @property
    def memory_used(self):
        """Get memory used in MB."""
        if self.start_memory and self.end_memory:
            return self.end_memory - self.start_memory
        return 0
    
    @property
    def nodes_per_second(self):
        """Calculate nodes processed per second."""
        if self.elapsed_time > 0:
            return self.node_count / self.elapsed_time
        return 0
    
    @property
    def memory_per_node(self):
        """Calculate memory used per node in KB."""
        if self.node_count > 0:
            return (self.memory_used * 1024) / self.node_count
        return 0


class TestPerformance(unittest.TestCase):
    """Test performance characteristics of DazzleTreeLib."""
    
    @classmethod
    def setUpClass(cls):
        """Create large test structures once for all tests."""
        cls.temp_dir = tempfile.mkdtemp(prefix='test_performance_')
        cls.small_tree_dir = cls.create_tree_structure(cls.temp_dir, 'small', depth=3, width=3)
        cls.medium_tree_dir = cls.create_tree_structure(cls.temp_dir, 'medium', depth=4, width=5)
        cls.large_tree_dir = cls.create_tree_structure(cls.temp_dir, 'large', depth=5, width=8)
        cls.deep_tree_dir = cls.create_deep_structure(cls.temp_dir, 'deep', depth=20)
        cls.wide_tree_dir = cls.create_wide_structure(cls.temp_dir, 'wide', width=100)
    
    @classmethod
    def tearDownClass(cls):
        """Clean up test structures."""
        import shutil
        shutil.rmtree(cls.temp_dir, ignore_errors=True)
    
    @staticmethod
    def create_tree_structure(base_dir, name, depth, width):
        """Create a balanced tree structure."""
        root = os.path.join(base_dir, f'{name}_tree')
        os.makedirs(root, exist_ok=True)
        
        def create_level(path, current_depth):
            if current_depth >= depth:
                return
            
            for i in range(width):
                # Create directories
                dir_path = os.path.join(path, f'dir_{current_depth}_{i}')
                os.makedirs(dir_path, exist_ok=True)
                
                # Create files
                for j in range(width // 2):
                    file_path = os.path.join(dir_path, f'file_{current_depth}_{i}_{j}.txt')
                    with open(file_path, 'w') as f:
                        f.write('x' * random.randint(100, 1000))
                
                # Recurse
                create_level(dir_path, current_depth + 1)
        
        create_level(root, 0)
        return root
    
    @staticmethod
    def create_deep_structure(base_dir, name, depth):
        """Create a very deep but narrow structure."""
        root = os.path.join(base_dir, f'{name}_tree')
        current = root
        
        for i in range(depth):
            current = os.path.join(current, f'level_{i}')
            os.makedirs(current, exist_ok=True)
            
            # Add a few files at each level
            for j in range(3):
                file_path = os.path.join(current, f'file_{i}_{j}.txt')
                with open(file_path, 'w') as f:
                    f.write('x' * 100)
        
        return root
    
    @staticmethod
    def create_wide_structure(base_dir, name, width):
        """Create a very wide but shallow structure."""
        root = os.path.join(base_dir, f'{name}_tree')
        os.makedirs(root, exist_ok=True)
        
        # Create many items at root level
        for i in range(width):
            # Mix of files and directories
            if i % 3 == 0:
                dir_path = os.path.join(root, f'dir_{i}')
                os.makedirs(dir_path, exist_ok=True)
                # Add a few files in each dir
                for j in range(5):
                    file_path = os.path.join(dir_path, f'file_{j}.txt')
                    with open(file_path, 'w') as f:
                        f.write('x' * 100)
            else:
                file_path = os.path.join(root, f'file_{i}.txt')
                with open(file_path, 'w') as f:
                    f.write('x' * random.randint(50, 500))
        
        return root
    
    def test_small_tree_performance(self):
        """Test performance on small tree (~100 nodes)."""
        metrics = PerformanceMetrics()
        adapter = FileSystemAdapter()
        root = FileSystemNode(Path(self.small_tree_dir))
        
        config = TraversalConfig(data_requirements=DataRequirement.METADATA)
        plan = ExecutionPlan(config, adapter)
        
        metrics.start()
        results = list(plan.execute(root))
        metrics.increment_nodes(len(results))
        metrics.end()
        
        # Small tree should be very fast
        self.assertLess(metrics.elapsed_time, 1.0, "Small tree took too long")
        self.assertGreater(metrics.nodes_per_second, 50, "Processing too slow")
        
        print(f"\nSmall tree performance:")
        print(f"  Nodes: {metrics.node_count}")
        print(f"  Time: {metrics.elapsed_time:.3f}s")
        print(f"  Speed: {metrics.nodes_per_second:.0f} nodes/sec")
        print(f"  Memory: {metrics.memory_used:.1f} MB")
    
    def test_medium_tree_performance(self):
        """Test performance on medium tree (~1000 nodes)."""
        metrics = PerformanceMetrics()
        adapter = FileSystemAdapter()
        root = FileSystemNode(Path(self.medium_tree_dir))
        
        config = TraversalConfig(data_requirements=DataRequirement.METADATA)
        plan = ExecutionPlan(config, adapter)
        
        metrics.start()
        results = list(plan.execute(root))
        metrics.increment_nodes(len(results))
        metrics.end()
        
        # Medium tree should still be fast
        self.assertLess(metrics.elapsed_time, 5.0, "Medium tree took too long")
        self.assertGreater(metrics.nodes_per_second, 100, "Processing too slow")
        
        print(f"\nMedium tree performance:")
        print(f"  Nodes: {metrics.node_count}")
        print(f"  Time: {metrics.elapsed_time:.3f}s")
        print(f"  Speed: {metrics.nodes_per_second:.0f} nodes/sec")
        print(f"  Memory: {metrics.memory_used:.1f} MB")
    
    def test_large_tree_performance(self):
        """Test performance on large tree (~10000 nodes)."""
        metrics = PerformanceMetrics()
        adapter = FileSystemAdapter()
        root = FileSystemNode(Path(self.large_tree_dir))
        
        config = TraversalConfig(data_requirements=DataRequirement.IDENTIFIER_ONLY)
        plan = ExecutionPlan(config, adapter)
        
        metrics.start()
        count = 0
        for node, data in plan.execute(root):
            count += 1
            if count % 1000 == 0:
                print(f"  Processed {count} nodes...")
        metrics.increment_nodes(count)
        metrics.end()
        
        # Large tree performance targets
        self.assertLess(metrics.elapsed_time, 30.0, "Large tree took too long")
        self.assertGreater(metrics.nodes_per_second, 300, "Processing too slow")
        
        print(f"\nLarge tree performance:")
        print(f"  Nodes: {metrics.node_count}")
        print(f"  Time: {metrics.elapsed_time:.3f}s")
        print(f"  Speed: {metrics.nodes_per_second:.0f} nodes/sec")
        print(f"  Memory: {metrics.memory_used:.1f} MB")
        print(f"  Memory/node: {metrics.memory_per_node:.2f} KB")
    
    def test_lazy_vs_eager_evaluation(self):
        """Compare lazy vs eager evaluation memory usage."""
        adapter = FileSystemAdapter()
        root = FileSystemNode(Path(self.medium_tree_dir))
        
        # Test lazy evaluation (generator)
        lazy_metrics = PerformanceMetrics()
        config = TraversalConfig(data_requirements=DataRequirement.IDENTIFIER_ONLY)
        plan = ExecutionPlan(config, adapter)
        
        lazy_metrics.start()
        count = 0
        for node, data in plan.execute(root):
            count += 1
        lazy_metrics.increment_nodes(count)
        lazy_metrics.end()
        
        # Test eager evaluation (list)
        eager_metrics = PerformanceMetrics()
        config = TraversalConfig(data_requirements=DataRequirement.FULL_NODE)
        plan = ExecutionPlan(config, adapter)
        
        eager_metrics.start()
        results = list(plan.execute(root))  # Force everything into memory
        eager_metrics.increment_nodes(len(results))
        eager_metrics.end()
        
        # Lazy should use less memory
        print(f"\nLazy vs Eager evaluation:")
        print(f"  Lazy memory: {lazy_metrics.memory_used:.1f} MB")
        print(f"  Eager memory: {eager_metrics.memory_used:.1f} MB")
        print(f"  Memory saved: {eager_metrics.memory_used - lazy_metrics.memory_used:.1f} MB")
        
        # Eager should use significantly more memory for large trees
        if eager_metrics.node_count > 100:
            self.assertGreater(eager_metrics.memory_used, lazy_metrics.memory_used)
    
    def test_traversal_strategy_performance(self):
        """Compare performance of different traversal strategies."""
        adapter = FileSystemAdapter()
        root = FileSystemNode(Path(self.medium_tree_dir))
        
        strategies = [
            TraversalStrategy.BFS,
            TraversalStrategy.DFS_PRE,
            TraversalStrategy.DFS_POST,
            TraversalStrategy.LEVEL_ORDER
        ]
        
        results = {}
        
        for strategy in strategies:
            metrics = PerformanceMetrics()
            config = TraversalConfig(
                traversal_strategy=strategy,
                data_requirements=DataRequirement.IDENTIFIER_ONLY
            )
            plan = ExecutionPlan(config, adapter)
            
            metrics.start()
            count = sum(1 for _ in plan.execute(root))
            metrics.increment_nodes(count)
            metrics.end()
            
            results[strategy] = metrics
        
        print(f"\nTraversal strategy comparison:")
        for strategy, metrics in results.items():
            print(f"  {strategy.value}:")
            print(f"    Time: {metrics.elapsed_time:.3f}s")
            print(f"    Speed: {metrics.nodes_per_second:.0f} nodes/sec")
            print(f"    Memory: {metrics.memory_used:.1f} MB")
        
        # All strategies should have similar performance
        times = [m.elapsed_time for m in results.values()]
        max_time = max(times)
        min_time = min(times)
        self.assertLess(max_time - min_time, min_time * 0.5, 
                       "Strategies have too different performance")
    
    def test_deep_tree_performance(self):
        """Test performance on very deep trees."""
        metrics = PerformanceMetrics()
        adapter = FileSystemAdapter()
        root = FileSystemNode(Path(self.deep_tree_dir))
        
        config = TraversalConfig(data_requirements=DataRequirement.IDENTIFIER_ONLY)
        plan = ExecutionPlan(config, adapter)
        
        metrics.start()
        results = list(plan.execute(root))
        metrics.increment_nodes(len(results))
        metrics.end()
        
        # Deep trees should still be handled efficiently
        self.assertLess(metrics.elapsed_time, 5.0, "Deep tree took too long")
        
        print(f"\nDeep tree performance (20 levels):")
        print(f"  Nodes: {metrics.node_count}")
        print(f"  Time: {metrics.elapsed_time:.3f}s")
        print(f"  Speed: {metrics.nodes_per_second:.0f} nodes/sec")
    
    def test_wide_tree_performance(self):
        """Test performance on very wide trees."""
        metrics = PerformanceMetrics()
        adapter = FileSystemAdapter()
        root = FileSystemNode(Path(self.wide_tree_dir))
        
        config = TraversalConfig(data_requirements=DataRequirement.IDENTIFIER_ONLY)
        plan = ExecutionPlan(config, adapter)
        
        metrics.start()
        results = list(plan.execute(root))
        metrics.increment_nodes(len(results))
        metrics.end()
        
        # Wide trees should be handled efficiently
        self.assertLess(metrics.elapsed_time, 5.0, "Wide tree took too long")
        
        print(f"\nWide tree performance (100+ items at root):")
        print(f"  Nodes: {metrics.node_count}")
        print(f"  Time: {metrics.elapsed_time:.3f}s")
        print(f"  Speed: {metrics.nodes_per_second:.0f} nodes/sec")
    
    def test_filtering_performance(self):
        """Test performance impact of filtering."""
        adapter = FileSystemAdapter()
        root = FileSystemNode(Path(self.large_tree_dir))
        
        # Test without filtering
        no_filter_metrics = PerformanceMetrics()
        config = TraversalConfig(data_requirements=DataRequirement.IDENTIFIER_ONLY)
        plan = ExecutionPlan(config, adapter)
        
        no_filter_metrics.start()
        count = sum(1 for _ in plan.execute(root))
        no_filter_metrics.increment_nodes(count)
        no_filter_metrics.end()
        
        # Test with filtering
        filter_metrics = PerformanceMetrics()
        config = TraversalConfig(data_requirements=DataRequirement.IDENTIFIER_ONLY)
        config.filter.exclude_patterns = {'*.txt', '*.log', 'temp*'}
        config.filter.include_filter = lambda n: not n.identifier.name.startswith('dir_1')
        plan = ExecutionPlan(config, adapter)
        
        filter_metrics.start()
        count = sum(1 for _ in plan.execute(root))
        filter_metrics.increment_nodes(count)
        filter_metrics.end()
        
        print(f"\nFiltering performance impact:")
        print(f"  No filter: {no_filter_metrics.elapsed_time:.3f}s ({no_filter_metrics.node_count} nodes)")
        print(f"  With filter: {filter_metrics.elapsed_time:.3f}s ({filter_metrics.node_count} nodes)")
        print(f"  Overhead: {filter_metrics.elapsed_time - no_filter_metrics.elapsed_time:.3f}s")
        
        # Filtering should reduce nodes processed
        self.assertLess(filter_metrics.node_count, no_filter_metrics.node_count)
    
    def test_depth_limiting_performance(self):
        """Test performance with depth limiting."""
        adapter = FileSystemAdapter()
        root = FileSystemNode(Path(self.large_tree_dir))
        
        depths = [1, 2, 3, None]
        results = {}
        
        for max_depth in depths:
            metrics = PerformanceMetrics()
            config = TraversalConfig(data_requirements=DataRequirement.IDENTIFIER_ONLY)
            if max_depth:
                config.depth.max_depth = max_depth
            
            plan = ExecutionPlan(config, adapter)
            
            metrics.start()
            count = sum(1 for _ in plan.execute(root))
            metrics.increment_nodes(count)
            metrics.end()
            
            results[max_depth or 'unlimited'] = metrics
        
        print(f"\nDepth limiting performance:")
        for depth, metrics in results.items():
            print(f"  Depth {depth}:")
            print(f"    Nodes: {metrics.node_count}")
            print(f"    Time: {metrics.elapsed_time:.3f}s")
            print(f"    Speed: {metrics.nodes_per_second:.0f} nodes/sec")
        
        # Shallower depths should be faster
        self.assertLess(results[1].elapsed_time, results['unlimited'].elapsed_time)
        self.assertLess(results[1].node_count, results['unlimited'].node_count)
    
    def test_metadata_collection_overhead(self):
        """Test overhead of collecting different levels of metadata."""
        adapter = FileSystemAdapter()
        root = FileSystemNode(Path(self.medium_tree_dir))
        
        data_reqs = [
            DataRequirement.IDENTIFIER_ONLY,
            DataRequirement.METADATA,
            DataRequirement.FULL_NODE
        ]
        
        results = {}
        
        for req in data_reqs:
            metrics = PerformanceMetrics()
            config = TraversalConfig(data_requirements=req)
            plan = ExecutionPlan(config, adapter)
            
            metrics.start()
            count = sum(1 for _ in plan.execute(root))
            metrics.increment_nodes(count)
            metrics.end()
            
            results[req] = metrics
        
        print(f"\nMetadata collection overhead:")
        for req, metrics in results.items():
            print(f"  {req.value}:")
            print(f"    Time: {metrics.elapsed_time:.3f}s")
            print(f"    Memory: {metrics.memory_used:.1f} MB")
            print(f"    Memory/node: {metrics.memory_per_node:.2f} KB")
        
        # More metadata should take more time and memory
        self.assertLess(results[DataRequirement.IDENTIFIER_ONLY].elapsed_time,
                       results[DataRequirement.FULL_NODE].elapsed_time)
    
    def test_cache_effectiveness(self):
        """Test effectiveness of metadata caching."""
        adapter = FileSystemAdapter()
        root = FileSystemNode(Path(self.small_tree_dir))
        
        # First pass - cold cache
        cold_metrics = PerformanceMetrics()
        config = TraversalConfig(data_requirements=DataRequirement.METADATA)
        plan = ExecutionPlan(config, adapter)
        
        cold_metrics.start()
        results1 = list(plan.execute(root))
        cold_metrics.increment_nodes(len(results1))
        cold_metrics.end()
        
        # Second pass - warm cache (reuse same nodes)
        warm_metrics = PerformanceMetrics()
        
        warm_metrics.start()
        # Access metadata again on same nodes
        for node, _ in results1:
            if isinstance(node, FileSystemNode):
                _ = node.metadata  # Access cached metadata
        warm_metrics.increment_nodes(len(results1))
        warm_metrics.end()
        
        print(f"\nCache effectiveness:")
        print(f"  Cold cache: {cold_metrics.elapsed_time:.3f}s")
        print(f"  Warm cache: {warm_metrics.elapsed_time:.3f}s")
        print(f"  Speedup: {cold_metrics.elapsed_time / max(warm_metrics.elapsed_time, 0.001):.1f}x")
        
        # Warm cache should be faster
        self.assertLess(warm_metrics.elapsed_time, cold_metrics.elapsed_time)
    
    def test_parallel_traversal_capability(self):
        """Test if multiple traversals can run without interference."""
        adapter1 = FileSystemAdapter()
        adapter2 = FileSystemAdapter()
        root1 = FileSystemNode(Path(self.small_tree_dir))
        root2 = FileSystemNode(Path(self.medium_tree_dir))
        
        config = TraversalConfig(data_requirements=DataRequirement.IDENTIFIER_ONLY)
        
        plan1 = ExecutionPlan(config, adapter1)
        plan2 = ExecutionPlan(config, adapter2)
        
        # Interleave execution
        gen1 = plan1.execute(root1)
        gen2 = plan2.execute(root2)
        
        count1 = 0
        count2 = 0
        
        try:
            while True:
                # Alternate between generators
                try:
                    next(gen1)
                    count1 += 1
                except StopIteration:
                    pass
                
                try:
                    next(gen2)
                    count2 += 1
                except StopIteration:
                    pass
                
                if count1 == 0 and count2 == 0:
                    break
                
                # Reset counts after check
                if count1 > 0 or count2 > 0:
                    count1 = 0
                    count2 = 0
        except Exception as e:
            self.fail(f"Parallel traversal failed: {e}")
        
        print(f"\nParallel traversal: Success - no interference detected")
    
    def test_memory_leak_detection(self):
        """Test for memory leaks during repeated traversals."""
        adapter = FileSystemAdapter()
        root = FileSystemNode(Path(self.small_tree_dir))
        config = TraversalConfig(data_requirements=DataRequirement.METADATA)
        
        # Get baseline memory
        gc.collect()
        process = psutil.Process()
        baseline_memory = process.memory_info().rss / 1024 / 1024
        
        # Perform many traversals
        memories = []
        for i in range(10):
            plan = ExecutionPlan(config, adapter)
            results = list(plan.execute(root))
            
            # Force cleanup
            del results
            del plan
            gc.collect()
            
            current_memory = process.memory_info().rss / 1024 / 1024
            memories.append(current_memory)
        
        # Check for memory growth
        memory_growth = memories[-1] - baseline_memory
        avg_growth_per_iteration = memory_growth / 10
        
        print(f"\nMemory leak detection:")
        print(f"  Baseline: {baseline_memory:.1f} MB")
        print(f"  After 10 iterations: {memories[-1]:.1f} MB")
        print(f"  Total growth: {memory_growth:.1f} MB")
        print(f"  Avg per iteration: {avg_growth_per_iteration:.2f} MB")
        
        # Should not have significant memory growth
        self.assertLess(avg_growth_per_iteration, 1.0, 
                       "Possible memory leak detected")


if __name__ == '__main__':
    # Run with verbose output to see performance metrics
    unittest.main(verbosity=2)