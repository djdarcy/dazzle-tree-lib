#!/usr/bin/env python3
"""Comprehensive test suite for DazzleTreeLib performance optimizations.

Tests both stat caching and fast adapter to ensure they're ready for production.
Includes scenarios relevant to folder-datetime-fix integration.
"""

import asyncio
import os
import time
import tempfile
import shutil
from pathlib import Path
import sys
import pytest
from typing import List, Dict, Any, Set
from unittest.mock import Mock, patch

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dazzletreelib.aio import traverse_tree_async
from dazzletreelib.aio.adapters.filesystem import (
    AsyncFileSystemAdapter, 
    AsyncFileSystemNode,
    StatCache
)
from dazzletreelib.aio.adapters.fast_filesystem import (
    FastAsyncFileSystemAdapter,
    FastAsyncFileSystemNode,
    fast_traverse_tree
)


class TestStatCache:
    """Test suite for stat caching functionality."""
    
    @pytest.mark.asyncio
    async def test_stat_cache_basic_functionality(self):
        """Test basic stat cache operations."""
        cache = StatCache(ttl=1.0)
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            test_file = Path(f.name)
            f.write(b"test content")
        
        try:
            # First access should be a miss
            stat1 = await cache.get_stat(test_file)
            assert stat1 is not None
            assert cache.hits == 0
            assert cache.misses == 1
            
            # Second access should be a hit
            stat2 = await cache.get_stat(test_file)
            assert stat2 is not None
            assert stat2 == stat1
            assert cache.hits == 1
            assert cache.misses == 1
            
            # Cache hit rate should be 50%
            stats = cache.get_stats()
            assert stats['hit_rate'] == 0.5
            
        finally:
            test_file.unlink()
    
    @pytest.mark.asyncio
    async def test_stat_cache_ttl_expiration(self):
        """Test that cache entries expire after TTL."""
        cache = StatCache(ttl=0.1)  # 100ms TTL
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            test_file = Path(f.name)
            f.write(b"test")
        
        try:
            # First access
            stat1 = await cache.get_stat(test_file)
            assert cache.misses == 1
            
            # Immediate second access (within TTL)
            stat2 = await cache.get_stat(test_file)
            assert cache.hits == 1
            
            # Wait for TTL to expire
            await asyncio.sleep(0.15)
            
            # Should be a miss again
            stat3 = await cache.get_stat(test_file)
            assert cache.misses == 2
            
        finally:
            test_file.unlink()
    
    @pytest.mark.asyncio
    async def test_stat_cache_with_traversal(self):
        """Test stat cache effectiveness during tree traversal."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir)
            
            # Create test tree
            for i in range(3):
                subdir = test_dir / f"dir_{i}"
                subdir.mkdir()
                for j in range(5):
                    file = subdir / f"file_{j}.txt"
                    file.write_text(f"content {i}-{j}")
            
            # Traverse with caching enabled
            adapter = AsyncFileSystemAdapter(use_stat_cache=True, cache_ttl=1.0)
            root = AsyncFileSystemNode(test_dir, adapter.stat_cache)
            
            # First traversal
            nodes1 = []
            from dazzletreelib.aio.core import AsyncBreadthFirstTraverser
            traverser = AsyncBreadthFirstTraverser()
            
            async for node in traverser.traverse(root, adapter):
                nodes1.append(node)
                if node.path.is_file():
                    await node.size()  # Trigger stat
            
            initial_stats = adapter.stat_cache.get_stats() if adapter.stat_cache else None
            
            # Second traversal should have cache hits
            nodes2 = []
            async for node in traverser.traverse(root, adapter):
                nodes2.append(node)
                if node.path.is_file():
                    await node.size()  # Should hit cache
            
            if adapter.stat_cache:
                final_stats = adapter.stat_cache.get_stats()
                assert final_stats['hits'] > initial_stats['hits']
                assert final_stats['hit_rate'] > 0
    
    @pytest.mark.asyncio
    async def test_stat_cache_memory_cleanup(self):
        """Test that cache can be cleared to free memory."""
        cache = StatCache()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir)
            
            # Create many files
            for i in range(100):
                file = test_dir / f"file_{i}.txt"
                file.write_text(f"content {i}")
                await cache.get_stat(file)
            
            assert cache.get_stats()['cached_paths'] == 100
            
            # Clear cache
            cache.clear()
            assert cache.get_stats()['cached_paths'] == 0
            assert cache.hits == 0
            assert cache.misses == 0


class TestFastAdapter:
    """Test suite for fast os.scandir-based adapter."""
    
    @pytest.mark.asyncio
    async def test_fast_adapter_basic_traversal(self):
        """Test basic traversal with fast adapter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir)
            
            # Create test structure
            subdir1 = test_dir / "subdir1"
            subdir1.mkdir()
            (subdir1 / "file1.txt").write_text("content1")
            
            subdir2 = test_dir / "subdir2"
            subdir2.mkdir()
            (subdir2 / "file2.txt").write_text("content2")
            
            # Traverse with fast adapter
            nodes = []
            async for node in fast_traverse_tree(test_dir):
                nodes.append(node.path.name)
            
            # Should find all nodes
            assert len(nodes) == 5  # root + 2 subdirs + 2 files
            assert "subdir1" in nodes
            assert "subdir2" in nodes
            assert "file1.txt" in nodes
            assert "file2.txt" in nodes
    
    @pytest.mark.asyncio
    async def test_fast_adapter_cached_stats(self):
        """Test that fast adapter uses cached stats from scandir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir)
            
            # Create files with known sizes
            (test_dir / "small.txt").write_text("small")  # 5 bytes
            (test_dir / "large.txt").write_text("x" * 1000)  # 1000 bytes
            
            # Traverse and check sizes
            files = {}
            async for node in fast_traverse_tree(test_dir):
                if not node.is_leaf():
                    continue
                size = await node.size()
                if size:
                    files[node.path.name] = size
            
            assert files["small.txt"] == 5
            assert files["large.txt"] == 1000
    
    @pytest.mark.asyncio
    async def test_fast_adapter_vs_original_correctness(self):
        """Ensure fast adapter produces same results as original."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir)
            
            # Create complex structure
            for i in range(3):
                subdir = test_dir / f"dir_{i}"
                subdir.mkdir()
                for j in range(3):
                    file = subdir / f"file_{j}.txt"
                    file.write_text(f"content {i}-{j}")
                    if j == 0:
                        nested = subdir / f"nested_{j}"
                        nested.mkdir()
                        (nested / "deep.txt").write_text("deep")
            
            # Collect with original adapter
            original_paths = set()
            async for node in traverse_tree_async(test_dir, use_stat_cache=False):
                original_paths.add(str(node.path.relative_to(test_dir)))
            
            # Collect with fast adapter
            fast_paths = set()
            async for node in fast_traverse_tree(test_dir):
                try:
                    fast_paths.add(str(node.path.relative_to(test_dir)))
                except ValueError:
                    fast_paths.add(".")  # Root node
            
            # Should have same paths
            assert fast_paths == original_paths
    
    @pytest.mark.asyncio
    async def test_fast_adapter_performance(self):
        """Test that fast adapter is significantly faster."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir)
            
            # Create larger tree for performance testing
            for i in range(10):
                subdir = test_dir / f"dir_{i}"
                subdir.mkdir()
                for j in range(20):
                    file = subdir / f"file_{j}.txt"
                    file.write_text(f"content {i}-{j}")
            
            # Time original adapter
            start = time.perf_counter()
            count_original = 0
            async for node in traverse_tree_async(test_dir, use_stat_cache=False):
                count_original += 1
                if node.path.is_file():
                    await node.size()
            time_original = time.perf_counter() - start
            
            # Time fast adapter
            start = time.perf_counter()
            count_fast = 0
            async for node in fast_traverse_tree(test_dir):
                count_fast += 1
                if not node.is_leaf():
                    continue
                await node.size()
            time_fast = time.perf_counter() - start
            
            # Fast adapter should be faster
            assert count_fast == count_original
            assert time_fast < time_original
            print(f"Performance improvement: {time_original/time_fast:.2f}x")
    
    @pytest.mark.asyncio
    async def test_fast_adapter_empty_directories(self):
        """Test fast adapter handles empty directories correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir)
            
            # Create empty directories
            (test_dir / "empty1").mkdir()
            (test_dir / "empty2").mkdir()
            nested = test_dir / "nested"
            nested.mkdir()
            (nested / "empty3").mkdir()
            
            # Should traverse all directories
            dirs = []
            async for node in fast_traverse_tree(test_dir):
                if not node.is_leaf():
                    dirs.append(node.path.name if node.path.name else "root")
            
            assert "empty1" in dirs
            assert "empty2" in dirs
            assert "nested" in dirs
            assert "empty3" in dirs
    
    @pytest.mark.asyncio
    async def test_fast_adapter_system_files(self):
        """Test fast adapter with system files (relevant for folder-datetime-fix)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir)
            
            # Create regular files and system files
            (test_dir / "normal.txt").write_text("normal")
            (test_dir / "thumbs.db").write_text("system")
            (test_dir / "desktop.ini").write_text("system")
            
            subdir = test_dir / "subdir"
            subdir.mkdir()
            (subdir / "file.txt").write_text("content")
            (subdir / ".DS_Store").write_text("mac system")
            
            # Collect all files
            files = []
            async for node in fast_traverse_tree(test_dir):
                if node.is_leaf():
                    files.append(node.path.name)
            
            # Should find all files (filtering happens at higher level)
            assert "normal.txt" in files
            assert "thumbs.db" in files
            assert "desktop.ini" in files
            assert "file.txt" in files
            assert ".DS_Store" in files


class TestDepthOperations:
    """Test depth-based operations (critical for folder-datetime-fix)."""
    
    @pytest.mark.asyncio
    async def test_depth_calculation(self):
        """Test accurate depth calculation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir)
            
            # Create nested structure
            current = test_dir
            for i in range(5):
                current = current / f"level_{i}"
                current.mkdir()
                (current / f"file_{i}.txt").write_text(f"depth {i}")
            
            # Track depths with both adapters
            depths_original = {}
            async for node in traverse_tree_async(test_dir):
                rel_path = str(node.path.relative_to(test_dir))
                depth = rel_path.count(os.sep) if rel_path != '.' else 0
                depths_original[rel_path] = depth
            
            depths_fast = {}
            async for node in fast_traverse_tree(test_dir):
                try:
                    rel_path = str(node.path.relative_to(test_dir))
                except ValueError:
                    rel_path = "."
                depth = rel_path.count(os.sep) if rel_path != '.' else 0
                depths_fast[rel_path] = depth
            
            # Depths should match
            for path in depths_original:
                if path in depths_fast:
                    assert depths_original[path] == depths_fast[path], \
                        f"Depth mismatch for {path}"
    
    @pytest.mark.asyncio
    async def test_max_depth_limiting(self):
        """Test max_depth parameter works correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir)
            
            # Create deep structure
            current = test_dir
            for i in range(10):
                current = current / f"level_{i}"
                current.mkdir()
            
            # Test with max_depth=3
            from dazzletreelib.aio.core import AsyncBreadthFirstTraverser
            
            adapter = FastAsyncFileSystemAdapter()
            root = FastAsyncFileSystemNode(test_dir)
            traverser = AsyncBreadthFirstTraverser()
            
            nodes = []
            async for node in traverser.traverse(root, adapter, max_depth=3):
                try:
                    rel_path = str(node.path.relative_to(test_dir))
                except ValueError:
                    rel_path = "."
                depth = rel_path.count(os.sep) if rel_path != '.' else 0
                nodes.append((rel_path, depth))
            
            # No node should be deeper than 3
            for path, depth in nodes:
                assert depth <= 3, f"Node {path} at depth {depth} exceeds max_depth=3"


class TestIntegrationScenarios:
    """Test scenarios relevant to folder-datetime-fix integration."""
    
    @pytest.mark.asyncio
    async def test_folder_timestamp_scenario(self):
        """Test scenario similar to folder-datetime-fix usage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir)
            
            # Create structure with mixed timestamps
            project = test_dir / "MyProject"
            project.mkdir()
            
            # Old actual work
            src = project / "src"
            src.mkdir()
            old_file = src / "main.py"
            old_file.write_text("# old code")
            os.utime(old_file, (time.time() - 86400 * 30, time.time() - 86400 * 30))  # 30 days old
            
            # Recent system file (like thumbs.db)
            thumbs = project / "thumbs.db"
            thumbs.write_text("system")
            # thumbs.db is recent (now)
            
            # Traverse and collect metadata
            metadata = {}
            async for node in fast_traverse_tree(test_dir):
                # Only collect files (not directories)
                if node.is_leaf():
                    # Get modification time (like folder-datetime-fix would)
                    mtime = await node.modified_time()
                    if mtime:
                        metadata[node.path.name] = mtime
            
            # Files should have been collected
            assert "thumbs.db" in metadata
            assert "main.py" in metadata
            # System file should have recent timestamp
            assert metadata["thumbs.db"] > metadata["main.py"]
            
            # This is where folder-datetime-fix would filter out thumbs.db
            # and use main.py's timestamp for the folder
    
    @pytest.mark.asyncio
    async def test_shallow_vs_deep_strategy(self):
        """Test shallow vs deep strategy (folder-datetime-fix strategies)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir)
            
            # Create structure
            project = test_dir / "project"
            project.mkdir()
            
            # Immediate child
            (project / "README.md").write_text("readme")
            
            # Deep nested file
            deep = project / "src" / "core" / "utils"
            deep.mkdir(parents=True)
            (deep / "helper.py").write_text("code")
            
            # For shallow strategy - only immediate children matter
            shallow_files = []
            async for node in fast_traverse_tree(project, max_depth=1):
                if node.path != project and node.path.parent == project:
                    shallow_files.append(node.path.name)
            
            assert "README.md" in shallow_files
            assert "src" in shallow_files  # Directory at depth 1
            assert "helper.py" not in shallow_files  # Too deep
            
            # For deep strategy - entire subtree matters
            all_files = []
            async for node in fast_traverse_tree(project):
                # Collect only files (leaves)
                if node.is_leaf():
                    all_files.append(node.path.name)
            
            assert "README.md" in all_files
            assert "helper.py" in all_files  # Found in deep traversal
    
    @pytest.mark.asyncio
    async def test_performance_with_many_system_files(self):
        """Test performance when many system files exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir)
            
            # Create structure with many system files
            for i in range(10):
                subdir = test_dir / f"folder_{i}"
                subdir.mkdir()
                
                # Regular files
                for j in range(5):
                    (subdir / f"file_{j}.txt").write_text(f"content {i}-{j}")
                
                # System files
                (subdir / "thumbs.db").write_text("system")
                (subdir / "desktop.ini").write_text("system")
                (subdir / ".DS_Store").write_text("system")
            
            # Time traversal
            start = time.perf_counter()
            file_count = 0
            system_count = 0
            
            async for node in fast_traverse_tree(test_dir):
                if not node.is_leaf():
                    continue
                
                name = node.path.name
                if name in ["thumbs.db", "desktop.ini", ".DS_Store"]:
                    system_count += 1
                else:
                    file_count += 1
            
            elapsed = time.perf_counter() - start
            
            assert file_count == 50  # 10 folders * 5 files
            assert system_count == 30  # 10 folders * 3 system files
            assert elapsed < 1.0  # Should be fast even with many files


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    @pytest.mark.asyncio
    async def test_nonexistent_path(self):
        """Test handling of nonexistent paths."""
        fake_path = Path("/nonexistent/path/that/does/not/exist")
        
        # Should handle gracefully
        nodes = []
        async for node in fast_traverse_tree(fake_path):
            nodes.append(node)
        
        # May return just root or nothing, but shouldn't crash
        assert len(nodes) <= 1
    
    @pytest.mark.asyncio
    async def test_file_as_root(self):
        """Test traversing from a file instead of directory."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            test_file = Path(f.name)
            f.write(b"test content")
        
        try:
            nodes = []
            async for node in fast_traverse_tree(test_file):
                nodes.append(node)
            
            # Should return just the file
            assert len(nodes) == 1
            assert nodes[0].path == test_file
            
        finally:
            test_file.unlink()
    
    @pytest.mark.asyncio
    async def test_permission_errors(self):
        """Test handling of permission errors (if applicable)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir)
            
            restricted = test_dir / "restricted"
            restricted.mkdir()
            (restricted / "file.txt").write_text("content")
            
            # Note: Actually restricting permissions is platform-specific
            # This test structure is ready for platform-specific implementation
            
            # Should complete even if some directories are inaccessible
            nodes = []
            async for node in fast_traverse_tree(test_dir):
                nodes.append(node.path.name if node.path.name else "root")
            
            assert len(nodes) > 0  # Should at least get root
    
    @pytest.mark.asyncio
    async def test_very_deep_tree(self):
        """Test handling of very deep directory structures."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir)
            
            # Create very deep structure (but not too deep to avoid OS limits)
            current = test_dir
            for i in range(50):  # 50 levels deep
                current = current / f"d{i}"
                current.mkdir()
            
            # Should handle deep trees
            depth_count = 0
            async for node in fast_traverse_tree(test_dir):
                depth_count += 1
            
            assert depth_count == 51  # 50 directories + root
    
    @pytest.mark.asyncio
    async def test_unicode_filenames(self):
        """Test handling of unicode filenames."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir)
            
            # Create files with unicode names
            (test_dir / "普通文件.txt").write_text("中文", encoding="utf-8")
            (test_dir / "файл.txt").write_text("русский", encoding="utf-8")
            (test_dir / "αρχείο.txt").write_text("ελληνικά", encoding="utf-8")
            
            # Should handle unicode
            files = []
            async for node in fast_traverse_tree(test_dir):
                # Collect only files (leaves)
                if node.is_leaf():
                    files.append(node.path.name)
            
            assert "普通文件.txt" in files
            assert "файл.txt" in files
            assert "αρχείο.txt" in files


def run_all_tests():
    """Run all optimization tests."""
    print("DAZZLETREELIB OPTIMIZATION TEST SUITE")
    print("=" * 60)
    
    # Run with pytest for better output
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "pytest", __file__, "-v", "--tb=short"],
        capture_output=False
    )
    
    return result.returncode == 0


if __name__ == "__main__":
    # Run all tests
    success = run_all_tests()
    
    if success:
        print("\n" + "=" * 60)
        print("[SUCCESS] All optimization tests passed!")
        print("\nRecommendation: Fast adapter is ready to become default behavior")
        print("Next steps:")
        print("1. Make FastAsyncFileSystemAdapter the default")
        print("2. Bump version to 0.2.0")
        print("3. Commit optimizations")
    else:
        print("\n[FAIL] Some tests failed - review before making default")
    
    sys.exit(0 if success else 1)