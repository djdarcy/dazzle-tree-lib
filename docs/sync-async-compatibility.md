# Sync/Async Compatibility Guide

This guide explains the differences between synchronous and asynchronous APIs in DazzleTreeLib and how to maintain compatibility when developing features that work with both.

## Table of Contents

1. [API Differences](#api-differences)
2. [Design Philosophy](#design-philosophy)
3. [Implementation Guidelines](#implementation-guidelines)
4. [Migration Strategies](#migration-strategies)
5. [Testing for Compatibility](#testing-for-compatibility)
6. [Common Pitfalls](#common-pitfalls)
7. [Performance Considerations](#performance-considerations)

## API Differences

### Key Differences Summary

| Feature | Synchronous | Asynchronous |
|---------|------------|--------------|
| **Import** | `from dazzletreelib.sync import ...` | `from dazzletreelib.aio import ...` |
| **Function Names** | `traverse_tree()` | `traverse_tree_async()` |
| **Return Type** | `Iterator[Tuple[Node, depth]]` | `AsyncIterator[Node]` |
| **Adapter Required** | Yes, passed to function | No, created internally |
| **Iteration** | `for node, depth in ...` | `async for node in ...` |
| **Node Methods** | `node.is_leaf()` | `await node.is_leaf()` |
| **Execution** | Direct call | `asyncio.run()` or await |
| **Batching** | Not available | `batch_size` parameter |
| **Concurrency** | Not available | `max_concurrent` parameter |

### Detailed API Comparison

#### Synchronous API

```python
from dazzletreelib.sync import (
    FileSystemNode,
    FileSystemAdapter,
    traverse_tree,
    collect_tree_data
)

# Setup requires explicit adapter
root_node = FileSystemNode("/path/to/dir")
adapter = FileSystemAdapter()

# Traversal returns (node, depth) tuples
for node, depth in traverse_tree(root_node, adapter, max_depth=3):
    # Synchronous method calls
    if node.is_leaf():
        size = node.size()  # Direct call
        print(f"{'  ' * depth}{node.path}: {size} bytes")

# Data collection
data = list(collect_tree_data(
    root_node,
    adapter,
    data_requirement=DataRequirement.METADATA
))
```

#### Asynchronous API

```python
from dazzletreelib.aio import (
    traverse_tree_async,
    collect_tree_data_async,
    filter_tree_async
)

# No adapter needed - created internally
# Returns nodes directly (no depth)
async for node in traverse_tree_async("/path/to/dir", max_depth=3):
    # Async method calls require await
    if await node.is_leaf():
        size = await node.size()  # Must await
        print(f"{node.path}: {size} bytes")

# Data collection with parallelism
data = await collect_tree_data_async(
    "/path/to/dir",
    batch_size=256,      # Async-specific
    max_concurrent=100   # Async-specific
)
```

## Design Philosophy

### Why Separate Implementations?

DazzleTreeLib intentionally maintains separate sync and async implementations rather than using compatibility layers. This design choice provides:

1. **Optimal Performance**: Each implementation is optimized for its execution model
2. **Clean APIs**: No confusing dual-mode functions or runtime switching
3. **Type Safety**: Proper type hints without Union types everywhere
4. **Maintainability**: Clear separation makes code easier to understand

### When to Use Each

#### Use Synchronous When:
- Working with small trees (<1000 nodes)
- CPU-bound operations dominate
- Integrating with sync-only codebases
- Debugging is a priority
- Simple, predictable execution is needed

#### Use Asynchronous When:
- Working with large trees (>1000 nodes)
- I/O operations dominate (file access, network)
- Need parallel processing
- Building async applications
- Performance is critical (3x+ speedup)

## Implementation Guidelines

### Creating Compatible Features

When implementing a feature that should work in both sync and async modes:

#### Step 1: Define Common Types

```python
# dazzletreelib/_common/types.py
from typing import Protocol, TypeVar, Generic

T = TypeVar('T')

class NodeProtocol(Protocol):
    """Common interface for nodes."""
    def identifier(self) -> str: ...
    
class Filter(Generic[T]):
    """Base filter that works with any node type."""
    def matches(self, node: T) -> bool:
        raise NotImplementedError
```

#### Step 2: Implement Sync Version

```python
# dazzletreelib/sync/filters.py
from typing import Iterator
from dazzletreelib._common.types import Filter
from dazzletreelib.sync.core.nodes import TreeNode

class SizeFilter(Filter[TreeNode]):
    """Filter nodes by size."""
    
    def __init__(self, min_size: int = 0, max_size: int = float('inf')):
        self.min_size = min_size
        self.max_size = max_size
    
    def matches(self, node: TreeNode) -> bool:
        """Check if node matches size criteria."""
        if node.is_leaf():
            size = node.size()  # Sync call
            return self.min_size <= size <= self.max_size
        return True

def filter_tree(
    root: TreeNode,
    adapter: TreeAdapter,
    filter: Filter[TreeNode]
) -> Iterator[TreeNode]:
    """Filter tree nodes synchronously."""
    for node, _ in traverse_tree(root, adapter):
        if filter.matches(node):
            yield node
```

#### Step 3: Implement Async Version

```python
# dazzletreelib/aio/filters.py
from typing import AsyncIterator
from dazzletreelib._common.types import Filter
from dazzletreelib.aio.core.nodes import AsyncTreeNode

class AsyncSizeFilter(Filter[AsyncTreeNode]):
    """Async filter nodes by size."""
    
    def __init__(self, min_size: int = 0, max_size: int = float('inf')):
        self.min_size = min_size
        self.max_size = max_size
    
    async def matches(self, node: AsyncTreeNode) -> bool:
        """Check if node matches size criteria."""
        if await node.is_leaf():  # Await async call
            size = await node.size()  # Await async call
            return self.min_size <= size <= self.max_size
        return True

async def filter_tree_async(
    root: Union[Path, AsyncTreeNode],
    filter: Filter[AsyncTreeNode],
    batch_size: int = 256,
    max_concurrent: int = 100
) -> AsyncIterator[AsyncTreeNode]:
    """Filter tree nodes asynchronously with batching."""
    async for node in traverse_tree_async(
        root,
        batch_size=batch_size,
        max_concurrent=max_concurrent
    ):
        if await filter.matches(node):  # Await async check
            yield node
```

### Shared Logic Pattern

When you have complex logic that should be shared:

```python
# dazzletreelib/_common/algorithms.py
def calculate_tree_statistics(
    node_count: int,
    total_size: int,
    max_depth: int
) -> dict:
    """Calculate tree statistics (pure function)."""
    return {
        'node_count': node_count,
        'total_size': total_size,
        'max_depth': max_depth,
        'average_size': total_size / node_count if node_count > 0 else 0
    }

# dazzletreelib/sync/stats.py
def get_tree_stats(root: TreeNode, adapter: TreeAdapter) -> dict:
    """Get tree statistics synchronously."""
    node_count = 0
    total_size = 0
    max_depth = 0
    
    for node, depth in traverse_tree(root, adapter):
        node_count += 1
        if node.is_leaf():
            total_size += node.size()
        max_depth = max(max_depth, depth)
    
    # Use shared logic
    return calculate_tree_statistics(node_count, total_size, max_depth)

# dazzletreelib/aio/stats.py
async def get_tree_stats_async(root: Path) -> dict:
    """Get tree statistics asynchronously."""
    node_count = 0
    total_size = 0
    max_depth = 0
    
    async for node in traverse_tree_async(root):
        node_count += 1
        if await node.is_leaf():
            total_size += await node.size()
        # Note: async version doesn't return depth directly
        # Would need separate tracking
    
    # Use shared logic
    return calculate_tree_statistics(node_count, total_size, max_depth)
```

## Migration Strategies

### Migrating from Sync to Async

#### Step 1: Identify I/O Boundaries

```python
# Before (Synchronous)
def process_tree(path: Path):
    root = FileSystemNode(path)
    adapter = FileSystemAdapter()
    
    results = []
    for node, depth in traverse_tree(root, adapter):
        if node.is_file():
            # I/O operation - good candidate for async
            content = node.path.read_text()
            results.append(process_content(content))
    
    return results
```

#### Step 2: Convert to Async

```python
# After (Asynchronous)
async def process_tree_async(path: Path):
    results = []
    
    async for node in traverse_tree_async(path):
        if node.path.is_file():
            # Async I/O - much faster
            async with aiofiles.open(node.path) as f:
                content = await f.read()
                results.append(process_content(content))
    
    return results
```

#### Step 3: Update Callers

```python
# Before
results = process_tree(Path("/data"))

# After
import asyncio
results = asyncio.run(process_tree_async(Path("/data")))
```

### Supporting Both APIs

If you need to support both sync and async callers:

```python
# dazzletreelib/hybrid.py
from typing import Union, Coroutine

def process_tree_hybrid(
    path: Path,
    async_mode: bool = False
) -> Union[list, Coroutine[None, None, list]]:
    """Process tree with optional async support."""
    if async_mode:
        return process_tree_async(path)
    else:
        return process_tree_sync(path)

# Usage
# Sync caller
results = process_tree_hybrid(path, async_mode=False)

# Async caller
results = await process_tree_hybrid(path, async_mode=True)
```

## Testing for Compatibility

### Contract Testing

Ensure both implementations behave identically:

```python
# tests/_common/test_contracts.py
from abc import ABC, abstractmethod
import pytest

class TraversalContract(ABC):
    """Base contract that both implementations must satisfy."""
    
    @abstractmethod
    def create_test_tree(self) -> Path:
        """Create a test tree structure."""
        pass
    
    def test_traversal_order(self):
        """Test that traversal order is consistent."""
        tree = self.create_test_tree()
        nodes = list(self.traverse(tree))
        
        # Verify BFS order
        assert nodes[0].name == "root"
        assert nodes[1].name == "child1"
        assert nodes[2].name == "child2"
    
    def test_max_depth(self):
        """Test depth limiting works."""
        tree = self.create_test_tree()
        nodes = list(self.traverse(tree, max_depth=1))
        
        # Should only get root and immediate children
        assert len(nodes) == 3
    
    @abstractmethod
    def traverse(self, tree: Path, **kwargs) -> list:
        """Traverse tree and return nodes."""
        pass

class TestSyncTraversal(TraversalContract):
    """Test sync implementation."""
    
    def traverse(self, tree: Path, **kwargs) -> list:
        root = FileSystemNode(tree)
        adapter = FileSystemAdapter()
        return [n for n, _ in traverse_tree(root, adapter, **kwargs)]

class TestAsyncTraversal(TraversalContract):
    """Test async implementation."""
    
    def traverse(self, tree: Path, **kwargs) -> list:
        async def _traverse():
            nodes = []
            async for node in traverse_tree_async(tree, **kwargs):
                nodes.append(node)
            return nodes
        
        return asyncio.run(_traverse())
```

### Performance Comparison Tests

```python
# tests/test_performance_comparison.py
import time
import asyncio
import pytest

def test_performance_improvement(large_tree):
    """Verify async is faster than sync."""
    # Sync timing
    start = time.perf_counter()
    sync_count = len(list(traverse_sync(large_tree)))
    sync_time = time.perf_counter() - start
    
    # Async timing
    start = time.perf_counter()
    async_count = asyncio.run(count_async(large_tree))
    async_time = time.perf_counter() - start
    
    # Verify same results
    assert sync_count == async_count
    
    # Verify performance improvement
    speedup = sync_time / async_time
    assert speedup > 2.0, f"Expected 2x+ speedup, got {speedup:.2f}x"
```

## Common Pitfalls

### Pitfall 1: Forgetting to Await

```python
# WRONG - Forgetting await
async def process(node):
    if node.is_leaf():  # Missing await!
        size = node.size()  # Missing await!
        return size

# CORRECT
async def process(node):
    if await node.is_leaf():  # Await async method
        size = await node.size()  # Await async method
        return size
```

### Pitfall 2: Mixing Sync and Async

```python
# WRONG - Can't use sync adapter with async traversal
adapter = FileSystemAdapter()  # Sync adapter
async for node in traverse_tree_async(root, adapter=adapter):  # Won't work!
    ...

# CORRECT - Use async adapter or let it create one
async for node in traverse_tree_async(root):  # Creates async adapter internally
    ...
```

### Pitfall 3: Blocking the Event Loop

```python
# WRONG - Blocking I/O in async context
async def process(node):
    with open(node.path) as f:  # Blocking I/O!
        content = f.read()
    return content

# CORRECT - Use async I/O
async def process(node):
    async with aiofiles.open(node.path) as f:  # Async I/O
        content = await f.read()
    return content
```

### Pitfall 4: Resource Exhaustion

```python
# WRONG - No concurrency limits
async def process_all(tree):
    tasks = []
    async for node in traverse_tree_async(tree):
        # Creating unlimited tasks!
        tasks.append(asyncio.create_task(process(node)))
    return await asyncio.gather(*tasks)

# CORRECT - Use concurrency limits
async def process_all(tree):
    results = []
    async for node in traverse_tree_async(
        tree,
        max_concurrent=100  # Limit concurrency
    ):
        result = await process(node)
        results.append(result)
    return results
```

## Performance Considerations

### Sync Performance Tips

1. **Use Generators**: Return iterators instead of lists
2. **Lazy Loading**: Load data only when needed
3. **Caching**: Cache expensive computations
4. **Early Exit**: Stop traversal when possible

```python
def find_first_match(root, adapter, predicate):
    """Stop traversal on first match."""
    for node, _ in traverse_tree(root, adapter):
        if predicate(node):
            return node  # Early exit
    return None
```

### Async Performance Tips

1. **Batch Operations**: Process multiple items together
2. **Concurrent Limits**: Prevent resource exhaustion
3. **Connection Pooling**: Reuse connections
4. **Async Context Managers**: Ensure proper cleanup

```python
async def optimized_traversal(tree):
    """Optimized async traversal."""
    # Use batching for better performance
    async for node in traverse_tree_async(
        tree,
        batch_size=512,      # Larger batches
        max_concurrent=200   # Higher concurrency
    ):
        await process(node)
```

### Choosing Parameters

| Tree Size | Batch Size | Max Concurrent | Expected Speedup |
|-----------|------------|----------------|------------------|
| <100 nodes | 32 | 10 | 1.5-2x |
| 100-1000 | 128 | 50 | 2-3x |
| 1000-10000 | 256 | 100 | 3-4x |
| >10000 | 512 | 200 | 4-5x |

## Best Practices Summary

1. **Keep Implementations Separate**: Don't try to share code that compromises performance
2. **Test Both Thoroughly**: Use contract tests to ensure behavioral compatibility
3. **Document Differences**: Clearly explain API differences in your code
4. **Provide Migration Path**: Show users how to move from sync to async
5. **Benchmark Everything**: Measure performance to validate async benefits
6. **Handle Errors Consistently**: Both APIs should handle errors similarly
7. **Use Type Hints**: Proper typing helps catch compatibility issues

## Conclusion

Maintaining sync/async compatibility in DazzleTreeLib requires careful design and implementation. By following the patterns and guidelines in this document, you can create features that work seamlessly with both APIs while maintaining optimal performance and clean code.