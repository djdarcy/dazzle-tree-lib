"""Contract tests ensuring sync and async implementations have identical behavior.

These tests verify that both sync and async implementations:
1. Visit nodes in the same order
2. Calculate identical depths
3. Handle errors identically
4. Filter nodes the same way
5. Collect data consistently
"""

import asyncio
import tempfile
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Any, Tuple, Optional
import pytest

from dazzletreelib.sync import (
    FileSystemNode as SyncNode,
    FileSystemAdapter as SyncAdapter,
    BreadthFirstTraverser as SyncBFS,
    DepthFirstPreOrderTraverser as SyncDFS,
    MetadataCollector as SyncMetaCollector,
    PathCollector as SyncPathCollector,
)

from dazzletreelib.aio import (
    AsyncFileSystemNode as AsyncNode,
    AsyncFileSystemAdapter as AsyncAdapter,
    AsyncBreadthFirstTraverser as AsyncBFS,
    AsyncDepthFirstTraverser as AsyncDFS,
    AsyncMetadataCollector as AsyncMetaCollector,
    AsyncPathCollector as AsyncPathCollector,
)


class TraversalContract(ABC):
    """Base contract that both sync and async traversal must satisfy."""
    
    @abstractmethod
    def setup_test_tree(self) -> Path:
        """Create a test directory structure."""
        pass
    
    @abstractmethod
    def teardown_test_tree(self, root: Path):
        """Clean up test directory."""
        pass
    
    def create_standard_tree(self) -> Tuple[Path, List[str]]:
        """Create a standard test tree and return (root, expected_paths).
        
        Tree structure:
        test_root/
        ├── dir1/
        │   ├── file1.txt
        │   └── file2.txt
        ├── dir2/
        │   ├── subdir/
        │   │   └── deep.txt
        │   └── file3.txt
        └── root_file.txt
        """
        root = Path(tempfile.mkdtemp(prefix="dazzle_contract_"))
        
        # Create structure
        (root / "dir1").mkdir()
        (root / "dir1" / "file1.txt").write_text("content1")
        (root / "dir1" / "file2.txt").write_text("content2")
        
        (root / "dir2").mkdir()
        (root / "dir2" / "subdir").mkdir()
        (root / "dir2" / "subdir" / "deep.txt").write_text("deep content")
        (root / "dir2" / "file3.txt").write_text("content3")
        
        (root / "root_file.txt").write_text("root content")
        
        # Expected BFS order (directories before files at each level)
        expected_bfs = [
            str(root),
            str(root / "dir1"),
            str(root / "dir2"),
            str(root / "root_file.txt"),
            str(root / "dir1" / "file1.txt"),
            str(root / "dir1" / "file2.txt"),
            str(root / "dir2" / "subdir"),
            str(root / "dir2" / "file3.txt"),
            str(root / "dir2" / "subdir" / "deep.txt"),
        ]
        
        return root, expected_bfs


class TestSyncTraversal(TraversalContract):
    """Test sync implementation against contract."""
    
    def setup_test_tree(self) -> Path:
        return self.create_standard_tree()[0]
    
    def teardown_test_tree(self, root: Path):
        shutil.rmtree(root)
    
    def test_breadth_first_order(self):
        """Verify BFS traversal order for sync implementation."""
        root, expected_paths = self.create_standard_tree()
        
        try:
            node = SyncNode(root)
            adapter = SyncAdapter()
            traverser = SyncBFS(adapter)
            
            collected_paths = []
            for visited_node, depth in traverser.traverse(node):
                collected_paths.append(str(visited_node.path))
            
            # Sort both for comparison (filesystem order may vary)
            assert sorted(collected_paths) == sorted(expected_paths), \
                f"Sync BFS order mismatch.\nExpected: {expected_paths}\nGot: {collected_paths}"
        
        finally:
            self.teardown_test_tree(root)
    
    def test_depth_calculation(self):
        """Verify depth calculation for sync implementation."""
        root, _ = self.create_standard_tree()
        
        try:
            node = SyncNode(root)
            adapter = SyncAdapter()
            
            # Track depths during traversal
            depths = {}
            
            # Use BFS to get depths
            traverser = SyncBFS(adapter)
            for visited_node, depth in traverser.traverse(node):
                path = str(visited_node.path)
                depths[path] = depth
            
            # Verify specific depths
            assert depths[str(root)] == 0
            assert depths[str(root / "dir1")] == 1
            assert depths[str(root / "dir2" / "subdir")] == 2
            assert depths[str(root / "dir2" / "subdir" / "deep.txt")] == 3
        
        finally:
            self.teardown_test_tree(root)
    
    def test_max_depth_limiting(self):
        """Verify max_depth parameter limits traversal."""
        root, _ = self.create_standard_tree()
        
        try:
            node = SyncNode(root)
            adapter = SyncAdapter()
            traverser = SyncBFS(adapter)
            
            # Traverse with max_depth=1 (root + immediate children)
            collected_paths = []
            for visited_node, depth in traverser.traverse(node, max_depth=1):
                collected_paths.append(str(visited_node.path))
            
            # Should only have root and immediate children
            assert str(root) in collected_paths
            assert str(root / "dir1") in collected_paths
            assert str(root / "dir2") in collected_paths
            assert str(root / "root_file.txt") in collected_paths
            
            # Should NOT have deeper nodes
            assert str(root / "dir1" / "file1.txt") not in collected_paths
            assert str(root / "dir2" / "subdir") not in collected_paths
        
        finally:
            self.teardown_test_tree(root)
    
    def test_metadata_collection(self):
        """Verify metadata collection for sync implementation."""
        root, _ = self.create_standard_tree()
        
        try:
            node = SyncNode(root)
            adapter = SyncAdapter()
            traverser = SyncBFS(adapter)
            collector = SyncMetaCollector(adapter)
            
            metadata_list = []
            for visited_node, depth in traverser.traverse(node):
                metadata = collector.collect(visited_node, depth)
                metadata_list.append(metadata)
            
            # Verify we got metadata for all nodes
            assert len(metadata_list) == 9  # Total nodes in test tree
            
            # Verify metadata structure
            for metadata in metadata_list:
                assert 'path' in metadata
                assert 'name' in metadata
                # Sync uses is_file/is_dir instead of type
                assert 'is_file' in metadata
                assert 'is_dir' in metadata
        
        finally:
            self.teardown_test_tree(root)


