# Getting Started with DazzleTreeLib

This guide will help you install DazzleTreeLib and start using it for tree traversal operations.

## Table of Contents

1. [Installation](#installation)
2. [Quick Start](#quick-start)
3. [Basic Concepts](#basic-concepts)
4. [Choosing Sync vs Async](#choosing-sync-vs-async)
5. [Common Use Cases](#common-use-cases)
6. [Migrating from Sync to Async](#migrating-from-sync-to-async)
7. [Next Steps](#next-steps)

## Installation

### From PyPI (Coming Soon)

```bash
pip install dazzletreelib
```

### From Source (Current Method)

```bash
# Clone the repository
git clone https://github.com/yourusername/DazzleTreeLib.git
cd DazzleTreeLib

# Install in development mode
pip install -e .

# Or install with development dependencies
pip install -e ".[dev]"
```

### Requirements

- Python 3.8 or higher
- aiofiles (for async file operations)
- No other external dependencies!

## Quick Start

### Your First Tree Traversal (Synchronous)

```python
from pathlib import Path
from dazzletreelib.sync import FileSystemNode, FileSystemAdapter, traverse_tree

# Create a root node for your directory
root = FileSystemNode("/path/to/directory")

# Create an adapter for filesystem traversal
adapter = FileSystemAdapter()

# Traverse the tree
for node, depth in traverse_tree(root, adapter, max_depth=3):
    indent = "  " * depth
    if node.is_file():
        print(f"{indent}📄 {node.path.name}")
    else:
        print(f"{indent}📁 {node.path.name}/")
```

### Your First Async Traversal (3x Faster!)

```python
import asyncio
from dazzletreelib.aio import traverse_tree_async

async def main():
    # Even simpler - no adapter needed!
    async for node in traverse_tree_async("/path/to/directory", max_depth=3):
        if node.path.is_file():
            print(f"📄 {node.path.name}")
        else:
            print(f"📁 {node.path.name}/")

# Run the async function
asyncio.run(main())
```

## Basic Concepts

### 1. Nodes

Nodes represent items in your tree structure:

```python
# Synchronous node
node = FileSystemNode("/path/to/file.txt")
print(node.identifier())  # Unique ID
print(node.is_leaf())     # True for files
print(node.size())        # File size in bytes

# Asynchronous node
async_node = AsyncFileSystemNode("/path/to/file.txt")
print(await async_node.identifier())  # Must await
print(await async_node.is_leaf())     # Must await
print(await async_node.size())        # Must await
```

### 2. Adapters

Adapters define how to navigate your tree:

```python
# Synchronous adapter
adapter = FileSystemAdapter(follow_symlinks=False)

# Async adapter (usually created automatically)
async_adapter = AsyncFileSystemAdapter(
    batch_size=256,      # Process children in batches
    max_concurrent=100   # Limit concurrent operations
)
```

### 3. Traversal Strategies

Choose how to traverse your tree:

```python
# Breadth-first (level by level)
traverse_tree(root, adapter, strategy='bfs')

# Depth-first pre-order (parent before children)
traverse_tree(root, adapter, strategy='dfs_pre')

# Depth-first post-order (children before parent)
traverse_tree(root, adapter, strategy='dfs_post')
```

## Choosing Sync vs Async

### When to Use Synchronous

Use the synchronous API when:
- Working with small trees (<1000 nodes)
- Integrating with synchronous code
- Debugging is important
- Simplicity is preferred

```python
# Synchronous - Simple and predictable
from dazzletreelib.sync import traverse_tree

def count_files(directory):
    root = FileSystemNode(directory)
    adapter = FileSystemAdapter()
    
    file_count = 0
    for node, _ in traverse_tree(root, adapter):
        if node.is_file():
            file_count += 1
    
    return file_count
```

### When to Use Asynchronous

Use the asynchronous API when:
- Working with large trees (>1000 nodes)
- I/O operations dominate
- Performance is critical
- Building async applications

```python
# Asynchronous - Fast and scalable
from dazzletreelib.aio import traverse_tree_async

async def count_files_async(directory):
    file_count = 0
    
    async for node in traverse_tree_async(directory):
        if node.path.is_file():
            file_count += 1
    
    return file_count

# 3x+ faster for large trees!
```

## Common Use Cases

### 1. Find Large Files

```python
import asyncio
from dazzletreelib.aio import traverse_tree_async

async def find_large_files(directory, min_size_mb=10):
    large_files = []
    
    async for node in traverse_tree_async(directory):
        if node.path.is_file():
            size = await node.size()
            if size and size > min_size_mb * 1024 * 1024:
                large_files.append((node.path, size))
    
    return sorted(large_files, key=lambda x: x[1], reverse=True)

# Usage
files = asyncio.run(find_large_files("/home/user", min_size_mb=100))
for path, size in files[:10]:
    print(f"{size/1024/1024:.1f} MB: {path}")
```

### 2. Directory Statistics

```python
from dazzletreelib.sync import traverse_tree, FileSystemNode, FileSystemAdapter

def get_directory_stats(directory):
    root = FileSystemNode(directory)
    adapter = FileSystemAdapter()
    
    stats = {
        'total_files': 0,
        'total_dirs': 0,
        'total_size': 0,
        'max_depth': 0,
        'file_types': {}
    }
    
    for node, depth in traverse_tree(root, adapter):
        if node.is_file():
            stats['total_files'] += 1
            stats['total_size'] += node.size() or 0
            
            # Track file types
            ext = node.path.suffix.lower()
            stats['file_types'][ext] = stats['file_types'].get(ext, 0) + 1
        else:
            stats['total_dirs'] += 1
        
        stats['max_depth'] = max(stats['max_depth'], depth)
    
    return stats
```

### 3. Search for Files

```python
import asyncio
from pathlib import Path
from dazzletreelib.aio import traverse_tree_async

async def search_files(directory, pattern="*.py", content_search=None):
    matching_files = []
    
    async for node in traverse_tree_async(directory):
        if node.path.is_file() and node.path.match(pattern):
            if content_search:
                try:
                    content = node.path.read_text()
                    if content_search in content:
                        matching_files.append(node.path)
                except:
                    pass  # Skip files that can't be read
            else:
                matching_files.append(node.path)
    
    return matching_files

# Find all Python files containing "async def"
files = asyncio.run(search_files(
    "/project",
    pattern="*.py",
    content_search="async def"
))
```

## Migrating from Sync to Async

### Step 1: Identify the Sync Code

```python
# Original synchronous code
from dazzletreelib.sync import traverse_tree, FileSystemNode, FileSystemAdapter

def process_tree_sync(directory):
    root = FileSystemNode(directory)
    adapter = FileSystemAdapter()
    
    results = []
    for node, depth in traverse_tree(root, adapter):
        if node.is_file():
            # Synchronous I/O
            size = node.size()
            results.append({
                'path': node.path,
                'size': size,
                'depth': depth
            })
    
    return results
```

### Step 2: Convert to Async

```python
# Converted to asynchronous
from dazzletreelib.aio import traverse_tree_async
import asyncio

async def process_tree_async(directory):
    results = []
    
    # Note: async version doesn't return depth directly
    async for node in traverse_tree_async(directory):
        if node.path.is_file():
            # Asynchronous I/O
            size = await node.size()
            results.append({
                'path': node.path,
                'size': size
            })
    
    return results
```

### Step 3: Update the Calling Code

```python
# Synchronous caller
results = process_tree_sync("/data")

# Asynchronous caller
results = asyncio.run(process_tree_async("/data"))
```

### Key Differences to Remember

| Aspect | Synchronous | Asynchronous |
|--------|------------|--------------|
| **Import** | `from dazzletreelib.sync import ...` | `from dazzletreelib.aio import ...` |
| **Function** | `traverse_tree()` | `traverse_tree_async()` |
| **Adapter** | Required | Optional (auto-created) |
| **Returns** | `(node, depth)` tuples | Just nodes |
| **Methods** | Direct calls | Must `await` |
| **Loop** | `for node, depth in ...` | `async for node in ...` |
| **Speed** | Baseline | 3x+ faster |

## Performance Tips

### Synchronous Performance

```python
# Use generators for memory efficiency
def process_files(directory):
    root = FileSystemNode(directory)
    adapter = FileSystemAdapter()
    
    # Generator - memory efficient
    for node, _ in traverse_tree(root, adapter):
        if should_process(node):
            yield process(node)  # Yield instead of accumulating
```

### Asynchronous Performance

```python
# Tune batch size and concurrency for your use case
async def optimized_traversal(directory):
    # For small trees
    if is_small_tree(directory):
        async for node in traverse_tree_async(
            directory,
            batch_size=32,       # Smaller batches
            max_concurrent=10    # Lower concurrency
        ):
            await process(node)
    
    # For large trees
    else:
        async for node in traverse_tree_async(
            directory,
            batch_size=512,      # Larger batches
            max_concurrent=200   # Higher concurrency
        ):
            await process(node)
```

## Error Handling

Both APIs handle errors gracefully:

```python
# Synchronous error handling
try:
    for node, depth in traverse_tree(root, adapter):
        try:
            process(node)
        except Exception as e:
            print(f"Error processing {node.path}: {e}")
            continue  # Continue with next node
except Exception as e:
    print(f"Fatal traversal error: {e}")

# Asynchronous error handling
try:
    async for node in traverse_tree_async(directory):
        try:
            await process(node)
        except Exception as e:
            print(f"Error processing {node.path}: {e}")
            continue
except Exception as e:
    print(f"Fatal traversal error: {e}")
```

## Next Steps

Now that you understand the basics:

1. **Learn the Architecture**: Read the [Architecture Overview](architecture.md) to understand the design
2. **Explore the API**: Check the [API Reference](api-reference.md) for detailed documentation
3. **Create Custom Adapters**: Follow the [Adapter Development Guide](adapter-development.md) to support new tree types
4. **Optimize Performance**: Read the [Performance Guide](performance.md) for tuning tips
5. **Study Examples**: Browse the [Examples](../examples/) directory for real-world usage

## Getting Help

- **Documentation**: You're reading it!
- **Examples**: Check the [examples](../examples/) directory
- **Issues**: Report bugs on [GitHub Issues](https://github.com/yourusername/DazzleTreeLib/issues)
- **Discussions**: Ask questions in [GitHub Discussions](https://github.com/yourusername/DazzleTreeLib/discussions)

## FAQ

**Q: Why do I need an adapter for sync but not async?**
A: The async API automatically creates a filesystem adapter when given a path. The sync API requires explicit adapter creation for flexibility.

**Q: How much faster is async really?**
A: Typically 3-4x faster for I/O-heavy operations on large trees. See the [Performance Guide](performance.md) for benchmarks.

**Q: Can I use both sync and async in the same application?**
A: Yes! They're completely separate and can be used together. See the [Compatibility Guide](sync-async-compatibility.md).

**Q: What Python versions are supported?**
A: Python 3.8 and higher. Async features require Python's asyncio support.

**Q: Is it production-ready?**
A: Yes! Version 0.6.0+ has comprehensive tests and is used in production systems.