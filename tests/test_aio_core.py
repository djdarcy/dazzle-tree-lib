"""Tests for async core abstractions."""

import asyncio
import pytest
from typing import AsyncIterator, Dict, Any, Optional

from dazzletreelib.aio.core import (
    AsyncTreeNode,
    AsyncTreeAdapter,
    AsyncBreadthFirstTraverser,
    AsyncDepthFirstTraverser,
    AsyncMetadataCollector,
    AsyncPathCollector,
)


# Test implementations

class MockAsyncNode(AsyncTreeNode):
    """Mock node for testing."""
    
    def __init__(self, id: str, children=None, metadata=None):
        self.id = id
        self.children = children or []
        self._metadata = metadata or {}
    
    async def identifier(self) -> str:
        return self.id
    
    async def metadata(self) -> Dict[str, Any]:
        # Simulate async I/O
        await asyncio.sleep(0)
        return self._metadata
    
    def is_leaf(self) -> bool:
        return len(self.children) == 0


class MockAsyncAdapter(AsyncTreeAdapter):
    """Mock adapter for testing."""
    
    async def get_children(self, node: MockAsyncNode) -> AsyncIterator[MockAsyncNode]:
        # Simulate async I/O for each child
        for child in node.children:
            await asyncio.sleep(0)
            yield child
    
    async def get_parent(self, node: MockAsyncNode) -> Optional[MockAsyncNode]:
        # Not implemented for this test
        return None
    
    async def get_depth(self, node: MockAsyncNode) -> int:
        # Simple depth calculation
        depth = 0
        current = node
        while hasattr(current, 'parent') and current.parent:
            depth += 1
            current = current.parent
        return depth


# Test fixtures

@pytest.fixture
def simple_tree():
    """Create a simple test tree.
    
    Structure:
        root
        ├── a
        │   ├── a1
        │   └── a2
        └── b
            └── b1
    """
    a1 = MockAsyncNode('a1')
    a2 = MockAsyncNode('a2')
    a = MockAsyncNode('a', children=[a1, a2])
    
    b1 = MockAsyncNode('b1')
    b = MockAsyncNode('b', children=[b1])
    
    root = MockAsyncNode('root', children=[a, b])
    
    return root


@pytest.fixture
def adapter():
    """Create a mock adapter."""
    return MockAsyncAdapter()


# Tests for AsyncTreeNode

@pytest.mark.asyncio
async def test_async_node_interface():
    """Test AsyncTreeNode interface."""
    node = MockAsyncNode('test', metadata={'size': 100})
    
    # Test identifier
    assert await node.identifier() == 'test'
    
    # Test metadata
    metadata = await node.metadata()
    assert metadata == {'size': 100}
    
    # Test is_leaf
    assert node.is_leaf() is True
    
    # Test with children
    child = MockAsyncNode('child')
    parent = MockAsyncNode('parent', children=[child])
    assert parent.is_leaf() is False


@pytest.mark.asyncio
async def test_async_node_optional_methods():
    """Test optional methods with defaults."""
    node = MockAsyncNode('test', metadata={'size': 100, 'modified_time': 1234567890})
    
    # Test display_name (should default to identifier)
    assert await node.display_name() == 'test'
    
    # Test size
    assert await node.size() == 100
    
    # Test modified_time
    assert await node.modified_time() == 1234567890


# Tests for AsyncTreeAdapter

@pytest.mark.asyncio
async def test_async_adapter_interface(simple_tree, adapter):
    """Test AsyncTreeAdapter interface."""
    # Test get_children
    children = []
    async for child in adapter.get_children(simple_tree):
        children.append(await child.identifier())
    
    assert children == ['a', 'b']
    
    # Test capabilities
    assert adapter.supports_capability('get_children')
    assert adapter.supports_capability('streaming')
    assert not adapter.supports_capability('unknown')


@pytest.mark.asyncio
async def test_async_adapter_context_manager(adapter):
    """Test adapter as async context manager."""
    async with adapter as ad:
        assert ad is adapter
        # Should not raise any exceptions


# Tests for Traversers

