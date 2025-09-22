# The Adapter Pattern in DazzleTreeLib

## A Practical Guide for Developers

This guide explains how DazzleTreeLib uses the adapter pattern with composition to create a flexible, extensible tree traversal system. If you're new to design patterns, start with our [Composition vs Inheritance](./composition-vs-inheritance.md) guide first.

---

## Table of Contents
1. [What is an Adapter?](#what-is-an-adapter)
2. [Why We Need Adapters](#why-we-need-adapters) 
3. [The DazzleTreeLib Adapter System](#the-dazzletreelib-adapter-system)
4. [Building Your Own Adapter](#building-your-own-adapter)
5. [Composing Adapters](#composing-adapters)
6. [Real-World Examples](#real-world-examples)
7. [Best Practices](#best-practices)

---

## What is an Adapter?

Think of an adapter like a universal translator. Just as a power adapter lets you plug your laptop into different types of outlets around the world, a software adapter lets different pieces of code work together even when they weren't originally designed to.

### Real-World Analogy

Imagine you have:
- A tree traversal algorithm that knows how to walk through any tree structure
- Different types of trees: filesystems, databases, JSON objects, Git repositories

The adapter is the bridge that lets the same traversal algorithm work with all these different tree types:

```
Traversal Algorithm <---> Adapter <---> Actual Tree Structure
                            |
                    Translates between
                    generic operations
                    and specific implementation
```

---

## Why We Need Adapters

### The Problem

Without adapters, we'd need separate traversal code for each tree type:

```python
# WITHOUT ADAPTERS - Lots of duplicate code!

def traverse_filesystem(path):
    for item in os.listdir(path):
        # Filesystem-specific logic
        pass

def traverse_database(connection):
    cursor = connection.execute("SELECT * FROM nodes")
    # Database-specific logic
    pass

def traverse_json(data):
    for key, value in data.items():
        # JSON-specific logic
        pass
```

### The Solution

With adapters, we write the traversal logic once:

```python
# WITH ADAPTERS - Write once, use everywhere!

async def traverse_tree(root, adapter):
    """Generic traversal that works with ANY adapter."""
    queue = [root]
    while queue:
        node = queue.pop(0)
        yield node
        children = await adapter.get_children(node)
        queue.extend(children)

# Now use with different adapters
async for node in traverse_tree(root, FileSystemAdapter()):
    print(f"File: {node}")

async for node in traverse_tree(root, DatabaseAdapter()):
    print(f"DB Record: {node}")

async for node in traverse_tree(root, JSONAdapter()):
    print(f"JSON Node: {node}")
```

---

## The DazzleTreeLib Adapter System

### Core Concepts

DazzleTreeLib defines a standard interface that all adapters must implement:

```python
class TreeAdapter:
    """Base interface for all tree adapters."""
    
    async def get_children(self, node) -> List[Node]:
        """Get child nodes of the given node."""
        raise NotImplementedError
    
    async def is_leaf(self, node) -> bool:
        """Check if node is a leaf (has no children)."""
        raise NotImplementedError
    
    async def get_node_data(self, node) -> Dict:
        """Get metadata about the node."""
        raise NotImplementedError
```

### The Current Adapter Hierarchy

```
TreeAdapter (Base Interface)
├── AsyncFileSystemAdapter (Concrete Implementation)
│   └── Uses os.scandir for fast filesystem access
├── AsyncFilteredFileSystemAdapter (Wrapper/Decorator)
│   └── Wraps any adapter to add filtering
└── CachingTreeAdapter (Wrapper/Decorator)
    └── Wraps any adapter to add caching
```

### How Adapters Work Together

Here's the flow when you use multiple adapters:

```python
# User creates a stack of adapters
base = AsyncFileSystemAdapter()
filtered = AsyncFilteredFileSystemAdapter(base, include_patterns=['*.py'])
cached = CachingTreeAdapter(filtered)

# When traverse_tree calls cached.get_children():
# 1. CachingTreeAdapter checks its cache
# 2. If miss, calls filtered.get_children()
# 3. FilteredAdapter calls base.get_children()
# 4. FileSystemAdapter actually reads the disk
# 5. Results flow back up through the chain
# 6. FilteredAdapter removes non-.py files
# 7. CachingTreeAdapter stores result in cache
# 8. User receives filtered, cached results
```

---

## Building Your Own Adapter

### Example 1: Git Repository Adapter

Let's build an adapter for traversing Git repositories:

```python
import git  # GitPython library

class GitTreeAdapter:
    """Adapter for traversing Git repository structure."""
    
    def __init__(self, repo_path, branch='main'):
        self.repo = git.Repo(repo_path)
        self.branch = branch
    
    async def get_children(self, node):
        """Get child nodes in the Git tree."""
        if node.is_root:
            # Return top-level items from the branch
            tree = self.repo.heads[self.branch].commit.tree
            return [GitNode(item) for item in tree]
        elif node.type == 'tree':
            # Return items within a directory
            return [GitNode(item) for item in node.git_object]
        else:
            # Files have no children
            return []
    
    async def is_leaf(self, node):
        """Check if this is a file (leaf) or directory (branch)."""
        return node.type == 'blob'
    
    async def get_node_data(self, node):
        """Get Git metadata for the node."""
        return {
            'path': node.path,
            'type': node.type,
            'size': node.size if node.type == 'blob' else None,
            'sha': node.hexsha,
            'last_modified': node.committed_date
        }

class GitNode:
    """Wrapper for Git tree/blob objects."""
    def __init__(self, git_object):
        self.git_object = git_object
        self.path = git_object.path
        self.type = git_object.type  # 'tree' or 'blob'
        self.hexsha = git_object.hexsha
```

### Example 2: Database Adapter

An adapter for hierarchical data in a database:

```python
class DatabaseTreeAdapter:
    """Adapter for traversing hierarchical database records."""
    
    def __init__(self, connection, table_name):
        self.conn = connection
        self.table = table_name
    
    async def get_children(self, node):
        """Get child records from database."""
        query = f"""
            SELECT id, name, parent_id, data 
            FROM {self.table}
            WHERE parent_id = ?
        """
        
        async with self.conn.execute(query, (node.id,)) as cursor:
            rows = await cursor.fetchall()
            return [DatabaseNode(row) for row in rows]
    
    async def is_leaf(self, node):
        """Check if node has any children."""
        query = f"""
            SELECT COUNT(*) FROM {self.table}
            WHERE parent_id = ?
        """
        
        async with self.conn.execute(query, (node.id,)) as cursor:
            count = await cursor.fetchone()
            return count[0] == 0
    
    async def get_node_data(self, node):
        """Get node metadata."""
        return {
            'id': node.id,
            'name': node.name,
            'data': node.data,
            'parent_id': node.parent_id
        }

class DatabaseNode:
    """Represents a database record as a tree node."""
    def __init__(self, row):
        self.id = row['id']
        self.name = row['name']
        self.parent_id = row['parent_id']
        self.data = row['data']
```

### Example 3: JSON/API Adapter

For traversing JSON data or REST APIs:

```python
class JSONTreeAdapter:
    """Adapter for traversing JSON structures."""
    
    def __init__(self, data=None, api_client=None):
        self.data = data
        self.api_client = api_client
    
    async def get_children(self, node):
        """Get child nodes from JSON structure."""
        if isinstance(node.value, dict):
            # Object: children are key-value pairs
            return [
                JSONNode(key=k, value=v, path=f"{node.path}.{k}")
                for k, v in node.value.items()
            ]
        elif isinstance(node.value, list):
            # Array: children are indexed elements
            return [
                JSONNode(key=i, value=v, path=f"{node.path}[{i}]")
                for i, v in enumerate(node.value)
            ]
        else:
            # Primitive value: no children
            return []
    
    async def is_leaf(self, node):
        """Check if this is a primitive value."""
        return not isinstance(node.value, (dict, list))
    
    async def get_node_data(self, node):
        """Get node metadata."""
        return {
            'path': node.path,
            'key': node.key,
            'type': type(node.value).__name__,
            'value': node.value if self.is_leaf(node) else None
        }

class JSONNode:
    """Represents a node in JSON structure."""
    def __init__(self, key, value, path):
        self.key = key
        self.value = value
        self.path = path
```

---

## Composing Adapters

### The Power of Wrapper Adapters

Wrapper adapters add functionality to ANY other adapter:

```python
class RateLimitingAdapter:
    """Limits the rate of operations on any adapter."""
    
    def __init__(self, base_adapter, max_per_second=10):
        self.base = base_adapter
        self.max_per_second = max_per_second
        self.last_call = 0
    
    async def get_children(self, node):
        # Enforce rate limit
        await self._rate_limit()
        # Delegate to wrapped adapter
        return await self.base.get_children(node)
    
    async def _rate_limit(self):
        now = time.time()
        time_since_last = now - self.last_call
        if time_since_last < 1.0 / self.max_per_second:
            await asyncio.sleep(1.0 / self.max_per_second - time_since_last)
        self.last_call = time.time()
    
    # Delegate all other methods
    def __getattr__(self, name):
        return getattr(self.base, name)
```

### Combining Multiple Adapters

You can stack adapters like building blocks:

```python
# Start with a base adapter for your data source
base = GitTreeAdapter(repo_path='/path/to/repo')

# Add filtering to only see Python files
filtered = AsyncFilteredFileSystemAdapter(
    base_adapter=base,
    include_patterns=['*.py']
)

# Add caching to avoid repeated Git operations
cached = CachingTreeAdapter(
    base_adapter=filtered,
    ttl=300  # Cache for 5 minutes
)

# Add rate limiting to be nice to the Git server
rate_limited = RateLimitingAdapter(
    base_adapter=cached,
    max_per_second=100
)

# Add logging for debugging
logged = LoggingAdapter(
    base_adapter=rate_limited,
    logger=logging.getLogger('git.traversal')
)

# Now traverse with all features combined!
async for node in traverse_tree(root, logged):
    print(node)  # Filtered, cached, rate-limited, logged!
```

---

## Real-World Examples

### Example 1: Multi-Source Tree Aggregator

Combine trees from different sources:

```python
class MultiSourceAdapter:
    """Aggregates multiple tree sources into one virtual tree."""
    
    def __init__(self, adapters_map):
        """
        adapters_map: {
            'filesystem': FileSystemAdapter(),
            'database': DatabaseAdapter(),
            'api': APIAdapter()
        }
        """
        self.adapters = adapters_map
    
    async def get_children(self, node):
        """Get children from appropriate source."""
        if node.is_root:
            # Root shows all sources
            return [
                SourceNode(name=name, adapter=adapter)
                for name, adapter in self.adapters.items()
            ]
        else:
            # Delegate to the appropriate adapter
            return await node.adapter.get_children(node)
```

### Example 2: Virtual Filesystem Overlay

Create a virtual view over a real filesystem:

```python
class VirtualOverlayAdapter:
    """Adds virtual nodes to a real filesystem."""
    
    def __init__(self, base_adapter, virtual_nodes):
        self.base = base_adapter
        self.virtual_nodes = virtual_nodes  # Dict of path -> virtual children
    
    async def get_children(self, node):
        # Get real children
        real_children = await self.base.get_children(node)
        
        # Add virtual children if any
        virtual = self.virtual_nodes.get(node.path, [])
        
        # Combine both
        return real_children + virtual
```

### Example 3: Permission-Aware Adapter

Filter based on user permissions:

```python
class PermissionAdapter:
    """Only shows nodes the user has permission to access."""
    
    def __init__(self, base_adapter, user, permission_checker):
        self.base = base_adapter
        self.user = user
        self.checker = permission_checker
    
    async def get_children(self, node):
        # Get all children
        all_children = await self.base.get_children(node)
        
        # Filter by permissions
        allowed = []
        for child in all_children:
            if await self.checker.can_read(self.user, child):
                allowed.append(child)
        
        return allowed
```

---

## Best Practices

### 1. Keep Adapters Focused

Each adapter should do ONE thing well:

```python
# GOOD: Single responsibility
class CachingAdapter:
    """ONLY handles caching."""
    pass

class FilteringAdapter:
    """ONLY handles filtering."""
    pass

# BAD: Too many responsibilities
class DoEverythingAdapter:
    """Caches, filters, logs, rate limits, etc."""
    pass
```

### 2. Use Type Hints

Make your adapters self-documenting:

```python
from typing import List, Dict, Optional, Any

class MyAdapter:
    async def get_children(self, node: Node) -> List[Node]:
        """Get child nodes."""
        pass
    
    async def get_node_data(self, node: Node) -> Dict[str, Any]:
        """Get node metadata."""
        pass
```

### 3. Handle Errors Gracefully

```python
class RobustAdapter:
    async def get_children(self, node):
        try:
            return await self.base.get_children(node)
        except PermissionError:
            # No permission? Return empty list
            logger.warning(f"Permission denied for {node.path}")
            return []
        except Exception as e:
            # Log unexpected errors but don't crash
            logger.error(f"Error getting children of {node}: {e}")
            return []
```

### 4. Provide Factory Functions

Make it easy to create common configurations:

```python
def create_filesystem_adapter(
    path,
    include_patterns=None,
    exclude_patterns=None,
    use_cache=True,
    cache_ttl=60
):
    """Factory function for common filesystem adapter setup."""
    
    # Start with base
    adapter = AsyncFileSystemAdapter()
    
    # Add filtering if needed
    if include_patterns or exclude_patterns:
        adapter = AsyncFilteredFileSystemAdapter(
            base_adapter=adapter,
            include_patterns=include_patterns,
            exclude_patterns=exclude_patterns
        )
    
    # Add caching if requested
    if use_cache:
        adapter = CachingTreeAdapter(
            base_adapter=adapter,
            ttl=cache_ttl
        )
    
    return adapter
```

### 5. Document Adapter Behavior

Always document what your adapter does:

```python
class MyCustomAdapter:
    """
    Adapter for traversing custom data structure.
    
    This adapter:
    - Lazy loads children only when requested
    - Caches results for 5 minutes
    - Filters out system files (starting with .)
    - Rate limits to 100 requests per second
    
    Usage:
        adapter = MyCustomAdapter(data_source)
        async for node in traverse_tree(root, adapter):
            process(node)
    
    Note:
        Requires asyncio event loop.
        Not thread-safe.
    """
    pass
```

---

## Summary

The adapter pattern with composition gives DazzleTreeLib incredible flexibility:

1. **Write once, traverse anything**: Same traversal code works with any tree structure
2. **Mix and match features**: Combine adapters like LEGO blocks
3. **Easy to extend**: Add new tree sources without changing existing code
4. **Testable**: Mock adapters make testing simple
5. **Performant**: Add caching, rate limiting, etc. transparently

By understanding adapters and composition, you can:
- Traverse any tree-like structure with DazzleTreeLib
- Add custom functionality without modifying the library
- Build complex behaviors from simple components
- Keep your code clean, focused, and maintainable

The key is to think of adapters as translators between the generic tree traversal algorithm and your specific data source, with wrapper adapters adding cross-cutting concerns like caching, filtering, and logging.