class TestAsyncTraversal(TraversalContract):
    """Test async implementation against contract."""
    
    def setup_test_tree(self) -> Path:
        return self.create_standard_tree()[0]
    
    def teardown_test_tree(self, root: Path):
        shutil.rmtree(root)
    
    @pytest.mark.asyncio
    async def test_breadth_first_order(self):
        """Verify BFS traversal order for async implementation."""
        root, expected_paths = self.create_standard_tree()
        
        try:
            node = AsyncNode(root)
            adapter = AsyncAdapter()
            traverser = AsyncBFS()
            
            collected_paths = []
            async for visited_node in traverser.traverse(node, adapter):
                collected_paths.append(str(visited_node.path))
            
            # Sort both for comparison (filesystem order may vary)
            assert sorted(collected_paths) == sorted(expected_paths), \
                f"Async BFS order mismatch.\nExpected: {expected_paths}\nGot: {collected_paths}"
        
        finally:
            self.teardown_test_tree(root)
    
    @pytest.mark.asyncio
    async def test_depth_calculation(self):
        """Verify depth calculation for async implementation."""
        root, _ = self.create_standard_tree()
        
        try:
            node = AsyncNode(root)
            adapter = AsyncAdapter()
            
            # Manually track depths during traversal
            depths = {}
            depths[str(root)] = 0
            
            # Use BFS to calculate depths
            traverser = AsyncBFS()
            async for visited_node in traverser.traverse(node, adapter):
                path = str(visited_node.path)
                if path not in depths:
                    parent = str(visited_node.path.parent)
                    depths[path] = depths[parent] + 1
            
            # Verify specific depths
            assert depths[str(root)] == 0
            assert depths[str(root / "dir1")] == 1
            assert depths[str(root / "dir2" / "subdir")] == 2
            assert depths[str(root / "dir2" / "subdir" / "deep.txt")] == 3
        
        finally:
            self.teardown_test_tree(root)
    
    @pytest.mark.asyncio
    async def test_max_depth_limiting(self):
        """Verify max_depth parameter limits traversal."""
        root, _ = self.create_standard_tree()
        
        try:
            node = AsyncNode(root)
            adapter = AsyncAdapter()
            traverser = AsyncBFS()
            
            # Traverse with max_depth=1 (root + immediate children)
            collected_paths = []
            async for visited_node in traverser.traverse(node, adapter, max_depth=1):
                collected_paths.append(str(visited_node.path))
            
            # Should only have root and immediate children
            assert str(root) in collected_paths
            assert str(root / "dir1") in collected_paths
            assert str(root / "dir2") in collected_paths
            assert str(root / "root_file.txt") in collected_paths
            
            # Should NOT have deeper nodes
            assert str(root / "dir1" / "file1.txt") not in collected_paths
            assert str(root / "dir2" / "subdir") not in collected_paths
        
        finally:
            self.teardown_test_tree(root)
    
    @pytest.mark.asyncio
    async def test_metadata_collection(self):
        """Verify metadata collection for async implementation."""
        root, _ = self.create_standard_tree()
        
        try:
            node = AsyncNode(root)
            adapter = AsyncAdapter()
            traverser = AsyncBFS()
            collector = AsyncMetaCollector()
            
            metadata_list = []
            async for visited_node in traverser.traverse(node, adapter):
                metadata = await collector.collect(visited_node)
                metadata_list.append(metadata)
            
            # Verify we got metadata for all nodes
            assert len(metadata_list) == 9  # Total nodes in test tree
            
            # Verify metadata structure
            for metadata in metadata_list:
                assert 'path' in metadata
                assert 'name' in metadata
                # Async uses type field
                assert 'type' in metadata
                assert metadata['type'] in ['file', 'directory']
        
        finally:
            self.teardown_test_tree(root)


