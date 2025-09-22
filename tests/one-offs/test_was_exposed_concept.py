"""
Quick test to verify was_exposed() concept for Issue #43.

This test demonstrates the semantic distinction between:
- was_discovered(): Node was processed by the adapter
- was_exposed(): Node was yielded to the layer above
"""

import pytest
import asyncio
from dazzletreelib.aio.adapters.smart_caching import SmartCachingAdapter


class SimpleNode:
    def __init__(self, path):
        self.path = path

    def __str__(self):
        return str(self.path)


class MockAdapter:
    """Base adapter that provides all nodes."""

    async def get_children(self, node):
        if str(node.path) == '/':
            yield SimpleNode('/docs')
            yield SimpleNode('/src')
            yield SimpleNode('/.git')  # Hidden
            yield SimpleNode('/.env')  # Hidden

    async def get_depth(self, node):
        return 0

    async def get_parent(self, node):
        return None


@pytest.mark.asyncio
async def test_was_exposed_tracks_all_yielded_nodes():
    """Test that was_exposed() correctly tracks all nodes yielded by adapter."""

    # Create adapter with tracking
    mock = MockAdapter()
    adapter = SmartCachingAdapter(mock, track_traversal=True)

    # Get children of root
    root = SimpleNode('/')
    children = []
    async for child in adapter.get_children(root):
        children.append(str(child.path))

    # All nodes should be discovered (adapter saw them)
    assert adapter.was_discovered('/docs')
    assert adapter.was_discovered('/src')
    assert adapter.was_discovered('/.git')
    assert adapter.was_discovered('/.env')

    # All nodes should ALSO be exposed (adapter yielded them all)
    assert adapter.was_exposed('/docs')
    assert adapter.was_exposed('/src')
    assert adapter.was_exposed('/.git')
    assert adapter.was_exposed('/.env')

    # was_filtered() should return False for all (nothing was filtered at this layer)
    assert not adapter.was_filtered('/docs')
    assert not adapter.was_filtered('/src')
    assert not adapter.was_filtered('/.git')
    assert not adapter.was_filtered('/.env')

    print("✓ All nodes discovered and exposed by SmartCachingAdapter")
    print(f"  Children received: {children}")
    print(f"  was_discovered('/.git'): {adapter.was_discovered('/.git')}")
    print(f"  was_exposed('/.git'): {adapter.was_exposed('/.git')}")
    print(f"  was_filtered('/.git'): {adapter.was_filtered('/.git')}")


@pytest.mark.asyncio
async def test_conceptual_filter_layer():
    """
    Demonstrate the conceptual difference with filtering.

    NOTE: This shows what WOULD happen if SmartCachingAdapter
    could know about filtering above it. In reality, it can't,
    which is the architectural challenge.
    """

    # This test just documents the desired behavior
    # In practice, SmartCachingAdapter can't know what FilteringWrapper does above it

    mock = MockAdapter()
    adapter = SmartCachingAdapter(mock, track_traversal=True)

    # Simulate what a filter would do (but adapter doesn't know)
    root = SimpleNode('/')
    user_received = []

    async for child in adapter.get_children(root):
        # Simulate filter logic (not part of adapter)
        if not str(child.path).startswith('/.'):
            user_received.append(str(child.path))

    # Reality: Adapter exposed everything
    assert adapter.was_exposed('/.git')  # TRUE - adapter yielded it

    # But user didn't receive it due to external filtering
    assert '/.git' not in user_received  # TRUE - filter blocked it

    print("\n✓ Conceptual demonstration:")
    print(f"  Adapter exposed /.git: {adapter.was_exposed('/.git')}")
    print(f"  User received /.git: {'/.git' in user_received}")
    print("  This is the semantic confusion Issue #43 addresses!")


if __name__ == '__main__':
    asyncio.run(test_was_exposed_tracks_all_yielded_nodes())
    asyncio.run(test_conceptual_filter_layer())
    print("\n✓ All concept tests passed!")