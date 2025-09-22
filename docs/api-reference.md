# API Reference

Complete API documentation for DazzleTreeLib's synchronous and asynchronous interfaces.

## Table of Contents

- [Synchronous API](#synchronous-api)
  - [Core Functions](#sync-core-functions)
  - [Node Classes](#sync-node-classes)
  - [Adapter Classes](#sync-adapter-classes)
  - [Traverser Classes](#sync-traverser-classes)
- [Asynchronous API](#asynchronous-api)
  - [Core Functions](#async-core-functions)
  - [Node Classes](#async-node-classes)
  - [Adapter Classes](#async-adapter-classes)
  - [Traverser Classes](#async-traverser-classes)
  - [Caching Adapters](#caching-adapters)
- [Common Types](#common-types)
  - [Enumerations](#enumerations)
  - [Type Definitions](#type-definitions)

---

## Synchronous API

### Sync Core Functions

#### `traverse_tree`

```python
def traverse_tree(
    root: TreeNode,
    adapter: TreeAdapter,
    strategy: str = 'bfs',
    max_depth: Optional[int] = None,
    filter_func: Optional[Callable[[TreeNode], bool]] = None
) -> Iterator[Tuple[TreeNode, int]]
```

Traverse a tree structure synchronously.

**Parameters:**
- `root`: The root node to start traversal from
- `adapter`: Adapter that defines how to navigate the tree
- `strategy`: Traversal strategy ('bfs', 'dfs_pre', 'dfs_post')
- `max_depth`: Maximum depth to traverse (None for unlimited)
- `filter_func`: Optional filter function to skip nodes

**Returns:**
- Iterator of (node, depth) tuples

**Example:**
```python
from dazzletreelib.sync import traverse_tree, FileSystemNode, FileSystemAdapter

root = FileSystemNode("/path/to/dir")
adapter = FileSystemAdapter()

for node, depth in traverse_tree(root, adapter, max_depth=3):
    print(f"{'  ' * depth}{node.path.name}")
```

#### `collect_tree_data`

```python
def collect_tree_data(
    root: TreeNode,
    adapter: TreeAdapter,
    data_requirement: DataRequirement = DataRequirement.BASIC,
    max_depth: Optional[int] = None
) -> Iterator[Tuple[TreeNode, Dict[str, Any]]]
```

Collect data from tree nodes during traversal.

**Parameters:**
- `root`: Root node to start from
- `adapter`: Tree adapter
- `data_requirement`: Level of data to collect
- `max_depth`: Maximum traversal depth

**Returns:**
- Iterator of (node, metadata) tuples

**Example:**
```python
from dazzletreelib.sync import collect_tree_data
from dazzletreelib._common.config import DataRequirement

for node, data in collect_tree_data(root, adapter, DataRequirement.METADATA):
    print(f"{node.path}: {data['size']} bytes")
```

#### `filter_tree`

```python
def filter_tree(
    root: TreeNode,
    adapter: TreeAdapter,
    predicate: Callable[[TreeNode], bool],
    max_depth: Optional[int] = None
) -> Iterator[TreeNode]
```

Filter tree nodes based on a predicate function.

**Parameters:**
- `root`: Root node
- `adapter`: Tree adapter
- `predicate`: Function that returns True for nodes to include
- `max_depth`: Maximum depth

**Returns:**
- Iterator of matching nodes

### Sync Node Classes

#### `TreeNode`

```python
class TreeNode(ABC):
    """Abstract base class for tree nodes."""
    
    @abstractmethod
    def identifier(self) -> str:
        """Return unique identifier for this node."""
    
    @abstractmethod
    def is_leaf(self) -> bool:
        """Check if this node has no children."""
    
    def size(self) -> Optional[int]:
        """Return size of node content (optional)."""
        return None
    
    def metadata(self) -> Dict[str, Any]:
        """Return node metadata (optional)."""
        return {}
```

#### `FileSystemNode`

```python
class FileSystemNode(TreeNode):
    """Node representing a file or directory."""
    
    def __init__(self, path: Union[str, Path]):
        """Initialize with file/directory path."""
        self.path = Path(path)
    
    def identifier(self) -> str:
        """Return absolute path as identifier."""
        return str(self.path.absolute())
    
    def is_leaf(self) -> bool:
        """Check if file (leaf) or directory (non-leaf)."""
        return self.path.is_file()
    
    def size(self) -> Optional[int]:
        """Return file size in bytes."""
        if self.path.is_file():
            return self.path.stat().st_size
        return None
    
    def is_file(self) -> bool:
        """Check if this node is a file."""
        return self.path.is_file()
    
    def is_dir(self) -> bool:
        """Check if this node is a directory."""
        return self.path.is_dir()
```

### Sync Adapter Classes

#### `TreeAdapter`

```python
class TreeAdapter(ABC):
    """Abstract base class for tree adapters."""
    
    @abstractmethod
    def get_children(self, node: TreeNode) -> Iterator[TreeNode]:
        """Get iterator of child nodes."""
    
    def get_parent(self, node: TreeNode) -> Optional[TreeNode]:
        """Get parent node (optional)."""
        return None
    
    def get_metadata(self, node: TreeNode) -> Dict[str, Any]:
        """Get node metadata (optional)."""
        return {}
```

#### `FileSystemAdapter`

```python
class FileSystemAdapter(TreeAdapter):
    """Adapter for filesystem traversal."""
    
    def __init__(self, follow_symlinks: bool = False):
        """Initialize filesystem adapter.
        
        Args:
            follow_symlinks: Whether to follow symbolic links
        """
        self.follow_symlinks = follow_symlinks
    
    def get_children(self, node: FileSystemNode) -> Iterator[FileSystemNode]:
        """Get child files and directories."""
        if node.path.is_dir():
            try:
                for child_path in sorted(node.path.iterdir()):
                    if not self.follow_symlinks and child_path.is_symlink():
                        continue
                    yield FileSystemNode(child_path)
            except (PermissionError, OSError):
                pass  # Skip inaccessible directories
```

### Sync Traverser Classes

#### `BreadthFirstTraverser`

```python
class BreadthFirstTraverser(Traverser):
    """Breadth-first (level-order) traversal."""
    
    def traverse(
        self,
        root: TreeNode,
        adapter: TreeAdapter,
        max_depth: Optional[int] = None
    ) -> Iterator[Tuple[TreeNode, int]]:
        """Traverse tree in breadth-first order."""
```

#### `DepthFirstPreOrderTraverser`

```python
class DepthFirstPreOrderTraverser(Traverser):
    """Depth-first pre-order traversal (visit node before children)."""
    
    def traverse(
        self,
        root: TreeNode,
        adapter: TreeAdapter,
        max_depth: Optional[int] = None
    ) -> Iterator[Tuple[TreeNode, int]]:
        """Traverse tree in DFS pre-order."""
```

---

## Asynchronous API

### Async Core Functions

#### `traverse_tree_async`

```python
async def traverse_tree_async(
    root: Union[Path, str, AsyncTreeNode],
    strategy: str = 'bfs',
    max_depth: Optional[int] = None,
    batch_size: int = 256,
    max_concurrent: int = 100,
    adapter: Optional[AsyncTreeAdapter] = None
) -> AsyncIterator[AsyncTreeNode]
```

Traverse a tree structure asynchronously with parallel processing.

**Parameters:**
- `root`: Path or root node to start traversal
- `strategy`: Traversal strategy ('bfs', 'dfs_pre', 'dfs_post')
- `max_depth`: Maximum depth to traverse
- `batch_size`: Number of children to process in parallel
- `max_concurrent`: Maximum concurrent I/O operations
- `adapter`: Optional custom adapter (auto-created for paths)

**Returns:**
- Async iterator of nodes (no depth information)

**Example:**
```python
from dazzletreelib.aio import traverse_tree_async
import asyncio

async def main():
    async for node in traverse_tree_async("/path", max_depth=3):
        print(f"Found: {node.path}")

asyncio.run(main())
```

#### `collect_tree_data_async`

```python
async def collect_tree_data_async(
    root: Union[Path, str, AsyncTreeNode],
    batch_size: int = 256,
    max_concurrent: int = 100
) -> List[Dict[str, Any]]
```

Collect data from all nodes asynchronously.

**Parameters:**
- `root`: Starting point for traversal
- `batch_size`: Batch size for parallel processing
- `max_concurrent`: Concurrency limit

**Returns:**
- List of metadata dictionaries

**Example:**
```python
async def analyze():
    data = await collect_tree_data_async("/path")
    total_size = sum(d.get('size', 0) for d in data)
    print(f"Total size: {total_size} bytes")
```

#### `filter_tree_async`

```python
async def filter_tree_async(
    root: Union[Path, str, AsyncTreeNode],
    predicate: Callable[[AsyncTreeNode], Awaitable[bool]],
    batch_size: int = 256,
    max_concurrent: int = 100
) -> List[AsyncTreeNode]
```

Filter tree nodes asynchronously.

**Parameters:**
- `root`: Starting point
- `predicate`: Async predicate function
- `batch_size`: Batch processing size
- `max_concurrent`: Concurrency limit

**Returns:**
- List of matching nodes

### Async Node Classes

#### `AsyncTreeNode`

```python
class AsyncTreeNode(ABC):
    """Abstract base class for async tree nodes."""
    
    @abstractmethod
    async def identifier(self) -> str:
        """Return unique identifier."""
    
    @abstractmethod
    async def is_leaf(self) -> bool:
        """Check if node has no children."""
    
    async def size(self) -> Optional[int]:
        """Return node size (optional)."""
        return None
    
    async def metadata(self) -> Dict[str, Any]:
        """Return node metadata (optional)."""
        return {}
```

#### `AsyncFileSystemNode`

```python
class AsyncFileSystemNode(AsyncTreeNode):
    """Async node for filesystem entries."""
    
    def __init__(self, path: Union[str, Path]):
        """Initialize with path."""
        self.path = Path(path)
    
    async def identifier(self) -> str:
        """Return absolute path."""
        return str(self.path.absolute())
    
    async def is_leaf(self) -> bool:
        """Check if file (leaf) or directory."""
        return self.path.is_file()
    
    async def size(self) -> Optional[int]:
        """Get file size asynchronously."""
        if self.path.is_file():
            stat = await asyncio.to_thread(self.path.stat)
            return stat.st_size
        return None
    
    async def metadata(self) -> Dict[str, Any]:
        """Get comprehensive metadata."""
        stat = await asyncio.to_thread(self.path.stat)
        return {
            'size': stat.st_size,
            'mtime': stat.st_mtime,
            'ctime': stat.st_ctime,
            'mode': stat.st_mode,
            'type': 'file' if self.path.is_file() else 'directory'
        }
```

### Async Adapter Classes

#### `AsyncTreeAdapter`

```python
class AsyncTreeAdapter(ABC):
    """Abstract base class for async adapters."""
    
    @abstractmethod
    async def get_children(
        self,
        node: AsyncTreeNode
    ) -> AsyncIterator[AsyncTreeNode]:
        """Get async iterator of children."""
    
    async def get_parent(
        self,
        node: AsyncTreeNode
    ) -> Optional[AsyncTreeNode]:
        """Get parent node (optional)."""
        return None
    
    async def get_metadata(
        self,
        node: AsyncTreeNode
    ) -> Dict[str, Any]:
        """Get node metadata (optional)."""
        return {}
```

#### `AsyncFileSystemAdapter`

```python
class AsyncFileSystemAdapter(AsyncTreeAdapter):
    """Async filesystem adapter with batching."""
    
    def __init__(
        self,
        batch_size: int = 256,
        max_concurrent: int = 100,
        follow_symlinks: bool = False
    ):
        """Initialize with batching parameters.
        
        Args:
            batch_size: Children to process per batch
            max_concurrent: Max concurrent operations
            follow_symlinks: Whether to follow symlinks
        """
        self.batch_size = batch_size
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.follow_symlinks = follow_symlinks
    
    async def get_children(
        self,
        node: AsyncFileSystemNode
    ) -> AsyncIterator[AsyncFileSystemNode]:
        """Get children with batched parallel processing."""
        if not node.path.is_dir():
            return
        
        # Get all children paths
        children = await asyncio.to_thread(
            lambda: sorted(node.path.iterdir())
        )
        
        # Process in batches
        for i in range(0, len(children), self.batch_size):
            batch = children[i:i + self.batch_size]
            
            async with asyncio.TaskGroup() as tg:
                tasks = []
                for child_path in batch:
                    if not self.follow_symlinks and child_path.is_symlink():
                        continue
                    
                    async def create_node(p):
                        async with self.semaphore:
                            return AsyncFileSystemNode(p)
                    
                    task = tg.create_task(create_node(child_path))
                    tasks.append(task)
            
            for task in tasks:
                yield await task
```

### Async Traverser Classes

#### `AsyncBreadthFirstTraverser`

```python
class AsyncBreadthFirstTraverser(AsyncTraverser):
    """Async breadth-first traversal with parallel level processing."""
    
    async def traverse(
        self,
        root: AsyncTreeNode,
        adapter: AsyncTreeAdapter,
        max_depth: Optional[int] = None
    ) -> AsyncIterator[AsyncTreeNode]:
        """Traverse tree in BFS order with parallelism."""
```

#### `AsyncDepthFirstTraverser`

```python
class AsyncDepthFirstTraverser(AsyncTraverser):
    """Async depth-first traversal."""
    
    async def traverse(
        self,
        root: AsyncTreeNode,
        adapter: AsyncTreeAdapter,
        max_depth: Optional[int] = None,
        order: str = 'pre'
    ) -> AsyncIterator[AsyncTreeNode]:
        """Traverse tree in DFS order.
        
        Args:
            order: 'pre' or 'post' order traversal
        """
```

### Caching Adapters

#### `CachingTreeAdapter`

```python
from dazzletreelib.aio.caching import CachingTreeAdapter

class CachingTreeAdapter(AsyncTreeAdapter):
    """Decorator adapter that adds caching to any AsyncTreeAdapter.
    
    Provides 55x+ speedup on repeated traversals by caching directory
    children lists. Uses Future-based coordination to prevent duplicate
    concurrent scans of the same directory.
    """
    
    def __init__(
        self,
        base_adapter: AsyncTreeAdapter,
        max_size: int = 10000,
        ttl: float = 300
    ):
        """Initialize caching adapter.
        
        Args:
            base_adapter: The adapter to wrap with caching
            max_size: Maximum number of directories to cache
            ttl: Time-to-live in seconds (from insertion time)
        """
```

**Features:**
- **55x+ speedup** on warm traversals
- **Future-based coordination** prevents duplicate concurrent scans
- **TTL-based expiration** for stale data prevention
- **Statistics tracking** for cache performance monitoring
- **Zero API changes** - drop-in replacement

**Example:**
```python
from dazzletreelib.aio import traverse_tree_async
from dazzletreelib.aio.adapters import FastAsyncFileSystemAdapter
from dazzletreelib.aio.caching import CachingTreeAdapter

# Create cached adapter
base = FastAsyncFileSystemAdapter()
cached = CachingTreeAdapter(base, max_size=50000, ttl=300)

# First traversal: ~40ms for 1000 nodes
async for node in traverse_tree_async(root, adapter=cached):
    process(node)

# Second traversal: <1ms (55x faster!)
async for node in traverse_tree_async(root, adapter=cached):
    process(node)

# Check cache statistics
stats = cached.get_cache_stats()
print(f"Cache hit rate: {stats['hit_rate']:.1%}")
print(f"Concurrent requests shared: {stats['concurrent_waits']}")
```

#### `FilesystemCachingAdapter`

```python
from dazzletreelib.aio.caching import FilesystemCachingAdapter

class FilesystemCachingAdapter(CachingTreeAdapter):
    """Filesystem-specific caching with mtime-based invalidation.
    
    Extends CachingTreeAdapter with dual-cache system:
    1. mtime cache for instant invalidation on file changes
    2. TTL cache as fallback when mtime unavailable
    """
    
    def __init__(
        self,
        base_adapter: AsyncTreeAdapter,
        max_size: int = 10000,
        ttl: float = 300
    ):
        """Initialize filesystem caching adapter.
        
        Args:
            base_adapter: Filesystem adapter to wrap
            max_size: Maximum cache entries
            ttl: TTL fallback when mtime unavailable
        """
```

**Features:**
- **Instant invalidation** when directory contents change (via mtime)
- **Graceful fallback** to TTL when mtime detection fails
- **Dual-cache system** for maximum reliability
- **Platform-aware** handling of filesystem differences

**Example:**
```python
from dazzletreelib.aio.caching import FilesystemCachingAdapter

# Filesystem-aware caching
cached = FilesystemCachingAdapter(base_adapter)

# Cache automatically invalidates when files change
async for node in traverse_tree_async(root, adapter=cached):
    process(node)

# Add a file to the directory
(root / "newfile.txt").touch()

# Next traversal detects change via mtime
async for node in traverse_tree_async(root, adapter=cached):
    process(node)  # Will include newfile.txt
```

#### Cache Management Methods

```python
# Get cache statistics
stats = cached.get_cache_stats()
# Returns: {
#     'hits': 450,
#     'misses': 50,
#     'hit_rate': 0.9,
#     'cache_size': 500,
#     'concurrent_waits': 4
# }

# Clear cache manually
cached.clear_cache()

# Check if caching is beneficial
if stats['hit_rate'] < 0.5:
    print("Consider disabling cache or adjusting TTL")
```

#### Performance Tuning

```python
# Conservative: Small cache, short TTL
cached = CachingTreeAdapter(base, max_size=1000, ttl=60)

# Aggressive: Large cache, long TTL
cached = CachingTreeAdapter(base, max_size=100000, ttl=3600)

# Filesystem-specific: Rely primarily on mtime
cached = FilesystemCachingAdapter(base, ttl=300)
```

---

## Common Types

### Enumerations

#### `DataRequirement`

```python
from enum import Enum

class DataRequirement(Enum):
    """Level of data to collect during traversal."""
    
    NONE = "none"           # No additional data
    BASIC = "basic"         # Name and type only
    METADATA = "metadata"   # Full metadata (size, dates, etc.)
    CONTENT = "content"     # Include file content (use carefully)
```

#### `TraversalStrategy`

```python
class TraversalStrategy(Enum):
    """Tree traversal strategies."""
    
    BREADTH_FIRST = "bfs"
    DEPTH_FIRST_PRE = "dfs_pre"
    DEPTH_FIRST_POST = "dfs_post"
```

### Type Definitions

```python
from typing import TypeVar, Protocol, Union
from pathlib import Path

# Type variables
NodeType = TypeVar('NodeType', bound='TreeNode')
AsyncNodeType = TypeVar('AsyncNodeType', bound='AsyncTreeNode')

# Path types
PathLike = Union[str, Path]

# Callback types
FilterFunc = Callable[[NodeType], bool]
AsyncFilterFunc = Callable[[AsyncNodeType], Awaitable[bool]]

ProgressCallback = Callable[[int, int], None]  # (current, total)
AsyncProgressCallback = Callable[[int, int], Awaitable[None]]

# Result types
TraversalResult = Tuple[NodeType, int]  # (node, depth)
MetadataResult = Tuple[NodeType, Dict[str, Any]]  # (node, metadata)
```

## Error Handling

Both sync and async APIs handle errors gracefully:

```python
# Errors are logged but don't stop traversal
try:
    for node, depth in traverse_tree(root, adapter):
        process(node)
except PermissionError:
    # Individual permission errors are caught internally
    # Only critical errors propagate
    pass

# Async version with timeout
try:
    async with asyncio.timeout(30):
        async for node in traverse_tree_async(root):
            await process(node)
except asyncio.TimeoutError:
    print("Traversal timed out")
```

## Performance Tips

### Synchronous Performance

```python
# Use generators for memory efficiency
def process_large_tree(root, adapter):
    # Good: Generator-based, memory efficient
    for node, depth in traverse_tree(root, adapter):
        if should_process(node):
            yield process(node)
    
    # Bad: Loads everything into memory
    # nodes = list(traverse_tree(root, adapter))
```

### Asynchronous Performance

```python
# Tune parameters for your use case
async def optimized_traversal(path):
    # Small tree: Lower concurrency
    if is_small_tree(path):
        async for node in traverse_tree_async(
            path,
            batch_size=32,
            max_concurrent=10
        ):
            await process(node)
    
    # Large tree: Higher concurrency
    else:
        async for node in traverse_tree_async(
            path,
            batch_size=512,
            max_concurrent=200
        ):
            await process(node)
```

## Complete Examples

### Sync Example: Find Duplicate Files

```python
from collections import defaultdict
from dazzletreelib.sync import traverse_tree, FileSystemNode, FileSystemAdapter

def find_duplicates(root_path: Path) -> Dict[int, List[Path]]:
    """Find duplicate files by size."""
    size_map = defaultdict(list)
    
    root = FileSystemNode(root_path)
    adapter = FileSystemAdapter()
    
    for node, _ in traverse_tree(root, adapter):
        if node.is_file():
            size = node.size()
            if size:
                size_map[size].append(node.path)
    
    # Return only duplicates
    return {
        size: paths
        for size, paths in size_map.items()
        if len(paths) > 1
    }
```

### Async Example: Parallel File Processing

```python
import asyncio
from dazzletreelib.aio import traverse_tree_async

async def process_files_parallel(root_path: Path):
    """Process all files in parallel."""
    tasks = []
    
    async for node in traverse_tree_async(root_path):
        if node.path.is_file():
            # Create task for each file
            task = asyncio.create_task(process_file(node))
            tasks.append(task)
            
            # Limit concurrent tasks
            if len(tasks) >= 100:
                done, tasks = await asyncio.wait(
                    tasks,
                    return_when=asyncio.FIRST_COMPLETED
                )
                # Process results
                for task in done:
                    result = await task
                    handle_result(result)
    
    # Process remaining tasks
    if tasks:
        results = await asyncio.gather(*tasks)
        for result in results:
            handle_result(result)
```