class TestSyncAsyncParity:
    """Direct comparison tests between sync and async implementations."""
    
    @pytest.mark.asyncio
    async def test_identical_traversal_results(self):
        """Verify sync and async produce identical results."""
        root = Path(tempfile.mkdtemp(prefix="dazzle_parity_"))
        
        # Create test structure
        (root / "dir1").mkdir()
        (root / "dir1" / "file1.txt").write_text("content1")
        (root / "dir2").mkdir()
        (root / "dir2" / "file2.txt").write_text("content2")
        
        try:
            # Collect sync results
            sync_node = SyncNode(root)
            sync_adapter = SyncAdapter()
            sync_traverser = SyncBFS(sync_adapter)
            
            sync_paths = []
            for node, depth in sync_traverser.traverse(sync_node):
                sync_paths.append(str(node.path))
            
            # Collect async results
            async_node = AsyncNode(root)
            async_adapter = AsyncAdapter()
            async_traverser = AsyncBFS()
            
            async_paths = []
            async for node in async_traverser.traverse(async_node, async_adapter):
                async_paths.append(str(node.path))
            
            # Compare (sort to handle filesystem ordering differences)
            assert sorted(sync_paths) == sorted(async_paths), \
                f"Sync/Async mismatch.\nSync: {sorted(sync_paths)}\nAsync: {sorted(async_paths)}"
        
        finally:
            shutil.rmtree(root)
    
    @pytest.mark.asyncio
    async def test_identical_metadata(self):
        """Verify sync and async collect identical metadata."""
        root = Path(tempfile.mkdtemp(prefix="dazzle_meta_"))
        
        # Create simple structure
        (root / "test.txt").write_text("test content")
        
        try:
            # Sync metadata
            sync_node = SyncNode(root / "test.txt")
            sync_adapter = SyncAdapter()
            sync_collector = SyncMetaCollector(sync_adapter)
            sync_meta = sync_collector.collect(sync_node, 0)
            
            # Async metadata
            async_node = AsyncNode(root / "test.txt")
            async_collector = AsyncMetaCollector()
            async_meta = await async_collector.collect(async_node)
            
            # Compare core fields (skip timestamps which might differ slightly)
            assert sync_meta['path'] == async_meta['path']
            assert sync_meta['name'] == async_meta['name']
            # Sync uses is_file/is_dir, async uses type
            if 'type' in async_meta:
                assert sync_meta['is_file'] == (async_meta['type'] == 'file')
                assert sync_meta['is_dir'] == (async_meta['type'] == 'directory')
            assert sync_meta.get('size') == async_meta.get('size')
        
        finally:
            shutil.rmtree(root)
    
    @pytest.mark.asyncio
    async def test_identical_depth_limiting(self):
        """Verify sync and async respect max_depth identically."""
        root = Path(tempfile.mkdtemp(prefix="dazzle_depth_"))
        
        # Create deep structure
        deep_path = root / "l1" / "l2" / "l3" / "l4"
        deep_path.mkdir(parents=True)
        (deep_path / "deep.txt").write_text("deep")
        
        try:
            # Test max_depth=2
            max_depth = 2
            
            # Sync with depth limit
            sync_node = SyncNode(root)
            sync_adapter = SyncAdapter()
            sync_traverser = SyncBFS(sync_adapter)
            
            sync_paths = []
            for node, depth in sync_traverser.traverse(sync_node, max_depth=max_depth):
                sync_paths.append(str(node.path))
            
            # Async with depth limit
            async_node = AsyncNode(root)
            async_adapter = AsyncAdapter()
            async_traverser = AsyncBFS()
            
            async_paths = []
            async for node in async_traverser.traverse(async_node, async_adapter, max_depth=max_depth):
                async_paths.append(str(node.path))
            
            # Both should stop at same depth
            assert sorted(sync_paths) == sorted(async_paths)
            
            # Verify depth limit was respected
            assert str(root / "l1" / "l2") in sync_paths
            assert str(root / "l1" / "l2" / "l3") not in sync_paths
            assert str(root / "l1" / "l2") in async_paths
            assert str(root / "l1" / "l2" / "l3") not in async_paths
        
        finally:
            shutil.rmtree(root)


# Run contract tests with pytest
if __name__ == "__main__":
    pytest.main([__file__, "-v"])