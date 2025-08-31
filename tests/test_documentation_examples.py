#!/usr/bin/env python3
"""
Test all examples from the documentation to ensure they work correctly.
"""

import asyncio
import tempfile
from pathlib import Path
import sys
import os

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from dazzletreelib.aio import traverse_tree_async


@pytest.mark.asyncio
async def test_find_large_files_example():
    """Test the find_large_files example from getting-started.md."""
    
    # Create test directory with known files
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)
        
        # Create directory structure
        subdir = test_dir / "subdir"
        subdir.mkdir()
        
        # Create test files of various sizes
        small_file1 = test_dir / "small1.txt"
        small_file1.write_bytes(b"x" * 1024)  # 1KB
        
        small_file2 = subdir / "small2.txt"
        small_file2.write_bytes(b"x" * (5 * 1024 * 1024))  # 5MB
        
        large_file1 = test_dir / "large1.bin"
        large_file1.write_bytes(b"x" * (11 * 1024 * 1024))  # 11MB
        
        large_file2 = subdir / "large2.bin"
        large_file2.write_bytes(b"x" * (25 * 1024 * 1024))  # 25MB
        
        # Test the exact code from documentation
        async def find_large_files(directory, min_size_mb=10):
            large_files = []
            
            async for node in traverse_tree_async(directory):
                if node.path.is_file():
                    size = await node.size()
                    if size and size > min_size_mb * 1024 * 1024:
                        large_files.append((node.path, size))
            
            return sorted(large_files, key=lambda x: x[1], reverse=True)
        
        # Run the function
        files = await find_large_files(test_dir, min_size_mb=10)
        
        # Verify results
        assert len(files) == 2, f"Expected 2 large files, got {len(files)}"
        
        # Check sizes (sorted largest first)
        assert files[0][1] == 25 * 1024 * 1024, f"Largest file should be 25MB"
        assert files[1][1] == 11 * 1024 * 1024, f"Second file should be 11MB"
        
        # Check paths contain the filenames
        assert "large2.bin" in str(files[0][0])
        assert "large1.bin" in str(files[1][0])
        
        print("[PASS] find_large_files example works correctly!")
        return True


@pytest.mark.asyncio  
async def test_search_files_example():
    """Test the search_files example from getting-started.md."""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)
        
        # Create Python files
        py_file1 = test_dir / "async_example.py"
        py_file1.write_text("async def main():\n    pass\n")
        
        py_file2 = test_dir / "sync_example.py"
        py_file2.write_text("def main():\n    pass\n")
        
        py_file3 = test_dir / "another_async.py"
        py_file3.write_text("async def process():\n    await something()\n")
        
        # Create non-Python file
        txt_file = test_dir / "readme.txt"
        txt_file.write_text("This is not a Python file")
        
        # Test search function (simplified version)
        async def search_python_async_files(directory):
            matching_files = []
            
            async for node in traverse_tree_async(directory):
                if node.path.is_file() and node.path.suffix == '.py':
                    try:
                        content = node.path.read_text()
                        if "async def" in content:
                            matching_files.append(node.path)
                    except:
                        pass
            
            return matching_files
        
        # Run search
        results = await search_python_async_files(test_dir)
        
        # Verify
        assert len(results) == 2, f"Expected 2 async Python files, got {len(results)}"
        
        result_names = [p.name for p in results]
        assert "async_example.py" in result_names
        assert "another_async.py" in result_names
        assert "sync_example.py" not in result_names
        
        print("[PASS] search_files example works correctly!")
        return True


def test_sync_vs_async_compatibility():
    """Test that both sync and async APIs work for the same task."""
    from dazzletreelib.sync import FileSystemNode, FileSystemAdapter, traverse_tree
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)
        
        # Create test structure
        for i in range(5):
            subdir = test_dir / f"dir_{i}"
            subdir.mkdir()
            for j in range(3):
                file = subdir / f"file_{j}.txt"
                file.write_text(f"Content {i}-{j}")
        
        # Sync traversal
        root = FileSystemNode(test_dir)
        adapter = FileSystemAdapter()
        sync_files = []
        
        for result in traverse_tree(root, adapter):
            # Handle the return type properly
            if isinstance(result, tuple):
                node, depth = result
            else:
                node = result
            if node.path.is_file():
                sync_files.append(node.path.name)
        
        # Async traversal
        async def get_async_files():
            async_files = []
            async for node in traverse_tree_async(test_dir):
                if node.path.is_file():
                    async_files.append(node.path.name)
            return async_files
        
        async_files = asyncio.run(get_async_files())
        
        # Compare results
        assert len(sync_files) == len(async_files), \
            f"Sync found {len(sync_files)} files, async found {len(async_files)}"
        assert set(sync_files) == set(async_files), \
            "Sync and async found different files"
        
        print(f"[PASS] Sync and async both found {len(sync_files)} files!")
        return True


def run_all_tests():
    """Run all documentation example tests."""
    print("Testing Documentation Examples")
    print("=" * 60)
    
    # Test async examples
    print("\n1. Testing find_large_files example...")
    result1 = asyncio.run(test_find_large_files_example())
    
    print("\n2. Testing search_files example...")
    result2 = asyncio.run(test_search_files_example())
    
    print("\n3. Testing sync/async compatibility...")
    result3 = test_sync_vs_async_compatibility()
    
    print("\n" + "=" * 60)
    if all([result1, result2, result3]):
        print("[SUCCESS] All documentation examples work correctly!")
        return True
    else:
        print("[FAIL] Some examples failed")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)