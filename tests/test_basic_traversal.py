"""Basic tests for DazzleTreeLib functionality.

This test file demonstrates that the core functionality works correctly.
"""

import sys
import os
from pathlib import Path
import tempfile
import shutil

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dazzletreelib.sync import (
    FileSystemNode,
    FileSystemAdapter,
    traverse_tree,
    collect_tree_data,
    count_nodes,
    TraversalConfig,
    ExecutionPlan,
    DataRequirement,
    TraversalStrategy,
)


def create_test_tree(base_dir: Path) -> None:
    """Create a test directory structure.
    
    Structure:
    base_dir/
    ├── file1.txt
    ├── file2.py
    ├── dir1/
    │   ├── file3.txt
    │   ├── file4.py
    │   └── subdir1/
    │       └── file5.txt
    └── dir2/
        └── file6.txt
    """
    # Create directories
    (base_dir / "dir1").mkdir()
    (base_dir / "dir1" / "subdir1").mkdir()
    (base_dir / "dir2").mkdir()
    
    # Create files
    (base_dir / "file1.txt").write_text("content1")
    (base_dir / "file2.py").write_text("# python file")
    (base_dir / "dir1" / "file3.txt").write_text("content3")
    (base_dir / "dir1" / "file4.py").write_text("# another python file")
    (base_dir / "dir1" / "subdir1" / "file5.txt").write_text("content5")
    (base_dir / "dir2" / "file6.txt").write_text("content6")


def test_basic_traversal():
    """Test basic tree traversal."""
    print("\n=== Test: Basic Traversal ===")
    
    # Create temporary test tree
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)
        create_test_tree(test_dir)
        
        # Create adapter and root node
        adapter = FileSystemAdapter()
        root = FileSystemNode(test_dir)
        
        # Traverse and collect all nodes
        nodes = list(traverse_tree(root, adapter))
        
        print(f"Found {len(nodes)} nodes")
        for node in nodes:
            print(f"  - {node.path.relative_to(test_dir)}")
        
        # Should find 9 nodes total (1 root + 3 dirs + 6 files)
        assert len(nodes) == 10, f"Expected 10 nodes, found {len(nodes)}"
        print("[PASS] Basic traversal passed")


def test_depth_filtering():
    """Test traversal with depth limits."""
    print("\n=== Test: Depth Filtering ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)
        create_test_tree(test_dir)
        
        adapter = FileSystemAdapter()
        root = FileSystemNode(test_dir)
        
        # Test max_depth=1 (root + immediate children)
        nodes_depth1 = list(traverse_tree(root, adapter, max_depth=1))
        print(f"Depth 1: Found {len(nodes_depth1)} nodes")
        
        # Should find root + 2 files + 2 dirs = 5 nodes
        assert len(nodes_depth1) == 5, f"Expected 5 nodes at depth<=1, found {len(nodes_depth1)}"
        
        # Test max_depth=2
        nodes_depth2 = list(traverse_tree(root, adapter, max_depth=2))
        print(f"Depth 2: Found {len(nodes_depth2)} nodes")
        
        # Should find everything except file5.txt in subdir1
        assert len(nodes_depth2) == 9, f"Expected 9 nodes at depth<=2, found {len(nodes_depth2)}"
        
        print("[PASS] Depth filtering passed")


def test_traversal_strategies():
    """Test different traversal strategies."""
    print("\n=== Test: Traversal Strategies ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)
        create_test_tree(test_dir)
        
        adapter = FileSystemAdapter()
        root = FileSystemNode(test_dir)
        
        # Test BFS
        bfs_nodes = []
        for node in traverse_tree(root, adapter, strategy="bfs"):
            relative = node.path.relative_to(test_dir) if node.path != test_dir else Path(".")
            bfs_nodes.append(str(relative))
        
        print("BFS order:", bfs_nodes[:5], "...")
        
        # Test DFS
        dfs_nodes = []
        for node in traverse_tree(root, adapter, strategy="dfs_pre"):
            relative = node.path.relative_to(test_dir) if node.path != test_dir else Path(".")
            dfs_nodes.append(str(relative))
        
        print("DFS order:", dfs_nodes[:5], "...")
        
        # Orders should be different
        assert bfs_nodes != dfs_nodes, "BFS and DFS should produce different orders"
        print("[PASS] Traversal strategies passed")


def test_data_collection():
    """Test different data collection strategies."""
    print("\n=== Test: Data Collection ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)
        create_test_tree(test_dir)
        
        adapter = FileSystemAdapter()
        root = FileSystemNode(test_dir)
        
        # Collect metadata
        for node, metadata in collect_tree_data(
            root, adapter, 
            data_requirement=DataRequirement.METADATA,
            max_depth=1
        ):
            print(f"  {node.path.name}: size={metadata.get('size', 'N/A')}, "
                  f"is_dir={metadata.get('is_dir', False)}")
        
        print("[PASS] Data collection passed")


def test_execution_plan():
    """Test ExecutionPlan validation and execution."""
    print("\n=== Test: Execution Plan ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)
        create_test_tree(test_dir)
        
        # Create configuration
        config = TraversalConfig.shallow_scan(max_depth=2)
        
        # Create adapter and plan
        adapter = FileSystemAdapter()
        plan = ExecutionPlan(config, adapter)
        
        # Get plan summary
        summary = plan.get_summary()
        print(f"Plan summary: strategy={summary['strategy']}, "
              f"max_depth={summary['max_depth']}")
        
        # Execute plan
        root = FileSystemNode(test_dir)
        results = list(plan.execute(root))
        
        print(f"Executed plan, processed {plan.nodes_processed} nodes")
        assert plan.nodes_processed > 0, "Should have processed some nodes"
        
        print("[PASS] Execution plan passed")


def test_filtering():
    """Test node filtering during traversal."""
    print("\n=== Test: Filtering ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)
        create_test_tree(test_dir)
        
        adapter = FileSystemAdapter()
        root = FileSystemNode(test_dir)
        
        # Filter to only .txt files
        txt_files = list(traverse_tree(
            root, adapter,
            include_filter=lambda n: n.path.suffix == '.txt' or n.path.is_dir()
        ))
        
        txt_count = sum(1 for n in txt_files if n.path.suffix == '.txt')
        print(f"Found {txt_count} .txt files")
        
        # Should find 4 .txt files
        assert txt_count == 4, f"Expected 4 .txt files, found {txt_count}"
        
        print("[PASS] Filtering passed")


def run_all_tests():
    """Run all tests."""
    print("\n" + "="*50)
    print("Running DazzleTreeLib Basic Tests")
    print("="*50)
    
    try:
        test_basic_traversal()
        test_depth_filtering()
        test_traversal_strategies()
        test_data_collection()
        test_execution_plan()
        test_filtering()
        
        print("\n" + "="*50)
        print("All tests passed! [SUCCESS]")
        print("="*50)
        
    except AssertionError as e:
        print(f"\n[FAIL] Test failed: {e}")
        return False
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)