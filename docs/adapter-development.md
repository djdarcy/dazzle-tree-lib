# Adapter Development Guide

This guide explains how to create custom adapters for DazzleTreeLib to support new tree structures. Whether you're working with databases, APIs, cloud storage, or custom data structures, this guide will help you build both synchronous and asynchronous adapters.

## Table of Contents

1. [Understanding Adapters](#understanding-adapters)
2. [Creating a Synchronous Adapter](#creating-a-synchronous-adapter)
3. [Creating an Asynchronous Adapter](#creating-an-asynchronous-adapter)
4. [Complete Example: JSON Tree Adapter](#complete-example-json-tree-adapter)
5. [Testing Your Adapter](#testing-your-adapter)
6. [Best Practices](#best-practices)
7. [Common Patterns](#common-patterns)

## Understanding Adapters

Adapters are the bridge between DazzleTreeLib's traversal algorithms and your specific tree structure. They define:
- How to get children of a node
- How to get the parent of a node (optional)
- How to create node instances
- How to extract metadata from nodes

### Core Interfaces

Every adapter must implement these base classes:

**Synchronous Adapter:**
```python
from abc import ABC, abstractmethod
from typing import Iterator, Optional
from dazzletreelib.sync.core.nodes import TreeNode

class TreeAdapter(ABC):
    @abstractmethod
    def get_children(self, node: TreeNode) -> Iterator[TreeNode]:
        """Return an iterator of child nodes."""
        pass
    
    def get_parent(self, node: TreeNode) -> Optional[TreeNode]:
        """Return the parent node (optional)."""
        return None
```

**Asynchronous Adapter:**
```python
from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional
from dazzletreelib.aio.core.nodes import AsyncTreeNode

class AsyncTreeAdapter(ABC):
    @abstractmethod
    async def get_children(self, node: AsyncTreeNode) -> AsyncIterator[AsyncTreeNode]:
        """Return an async iterator of child nodes."""
        pass
    
    async def get_parent(self, node: AsyncTreeNode) -> Optional[AsyncTreeNode]:
        """Return the parent node (optional)."""
        return None
```

## Creating a Synchronous Adapter

Let's create a synchronous adapter for a database tree structure:

### Step 1: Define Your Node Class

```python
# dazzletreelib/sync/adapters/database.py
from dataclasses import dataclass
from typing import Any, Optional
from dazzletreelib.sync.core.nodes import TreeNode

@dataclass
class DatabaseNode(TreeNode):
    """Node representing a database record in a hierarchical structure."""
    
    id: int
    parent_id: Optional[int]
    name: str
    data: dict
    _connection: Any  # Database connection
    
    def identifier(self) -> str:
        """Unique identifier for this node."""
        return f"db_node_{self.id}"
    
    def is_leaf(self) -> bool:
        """Check if this node has no children."""
        cursor = self._connection.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM nodes WHERE parent_id = ?",
            (self.id,)
        )
        count = cursor.fetchone()[0]
        return count == 0
    
    @property
    def path(self):
        """Path-like representation for compatibility."""
        return f"/db/{self.name}"
```

### Step 2: Implement the Adapter

```python
# dazzletreelib/sync/adapters/database.py (continued)
from typing import Iterator, Optional
import sqlite3
from dazzletreelib.sync.core.adapters import TreeAdapter

class DatabaseAdapter(TreeAdapter):
    """Adapter for traversing database hierarchies."""
    
    def __init__(self, connection_string: str):
        self.connection = sqlite3.connect(connection_string)
    
    def get_children(self, node: DatabaseNode) -> Iterator[DatabaseNode]:
        """Get all child nodes from database."""
        cursor = self.connection.cursor()
        cursor.execute(
            """
            SELECT id, parent_id, name, data 
            FROM nodes 
            WHERE parent_id = ?
            ORDER BY name
            """,
            (node.id,)
        )
        
        for row in cursor:
            yield DatabaseNode(
                id=row[0],
                parent_id=row[1],
                name=row[2],
                data=json.loads(row[3]),
                _connection=self.connection
            )
    
    def get_parent(self, node: DatabaseNode) -> Optional[DatabaseNode]:
        """Get parent node from database."""
        if node.parent_id is None:
            return None
            
        cursor = self.connection.cursor()
        cursor.execute(
            """
            SELECT id, parent_id, name, data 
            FROM nodes 
            WHERE id = ?
            """,
            (node.parent_id,)
        )
        
        row = cursor.fetchone()
        if row:
            return DatabaseNode(
                id=row[0],
                parent_id=row[1],
                name=row[2],
                data=json.loads(row[3]),
                _connection=self.connection
            )
        return None
    
    def create_root_node(self, root_id: int) -> DatabaseNode:
        """Create a root node for traversal."""
        cursor = self.connection.cursor()
        cursor.execute(
            """
            SELECT id, parent_id, name, data 
            FROM nodes 
            WHERE id = ?
            """,
            (root_id,)
        )
        
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Node with id {root_id} not found")
            
        return DatabaseNode(
            id=row[0],
            parent_id=row[1],
            name=row[2],
            data=json.loads(row[3]),
            _connection=self.connection
        )
```

### Step 3: Use Your Adapter

```python
from dazzletreelib.sync import traverse_tree
from dazzletreelib.sync.adapters.database import DatabaseAdapter, DatabaseNode

# Initialize adapter
adapter = DatabaseAdapter("my_tree.db")

# Create root node
root = adapter.create_root_node(root_id=1)

# Traverse the tree
for node, depth in traverse_tree(root, adapter, max_depth=5):
    print(f"{'  ' * depth}{node.name}: {node.data}")
```

## Creating an Asynchronous Adapter

Now let's create the async version with batched parallel processing:

### Step 1: Define Async Node Class

```python
# dazzletreelib/aio/adapters/database.py
from dataclasses import dataclass
from typing import Optional
import aiosqlite
from dazzletreelib.aio.core.nodes import AsyncTreeNode

@dataclass
class AsyncDatabaseNode(AsyncTreeNode):
    """Async node for database records."""
    
    id: int
    parent_id: Optional[int]
    name: str
    data: dict
    _db_path: str  # Store path instead of connection
    
    async def identifier(self) -> str:
        """Unique identifier for this node."""
        return f"db_node_{self.id}"
    
    async def is_leaf(self) -> bool:
        """Check if this node has no children."""
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                "SELECT COUNT(*) FROM nodes WHERE parent_id = ?",
                (self.id,)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] == 0
    
    @property
    def path(self):
        """Path-like representation."""
        return f"/db/{self.name}"
```

### Step 2: Implement Async Adapter with Batching

```python
# dazzletreelib/aio/adapters/database.py (continued)
from typing import AsyncIterator, Optional, List
import asyncio
import aiosqlite
import json
from dazzletreelib.aio.core.adapters import AsyncTreeAdapter

class AsyncDatabaseAdapter(AsyncTreeAdapter):
    """Async adapter with batched parallel fetching."""
    
    def __init__(self, db_path: str, batch_size: int = 256, max_concurrent: int = 100):
        self.db_path = db_path
        self.batch_size = batch_size
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def get_children(self, node: AsyncDatabaseNode) -> AsyncIterator[AsyncDatabaseNode]:
        """Get children with batched fetching."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            # First, get all child IDs
            async with db.execute(
                "SELECT id FROM nodes WHERE parent_id = ? ORDER BY name",
                (node.id,)
            ) as cursor:
                child_ids = [row['id'] for row in await cursor.fetchall()]
            
            # Process in batches for optimal performance
            for i in range(0, len(child_ids), self.batch_size):
                batch_ids = child_ids[i:i + self.batch_size]
                
                # Fetch batch of children in parallel
                async with asyncio.TaskGroup() as tg:
                    tasks = []
                    for child_id in batch_ids:
                        task = tg.create_task(self._fetch_node(child_id))
                        tasks.append(task)
                
                # Yield results as they complete
                for task in tasks:
                    node = await task
                    if node:
                        yield node
    
    async def _fetch_node(self, node_id: int) -> Optional[AsyncDatabaseNode]:
        """Fetch a single node with semaphore control."""
        async with self.semaphore:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                
                async with db.execute(
                    """
                    SELECT id, parent_id, name, data 
                    FROM nodes 
                    WHERE id = ?
                    """,
                    (node_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                    
                    if row:
                        return AsyncDatabaseNode(
                            id=row['id'],
                            parent_id=row['parent_id'],
                            name=row['name'],
                            data=json.loads(row['data']),
                            _db_path=self.db_path
                        )
                    return None
    
    async def get_parent(self, node: AsyncDatabaseNode) -> Optional[AsyncDatabaseNode]:
        """Get parent node asynchronously."""
        if node.parent_id is None:
            return None
        
        return await self._fetch_node(node.parent_id)
    
    async def create_root_node(self, root_id: int) -> AsyncDatabaseNode:
        """Create root node for traversal."""
        node = await self._fetch_node(root_id)
        if not node:
            raise ValueError(f"Node with id {root_id} not found")
        return node
```

### Step 3: Use Async Adapter

```python
import asyncio
from dazzletreelib.aio import traverse_tree_async
from dazzletreelib.aio.adapters.database import AsyncDatabaseAdapter

async def main():
    # Initialize adapter with batching
    adapter = AsyncDatabaseAdapter(
        "my_tree.db",
        batch_size=256,
        max_concurrent=100
    )
    
    # Create root node
    root = await adapter.create_root_node(root_id=1)
    
    # Traverse asynchronously (3x+ faster!)
    async for node in traverse_tree_async(root, adapter=adapter, max_depth=5):
        print(f"{node.name}: {node.data}")

asyncio.run(main())
```

## Complete Example: JSON Tree Adapter

Here's a complete example of adapters for JSON tree structures:

### Synchronous JSON Adapter

```python
# dazzletreelib/sync/adapters/json_tree.py
from dataclasses import dataclass
from typing import Iterator, Optional, Any, Dict, List, Union
from pathlib import Path
import json
from dazzletreelib.sync.core.nodes import TreeNode
from dazzletreelib.sync.core.adapters import TreeAdapter

@dataclass
class JSONNode(TreeNode):
    """Node representing a JSON object or array element."""
    
    key: str
    value: Any
    parent_key: Optional[str] = None
    
    def identifier(self) -> str:
        return self.key
    
    def is_leaf(self) -> bool:
        return not isinstance(self.value, (dict, list))
    
    @property
    def path(self):
        return self.key

class JSONAdapter(TreeAdapter):
    """Adapter for traversing JSON structures."""
    
    def __init__(self, json_data: Union[str, Path, dict]):
        if isinstance(json_data, (str, Path)):
            with open(json_data) as f:
                self.data = json.load(f)
        else:
            self.data = json_data
        
        # Cache for parent lookups
        self._parent_map = {}
        self._build_parent_map()
    
    def _build_parent_map(self):
        """Build parent relationship map."""
        def map_parents(obj, parent_key=None, prefix=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    full_key = f"{prefix}.{key}" if prefix else key
                    self._parent_map[full_key] = parent_key
                    map_parents(value, full_key, full_key)
            elif isinstance(obj, list):
                for i, value in enumerate(obj):
                    full_key = f"{prefix}[{i}]"
                    self._parent_map[full_key] = parent_key
                    map_parents(value, full_key, full_key)
        
        map_parents(self.data)
    
    def get_children(self, node: JSONNode) -> Iterator[JSONNode]:
        """Get children of a JSON node."""
        if isinstance(node.value, dict):
            for key, value in node.value.items():
                child_key = f"{node.key}.{key}" if node.key != "root" else key
                yield JSONNode(
                    key=child_key,
                    value=value,
                    parent_key=node.key
                )
        elif isinstance(node.value, list):
            for i, value in enumerate(node.value):
                child_key = f"{node.key}[{i}]"
                yield JSONNode(
                    key=child_key,
                    value=value,
                    parent_key=node.key
                )
    
    def get_parent(self, node: JSONNode) -> Optional[JSONNode]:
        """Get parent of a JSON node."""
        if node.parent_key is None or node.parent_key == "root":
            return None
        
        # Navigate to parent in the data structure
        parent_value = self._get_value_by_key(node.parent_key)
        if parent_value is not None:
            return JSONNode(
                key=node.parent_key,
                value=parent_value,
                parent_key=self._parent_map.get(node.parent_key)
            )
        return None
    
    def _get_value_by_key(self, key: str) -> Any:
        """Get value from data structure by key path."""
        if key == "root":
            return self.data
        
        parts = key.replace("[", ".[").split(".")
        value = self.data
        
        for part in parts:
            if part.startswith("[") and part.endswith("]"):
                index = int(part[1:-1])
                value = value[index]
            elif part:
                value = value[part]
        
        return value
    
    def create_root_node(self) -> JSONNode:
        """Create root node for JSON tree."""
        return JSONNode(key="root", value=self.data)
```

### Asynchronous JSON Adapter

```python
# dazzletreelib/aio/adapters/json_tree.py
import asyncio
from dataclasses import dataclass
from typing import AsyncIterator, Optional, Any, Dict, List, Union
from pathlib import Path
import json
import aiofiles
from dazzletreelib.aio.core.nodes import AsyncTreeNode
from dazzletreelib.aio.core.adapters import AsyncTreeAdapter

@dataclass
class AsyncJSONNode(AsyncTreeNode):
    """Async node for JSON structures."""
    
    key: str
    value: Any
    parent_key: Optional[str] = None
    
    async def identifier(self) -> str:
        return self.key
    
    async def is_leaf(self) -> bool:
        return not isinstance(self.value, (dict, list))
    
    @property
    def path(self):
        return self.key

class AsyncJSONAdapter(AsyncTreeAdapter):
    """Async adapter for JSON with parallel child processing."""
    
    def __init__(self, batch_size: int = 256):
        self.batch_size = batch_size
        self.data = None
        self._parent_map = {}
    
    async def load_json(self, source: Union[str, Path, dict]):
        """Load JSON data asynchronously."""
        if isinstance(source, (str, Path)):
            async with aiofiles.open(source, mode='r') as f:
                content = await f.read()
                self.data = json.loads(content)
        else:
            self.data = source
        
        # Build parent map
        await self._build_parent_map()
    
    async def _build_parent_map(self):
        """Build parent relationship map asynchronously."""
        async def map_parents(obj, parent_key=None, prefix=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    full_key = f"{prefix}.{key}" if prefix else key
                    self._parent_map[full_key] = parent_key
                    await map_parents(value, full_key, full_key)
            elif isinstance(obj, list):
                for i, value in enumerate(obj):
                    full_key = f"{prefix}[{i}]"
                    self._parent_map[full_key] = parent_key
                    await map_parents(value, full_key, full_key)
        
        await map_parents(self.data)
    
    async def get_children(self, node: AsyncJSONNode) -> AsyncIterator[AsyncJSONNode]:
        """Get children with batched processing."""
        children = []
        
        if isinstance(node.value, dict):
            for key, value in node.value.items():
                child_key = f"{node.key}.{key}" if node.key != "root" else key
                children.append(AsyncJSONNode(
                    key=child_key,
                    value=value,
                    parent_key=node.key
                ))
        elif isinstance(node.value, list):
            for i, value in enumerate(node.value):
                child_key = f"{node.key}[{i}]"
                children.append(AsyncJSONNode(
                    key=child_key,
                    value=value,
                    parent_key=node.key
                ))
        
        # Process in batches
        for i in range(0, len(children), self.batch_size):
            batch = children[i:i + self.batch_size]
            
            # Simulate async I/O benefit (in real adapter, this would be actual I/O)
            await asyncio.sleep(0)  # Yield to event loop
            
            for child in batch:
                yield child
    
    async def create_root_node(self) -> AsyncJSONNode:
        """Create root node."""
        if self.data is None:
            raise ValueError("JSON data not loaded. Call load_json() first.")
        return AsyncJSONNode(key="root", value=self.data)
```

## Testing Your Adapter

### Contract Testing

Use contract tests to ensure your adapters work correctly:

```python
# tests/test_custom_adapter.py
import pytest
from dazzletreelib.tests._common.test_contracts import TraversalContract

class TestJSONAdapterSync(TraversalContract):
    """Test sync JSON adapter conforms to contract."""
    
    def create_adapter_and_root(self):
        """Create JSON adapter and root for testing."""
        test_data = {
            "name": "root",
            "children": [
                {"name": "child1", "value": 1},
                {"name": "child2", "children": [
                    {"name": "grandchild", "value": 2}
                ]}
            ]
        }
        
        adapter = JSONAdapter(test_data)
        root = adapter.create_root_node()
        return adapter, root

class TestJSONAdapterAsync(TraversalContract):
    """Test async JSON adapter conforms to contract."""
    
    async def create_adapter_and_root(self):
        """Create async JSON adapter and root."""
        test_data = {...}  # Same as above
        
        adapter = AsyncJSONAdapter()
        await adapter.load_json(test_data)
        root = await adapter.create_root_node()
        return adapter, root
```

### Performance Testing

```python
# tests/test_adapter_performance.py
import time
import asyncio
import pytest

def test_sync_adapter_performance(json_adapter, large_json_tree):
    """Test synchronous adapter performance."""
    start = time.perf_counter()
    
    count = 0
    for node, depth in traverse_tree(large_json_tree, json_adapter):
        count += 1
    
    elapsed = time.perf_counter() - start
    print(f"Sync: {count} nodes in {elapsed:.3f}s")
    
    # Should complete within reasonable time
    assert elapsed < 10.0

@pytest.mark.asyncio
async def test_async_adapter_performance(async_json_adapter, large_json_tree):
    """Test async adapter performance."""
    start = time.perf_counter()
    
    count = 0
    async for node in traverse_tree_async(large_json_tree, async_json_adapter):
        count += 1
    
    elapsed = time.perf_counter() - start
    print(f"Async: {count} nodes in {elapsed:.3f}s")
    
    # Should be significantly faster
    assert elapsed < 5.0
```

## Best Practices

### 1. Implement Both Sync and Async

Always provide both versions for maximum compatibility:

```python
# Good: Both implementations
class MyAdapter:  # Sync version
    def get_children(self, node): ...

class AsyncMyAdapter:  # Async version
    async def get_children(self, node): ...
```

### 2. Use Proper Resource Management

```python
# Good: Context managers for resources
class DatabaseAdapter:
    def __enter__(self):
        self.connection = sqlite3.connect(self.db_path)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.connection.close()

# Usage
with DatabaseAdapter("my.db") as adapter:
    for node in traverse_tree(root, adapter):
        process(node)
```

### 3. Handle Errors Gracefully

```python
class RobustAdapter:
    def get_children(self, node):
        try:
            # Attempt to get children
            return self._fetch_children(node)
        except NetworkError:
            # Log and return empty on network issues
            logger.warning(f"Failed to fetch children for {node}")
            return iter([])  # Empty iterator
```

### 4. Optimize for Performance

```python
class OptimizedAdapter:
    def __init__(self):
        # Cache frequently accessed data
        self._cache = {}
    
    def get_children(self, node):
        # Check cache first
        if node.id in self._cache:
            return self._cache[node.id]
        
        # Fetch and cache
        children = self._fetch_children(node)
        self._cache[node.id] = list(children)
        return iter(self._cache[node.id])
```

### 5. Document Your Adapter

```python
class WellDocumentedAdapter(TreeAdapter):
    """
    Adapter for XYZ tree structure.
    
    This adapter supports:
    - Feature A
    - Feature B
    - Feature C
    
    Example:
        adapter = WellDocumentedAdapter(config)
        root = adapter.create_root()
        for node in traverse_tree(root, adapter):
            print(node)
    
    Note:
        Requires XYZ library version 2.0+
    """
```

## Common Patterns

### Pattern 1: Lazy Loading

```python
class LazyAdapter:
    """Load data only when needed."""
    
    def get_children(self, node):
        # Don't load all children data at once
        for child_id in node.child_ids:
            # Load each child on demand
            yield self._load_node(child_id)
```

### Pattern 2: Connection Pooling

```python
class PooledAdapter:
    """Use connection pool for database adapters."""
    
    def __init__(self, pool_size=10):
        self.pool = ConnectionPool(size=pool_size)
    
    def get_children(self, node):
        with self.pool.get_connection() as conn:
            return self._fetch_children(conn, node)
```

### Pattern 3: Filtering at Adapter Level

```python
class FilteringAdapter:
    """Apply filters during traversal."""
    
    def __init__(self, base_adapter, filter_func):
        self.base = base_adapter
        self.filter = filter_func
    
    def get_children(self, node):
        for child in self.base.get_children(node):
            if self.filter(child):
                yield child
```

### Pattern 4: Metadata Enrichment

```python
class MetadataAdapter:
    """Enrich nodes with additional metadata."""
    
    def get_children(self, node):
        for child in self._base_children(node):
            # Add metadata
            child.metadata = self._fetch_metadata(child)
            child.permissions = self._get_permissions(child)
            child.stats = self._calculate_stats(child)
            yield child
```

## Adapter Checklist

Before publishing your adapter, ensure:

- [ ] Implements all required abstract methods
- [ ] Has both sync and async versions
- [ ] Includes comprehensive docstrings
- [ ] Has unit tests with >80% coverage
- [ ] Passes contract tests
- [ ] Handles errors gracefully
- [ ] Manages resources properly
- [ ] Documents any external dependencies
- [ ] Provides usage examples
- [ ] Includes performance benchmarks

## Contributing Your Adapter

To contribute your adapter to DazzleTreeLib:

1. Fork the repository
2. Create your adapter in appropriate directory
3. Add comprehensive tests
4. Update documentation
5. Submit a pull request

See [CONTRIBUTING.md](../CONTRIBUTING.md) for detailed guidelines.