@pytest.mark.asyncio
async def test_breadth_first_traverser(simple_tree, adapter):
    """Test AsyncBreadthFirstTraverser."""
    traverser = AsyncBreadthFirstTraverser()
    
    nodes = []
    async for node in traverser.traverse(simple_tree, adapter):
        nodes.append(await node.identifier())
    
    # BFS order: root, a, b, a1, a2, b1
    assert nodes == ['root', 'a', 'b', 'a1', 'a2', 'b1']


@pytest.mark.asyncio
async def test_depth_first_traverser(simple_tree, adapter):
    """Test AsyncDepthFirstTraverser."""
    # Test pre-order
    traverser = AsyncDepthFirstTraverser(pre_order=True)
    
    nodes = []
    async for node in traverser.traverse(simple_tree, adapter):
        nodes.append(await node.identifier())
    
    # DFS pre-order: root, a, a1, a2, b, b1
    assert nodes == ['root', 'a', 'a1', 'a2', 'b', 'b1']
    
    # Test post-order
    traverser = AsyncDepthFirstTraverser(pre_order=False)
    
    nodes = []
    async for node in traverser.traverse(simple_tree, adapter):
        nodes.append(await node.identifier())
    
    # DFS post-order: a1, a2, a, b1, b, root
    assert nodes == ['a1', 'a2', 'a', 'b1', 'b', 'root']


@pytest.mark.asyncio
async def test_traverser_max_depth(simple_tree, adapter):
    """Test traverser with max_depth limit."""
    traverser = AsyncBreadthFirstTraverser()
    
    nodes = []
    async for node in traverser.traverse(simple_tree, adapter, max_depth=1):
        nodes.append(await node.identifier())
    
    # Only root and immediate children (depth 0 and 1)
    assert nodes == ['root', 'a', 'b']


# Tests for Collectors

@pytest.mark.asyncio
async def test_metadata_collector(simple_tree, adapter):
    """Test AsyncMetadataCollector."""
    collector = AsyncMetadataCollector()
    traverser = AsyncBreadthFirstTraverser()
    
    # Collect metadata during traversal
    async for node in traverser.traverse(simple_tree, adapter):
        await collector.collect(node)
    
    result = collector.get_result()
    
    # Should have metadata for all 6 nodes
    assert len(result) == 6
    
    # Check first node
    assert result[0]['id'] == 'root'
    assert result[0]['depth'] == 0


@pytest.mark.asyncio
async def test_path_collector(simple_tree, adapter):
    """Test AsyncPathCollector."""
    collector = AsyncPathCollector()
    traverser = AsyncBreadthFirstTraverser()
    
    # Create a depth tracking wrapper
    depth_map = {'root': 0, 'a': 1, 'b': 1, 'a1': 2, 'a2': 2, 'b1': 2}
    
    async for node in traverser.traverse(simple_tree, adapter):
        node_id = await node.identifier()
        await collector.collect(node, depth_map[node_id])
    
    paths = collector.get_result()
    
    # Check collected paths
    assert 'root' in paths
    assert 'root/a' in paths or 'a' in paths  # Depending on implementation
    assert len(paths) == 6


@pytest.mark.asyncio
async def test_collector_stream_processing():
    """Test collector stream processing."""
    collector = AsyncMetadataCollector()
    
    async def node_generator():
        """Generate test nodes."""
        for i in range(3):
            yield MockAsyncNode(f'node{i}', metadata={'index': i})
    
    result = await collector.process_stream(node_generator())
    
    assert len(result) == 3
    assert result[0]['id'] == 'node0'
    assert result[2]['index'] == 2


# Test error handling

@pytest.mark.asyncio
async def test_traverser_with_cycles():
    """Test traverser handles cycles correctly."""
    # Create a tree with a cycle
    node_a = MockAsyncNode('a')
    node_b = MockAsyncNode('b')
    node_a.children = [node_b]
    node_b.children = [node_a]  # Cycle!
    
    adapter = MockAsyncAdapter()
    traverser = AsyncBreadthFirstTraverser()
    
    nodes = []
    async for node in traverser.traverse(node_a, adapter):
        nodes.append(await node.identifier())
        if len(nodes) > 10:  # Safety check
            break
    
    # Should only visit each node once
    assert len(nodes) == 2
    assert set(nodes) == {'a', 'b'}