# Architecture Overview

## Design Philosophy

DazzleTreeLib follows a **dual-implementation architecture** where sync and async versions are intentionally kept separate to maximize performance and maintainability. This design decision allows each implementation to be optimized for its execution model without compromises.

## Package Structure

```
dazzletreelib/
├── __init__.py           # Package root, version info
├── _common/              # Shared components (minimal)
│   ├── __init__.py
│   ├── config.py        # Configuration enums and constants
│   └── types.py         # Shared type definitions
├── sync/                 # Synchronous implementation
│   ├── __init__.py
│   ├── api.py          # High-level sync API
│   ├── core/            # Core sync abstractions
│   │   ├── __init__.py
│   │   ├── nodes.py    # TreeNode base class
│   │   └── traversers.py # Sync traversal algorithms
│   └── adapters/        # Sync adapters
│       ├── __init__.py
│       └── filesystem.py # FileSystem adapter
└── aio/                  # Asynchronous implementation
    ├── __init__.py
    ├── api.py           # High-level async API
    ├── core/            # Core async abstractions
    │   ├── __init__.py
    │   ├── nodes.py     # AsyncTreeNode base class
    │   └── traversers.py # Async traversal algorithms
    └── adapters/        # Async adapters
        ├── __init__.py
        └── filesystem.py # AsyncFileSystem adapter
```

## Core Components

### 1. TreeNode Abstraction

The TreeNode represents any node in a tree structure:

**Synchronous TreeNode:**
```python
class TreeNode(ABC):
    @abstractmethod
    def identifier(self) -> str:
        """Unique identifier for this node."""
        pass
    
    @abstractmethod
    def is_leaf(self) -> bool:
        """Whether this node has no children."""
        pass
```

**Asynchronous AsyncTreeNode:**
```python
class AsyncTreeNode(ABC):
    @abstractmethod
    async def identifier(self) -> str:
        """Unique identifier for this node."""
        pass
    
    @abstractmethod
    async def is_leaf(self) -> bool:
        """Whether this node has no children."""
        pass
```

### 2. TreeAdapter Pattern

Adapters define how to navigate specific tree structures:

**Synchronous Adapter:**
```python
class TreeAdapter(ABC):
    @abstractmethod
    def get_children(self, node: TreeNode) -> Iterator[TreeNode]:
        """Get child nodes."""
        pass
    
    @abstractmethod
    def get_parent(self, node: TreeNode) -> Optional[TreeNode]:
        """Get parent node."""
        pass
```

**Asynchronous Adapter:**
```python
class AsyncTreeAdapter(ABC):
    @abstractmethod
    async def get_children(self, node: AsyncTreeNode) -> AsyncIterator[AsyncTreeNode]:
        """Get child nodes."""
        pass
    
    @abstractmethod
    async def get_parent(self, node: AsyncTreeNode) -> Optional[AsyncTreeNode]:
        """Get parent node."""
        pass
```

### 3. Traverser Implementations

Traversers implement different traversal algorithms:

- **BreadthFirstTraverser**: Level-order traversal
- **DepthFirstPreOrderTraverser**: Visit node before children
- **DepthFirstPostOrderTraverser**: Visit node after children

### 4. High-Level APIs

The library provides convenient high-level functions:

**Synchronous API:**
```python
def traverse_tree(
    root: TreeNode,
    adapter: TreeAdapter,
    strategy: str = 'bfs',
    max_depth: Optional[int] = None
) -> Iterator[Tuple[TreeNode, int]]:
    """Traverse a tree synchronously."""
```

**Asynchronous API:**
```python
async def traverse_tree_async(
    root: Union[Path, AsyncTreeNode],
    strategy: str = 'bfs',
    max_depth: Optional[int] = None,
    batch_size: int = 256,
    max_concurrent: int = 100
) -> AsyncIterator[AsyncTreeNode]:
    """Traverse a tree asynchronously with batched parallel processing."""
```

## Key Design Decisions

### 1. Separation of Sync and Async

**Why separate implementations?**
- **Performance**: Each can be optimized without compromise
- **Simplicity**: No complex compatibility layers
- **Maintainability**: Clear separation of concerns
- **Type Safety**: Proper type hints for each model

### 2. Minimal Shared Code

Only truly universal components are shared:
- Configuration enums (DataRequirement, TraversalStrategy)
- Type definitions
- Constants

### 3. Adapter Pattern

The adapter pattern enables:
- Support for any tree structure
- Easy extension without modifying core
- Consistent interface across data sources
- Testable abstractions

### 4. Streaming Iterators

Both implementations use iterators for memory efficiency:
- Sync: Python's `Iterator` protocol
- Async: `AsyncIterator` with `__aiter__` and `__anext__`

### 5. Batched Parallel Processing (Async)

The async implementation uses intelligent batching:
```python
# Process children in batches for optimal I/O
batch_size = 256  # Items per batch
max_concurrent = 100  # Concurrent operations limit
```

## Extension Points

### 1. Custom Adapters
Create adapters for new tree types by implementing the adapter interface.

### 2. Custom Traversers
Add new traversal algorithms by extending the traverser base class.

### 3. Data Collectors
Implement custom data extraction during traversal.

### 4. Filters and Transforms
Add pre/post processing of nodes during traversal.

## Performance Characteristics

### Synchronous Implementation
- **Predictable**: Linear execution, easy to debug
- **Memory Efficient**: One node at a time
- **CPU Bound**: Limited by single-thread execution
- **Best For**: Small trees, simple operations

### Asynchronous Implementation
- **Parallel I/O**: 3.3x+ speedup for I/O operations
- **Batched Processing**: Reduces overhead
- **Concurrent Limits**: Prevents resource exhaustion
- **Best For**: Large trees, I/O-heavy operations

## Thread Safety

### Synchronous
- Not thread-safe by default
- Use threading locks if sharing across threads

### Asynchronous
- Coroutine-safe within single event loop
- Use `asyncio.Lock` for shared state
- TaskGroup ensures structured concurrency

## Error Handling

Both implementations follow similar error strategies:

1. **Fail-Fast**: Invalid inputs raise immediately
2. **Graceful Degradation**: I/O errors logged but don't stop traversal
3. **Resource Cleanup**: Proper cleanup in finally blocks
4. **Timeout Support**: Both support operation timeouts

## Future Architecture Considerations

### Plugin System (Planned)
```python
@tree_plugin
class MyPlugin:
    async def pre_traverse(self, node): ...
    async def post_traverse(self, stats): ...
```

### Distributed Processing (Planned)
```python
cluster = DistributedTraversal(workers=10)
await cluster.traverse(massive_tree)
```

### Caching Layer (Planned)
```python
cache = TreeCache(ttl=300)
async for node in traverse_tree_async(root, cache=cache):
    # Automatic caching
```

## Best Practices

1. **Choose the Right API**: Use async for I/O-heavy operations
2. **Implement Both**: Adapters should support both sync and async
3. **Test Thoroughly**: Use contract tests to ensure compatibility
4. **Document Clearly**: Explain any API differences
5. **Benchmark**: Measure performance improvements