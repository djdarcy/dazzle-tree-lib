# Universal Adapters: How DazzleTreeLib Works with Any Tree

## What Are Universal Adapters?

DazzleTreeLib's universal adapter system is a design pattern that provides a single, consistent interface for traversing any tree-like data structure. Whether you're working with filesystems, databases, APIs, or custom data structures, the same traversal code works everywhere.

## The Problem They Solve

Traditional tree libraries force you to learn different APIs for different data sources:

```python
# Without universal adapters - different code for each source
import os
import json
import sqlite3

# Filesystem traversal
for root, dirs, files in os.walk("/path"):
    process_item(root)

# JSON traversal
def traverse_json(node):
    process_item(node)
    for child in node.get("children", []):
        traverse_json(child)

# Database traversal
cursor.execute("SELECT * FROM tree_table WHERE parent_id = ?", [node_id])
for row in cursor:
    process_item(row)
```

With DazzleTreeLib's universal adapters:

```python
from dazzletreelib.aio import traverse_tree_async

# Same code for ANY tree source!
async for node in traverse_tree_async(source, adapter=adapter):
    process_item(node)
```

## How Universal Adapters Work

### Core Concepts

1. **Node Abstraction**: Every tree element is a Node, regardless of source
2. **Adapter Interface**: Consistent methods for tree operations
3. **Traversal Separation**: Tree navigation logic is independent of data access
4. **Composition**: Adapters can wrap other adapters for added functionality

### The Adapter Interface

All adapters implement these core methods:

```python
class TreeAdapter:
    async def get_children(self, node: Node) -> List[Node]:
        """Return child nodes of the given node"""

    async def is_leaf(self, node: Node) -> bool:
        """Check if node has no children"""

    async def get_node_data(self, node: Node) -> Any:
        """Retrieve node's data/metadata"""
```

### Built-in Adapters

#### FileSystemAdapter
Traverses filesystem directories and files:

```python
from dazzletreelib.aio import FileSystemAdapter, traverse_tree_async

adapter = FileSystemAdapter()
async for node in traverse_tree_async("/home/user", adapter=adapter):
    print(f"Found: {node.path}")
```

#### FilteringAdapter
Wraps any adapter to add filtering:

```python
from dazzletreelib.aio.adapters import FilteringAdapter

# Only process Python files
def is_python_file(node):
    return node.path.suffix == '.py'

filtered = FilteringAdapter(base_adapter, predicate=is_python_file)
```

#### CachingAdapter
Adds intelligent caching to any adapter:

```python
from dazzletreelib.aio.adapters import CompletenessAwareCacheAdapter

# 4-5x speedup on repeated traversals
cached = CompletenessAwareCacheAdapter(base_adapter)
```

## Creating Custom Adapters

### Example: JSON Tree Adapter

```python
from dazzletreelib.core import Node, TreeAdapter

class JSONAdapter(TreeAdapter):
    async def get_children(self, node: Node) -> List[Node]:
        data = node.data
        if isinstance(data, dict):
            children = data.get('children', [])
            return [Node(child) for child in children]
        return []

    async def is_leaf(self, node: Node) -> bool:
        return not isinstance(node.data, dict) or 'children' not in node.data

    async def get_node_data(self, node: Node) -> Any:
        return node.data.get('value', node.data)

# Use it like any other adapter
json_tree = {"value": "root", "children": [...]}
adapter = JSONAdapter()
async for node in traverse_tree_async(Node(json_tree), adapter=adapter):
    print(node.data)
```

### Example: Database Tree Adapter

```python
class DatabaseAdapter(TreeAdapter):
    def __init__(self, connection):
        self.conn = connection

    async def get_children(self, node: Node) -> List[Node]:
        cursor = self.conn.execute(
            "SELECT * FROM nodes WHERE parent_id = ?",
            [node.data['id']]
        )
        return [Node(dict(row)) for row in cursor]

    async def is_leaf(self, node: Node) -> bool:
        cursor = self.conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE parent_id = ?",
            [node.data['id']]
        )
        return cursor.fetchone()[0] == 0
```

## Composing Adapters

The real power comes from composing adapters:

```python
# Start with a base adapter
base = FileSystemAdapter()

# Add filtering
filtered = FilteringAdapter(base, predicate=is_python_file)

# Add caching for performance
cached = CompletenessAwareCacheAdapter(filtered)

# Add custom behavior
class LoggingAdapter(TreeAdapter):
    def __init__(self, base):
        self.base = base

    async def get_children(self, node):
        children = await self.base.get_children(node)
        print(f"Node {node} has {len(children)} children")
        return children

logged = LoggingAdapter(cached)

# Use the composed adapter
async for node in traverse_tree_async(root, adapter=logged):
    # Benefits from filtering, caching, and logging!
    process(node)
```

## Async/Sync Parity

Every adapter has both async and sync versions with identical APIs:

```python
# Async version
from dazzletreelib.aio import FileSystemAdapter as AsyncFSAdapter
async for node in traverse_tree_async(root, adapter=AsyncFSAdapter()):
    await process_async(node)

# Sync version
from dazzletreelib.sync import FileSystemAdapter as SyncFSAdapter
for node, depth in traverse_tree(root, adapter=SyncFSAdapter()):
    process_sync(node)
```

## Why This Matters

1. **Write Once, Use Everywhere**: Your traversal logic works with any tree
2. **Testability**: Swap real adapters for test adapters easily
3. **Extensibility**: Add new data sources without changing traversal code
4. **Composition**: Build complex behaviors from simple pieces
5. **Performance**: Add caching/optimization to any adapter

## Advanced Patterns

### Adapter Factories

```python
def create_adapter(source_type: str, **kwargs):
    adapters = {
        'filesystem': FileSystemAdapter,
        'database': DatabaseAdapter,
        'api': APIAdapter,
        'json': JSONAdapter,
    }
    adapter_class = adapters[source_type]
    return adapter_class(**kwargs)

# Dynamic adapter selection
adapter = create_adapter(config.source_type)
```

### Multi-Source Traversal

```python
class MultiSourceAdapter(TreeAdapter):
    def __init__(self, adapters: Dict[str, TreeAdapter]):
        self.adapters = adapters

    async def get_children(self, node: Node) -> List[Node]:
        # Route to appropriate adapter based on node type
        adapter = self.adapters[node.source_type]
        return await adapter.get_children(node)

# Traverse filesystem AND database in one operation!
multi = MultiSourceAdapter({
    'fs': FileSystemAdapter(),
    'db': DatabaseAdapter(conn)
})
```

## Comparison with Other Libraries

Unlike other Python tree libraries:

- **anytree**: Requires manual parent/child relationship setup for each source
- **treelib**: No abstraction for different data sources
- **NetworkX**: Plugin system for algorithms, not data sources
- **DazzleTreeLib**: Universal adapters work with ANY tree structure

## Next Steps

- See [examples](../examples/) for real-world adapter usage
- Read about [caching adapters](caching.md) for performance optimization
- Check the [API reference](../api/) for complete adapter documentation
- Learn about [creating custom adapters](../tutorials/custom-adapters.md)

## Summary

DazzleTreeLib's universal adapter system is what makes it unique in the Python ecosystem. By separating traversal logic from data access and providing a consistent interface, it enables you to write tree processing code once and use it everywhere. The composable nature of adapters means you can build sophisticated tree processing pipelines while keeping your code clean and maintainable.