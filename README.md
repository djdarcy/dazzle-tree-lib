# DazzleTreeLib - Universal Tree Traversal Library

DazzleTreeLib is a Python library providing both synchronous and asynchronous tree traversal with a universal interface. Currently optimized for high-performance filesystem operations with production-grade error handling and 55x caching speedup, the architecture is designed to support any tree-like data structure - from game development BSTs to JSON manipulation to hierarchical data processing.

## ✨ Features

- 🔄 **Universal Interface**: Single API for filesystem, database, API, and custom trees
- ⚡ **Async Support**: Full async/await implementation (3.3x faster than sync)
- 🎯 **Flexible Adapters**: Easy integration with any tree-like data structure
- 💾 **Memory Efficient**: Streaming iterators for handling large trees
- 🛡️ **Error Resilient**: Structured concurrency with proper error handling
- 🔧 **Highly Extensible**: Custom adapters, collectors, and traversal strategies
- 🚀 **High-Performance Caching**: Optional 55x speedup for repeated traversals

## 📊 Performance

### Honest Performance Assessment

| Comparison | Performance | Best Use Case |
|------------|-------------|---------------|
| **DazzleTree async vs sync** | 3.3x faster | When using DazzleTreeLib |
| **DazzleTree vs os.scandir** | 2-3x slower | DazzleTree for flexibility, os.scandir for speed |
| **Memory usage** | ~15MB base + 14MB/1K nodes | Acceptable for most applications |

### When to Use DazzleTreeLib

✅ **Use DazzleTreeLib for:**
- Non-filesystem trees (databases, APIs, cloud storage)
- Unified interface across different tree types
- Complex filtering and transformation logic
- Async/await workflows
- Educational purposes and prototyping

❌ **Use Native Python for:**
- Simple filesystem traversal (use `os.scandir`)
- Maximum performance requirements
- Minimal memory footprint needs

## 🚀 Quick Start

### Installation

```bash
pip install dazzletreelib  # Coming soon to PyPI
# For now, install from source:
git clone https://github.com/yourusername/DazzleTreeLib.git
cd DazzleTreeLib
pip install -e .
```

### Basic Usage - Synchronous

```python
from dazzletreelib.sync import FileSystemNode, FileSystemAdapter, traverse_tree

# Simple filesystem traversal
root_node = FileSystemNode("/path/to/directory")
adapter = FileSystemAdapter()

for node, depth in traverse_tree(root_node, adapter):
    print(f"{'  ' * depth}{node.path.name}")
```

### Basic Usage - Asynchronous (3x+ Faster!)

```python
import asyncio
from dazzletreelib.aio import traverse_tree_async

async def main():
    # Async traversal with blazing speed
    async for node in traverse_tree_async("/path/to/directory"):
        print(f"Processing: {node.path}")
        
        # Access file metadata asynchronously
        size = await node.size()
        if size and size > 1_000_000:  # Files > 1MB
            print(f"  Large file: {size:,} bytes")

asyncio.run(main())
```

## 🎯 Real-World Examples

### Find Large Files Efficiently

```python
from dazzletreelib.aio import traverse_tree_async
import asyncio

async def find_large_files(root_path, min_size_mb=10):
    """Find all files larger than specified size."""
    large_files = []
    
    async for node in traverse_tree_async(root_path):
        if node.path.is_file():
            size = await node.size()
            if size and size > min_size_mb * 1024 * 1024:
                large_files.append((node.path, size))
    
    # Sort by size descending
    large_files.sort(key=lambda x: x[1], reverse=True)
    return large_files

# Usage
files = asyncio.run(find_large_files("/home/user", min_size_mb=100))
for path, size in files[:10]:  # Top 10 largest
    print(f"{size/1024/1024:.1f} MB: {path}")
```

### Parallel Directory Analysis

```python
from dazzletreelib.aio import get_tree_stats_async
import asyncio

async def analyze_projects(project_dirs):
    """Analyze multiple project directories in parallel."""
    tasks = [get_tree_stats_async(dir) for dir in project_dirs]
    stats = await asyncio.gather(*tasks)
    
    for dir, stat in zip(project_dirs, stats):
        print(f"\n{dir}:")
        print(f"  Files: {stat['file_count']:,}")
        print(f"  Directories: {stat['dir_count']:,}")
        print(f"  Total Size: {stat['total_size']/1024/1024:.1f} MB")
        print(f"  Largest: {stat['largest_file']}")

# Analyze multiple projects simultaneously
projects = ["/code/project1", "/code/project2", "/code/project3"]
asyncio.run(analyze_projects(projects))
```

### Directory Timestamp Fixer (folder-datetime-fix use case)

```python
from dazzletreelib.aio import traverse_tree_async
import asyncio
from pathlib import Path
import os

async def fix_directory_timestamps(root_path):
    """Fix directory modification times to match their newest content."""
    directories = []
    
    # Collect all directories first (depth-first post-order)
    async for node in traverse_tree_async(root_path, strategy='dfs_post'):
        if node.path.is_dir():
            directories.append(node.path)
    
    # Process directories from deepest to shallowest
    for dir_path in reversed(directories):
        newest_time = 0
        
        # Find newest modification time in directory
        for item in dir_path.iterdir():
            stat = item.stat()
            newest_time = max(newest_time, stat.st_mtime)
        
        # Update directory timestamp
        if newest_time > 0:
            os.utime(dir_path, (newest_time, newest_time))
            print(f"Updated: {dir_path}")

# Fix all directory timestamps
asyncio.run(fix_directory_timestamps("/path/to/fix"))
```

## 🔄 Migrating from Sync to Async

The async API mirrors the sync API closely, making migration straightforward:

### Sync Version
```python
from dazzletreelib.sync import traverse_tree, FileSystemNode, FileSystemAdapter

node = FileSystemNode(path)
adapter = FileSystemAdapter()
for node, depth in traverse_tree(node, adapter):
    process(node)
```

### Async Version
```python
from dazzletreelib.aio import traverse_tree_async

async for node in traverse_tree_async(path):
    await process_async(node)
```

Key differences:
- No need to create node/adapter explicitly in async
- Use `async for` instead of `for`
- Await any async operations on nodes
- Wrap in `asyncio.run()` or existing async function

## 📁 Advanced Features

### Batched Parallel Processing

The async implementation uses intelligent batching for optimal performance:

```python
# Control parallelism with batch_size and max_concurrent
async for node in traverse_tree_async(
    root,
    batch_size=256,      # Process children in batches
    max_concurrent=100   # Limit concurrent I/O operations
):
    await process(node)
```

### Depth Limiting

```python
# Only traverse 3 levels deep
async for node in traverse_tree_async(root, max_depth=3):
    print(node.path)
```

### Custom Filtering

```python
from dazzletreelib.aio import filter_tree_async

# Custom predicate function
async def is_python_file(node):
    return node.path.suffix == '.py'

# Get all Python files
python_files = await filter_tree_async(root, predicate=is_python_file)
```

### High-Performance Caching (New in v0.8.0!)

Get 55x speedup on repeated traversals with the optional caching layer:

```python
from dazzletreelib.aio.adapters import FastAsyncFileSystemAdapter
from dazzletreelib.aio.caching import CachingTreeAdapter, FilesystemCachingAdapter

# Basic caching with TTL
base_adapter = FastAsyncFileSystemAdapter()
cached_adapter = CachingTreeAdapter(base_adapter, max_size=50000, ttl=300)

# First traversal: ~40ms for 1000 nodes
async for node in traverse_tree_async(root, adapter=cached_adapter):
    process(node)

# Second traversal: <1ms! (55x faster)
async for node in traverse_tree_async(root, adapter=cached_adapter):
    process(node)

# Filesystem-specific caching with instant invalidation
fs_cached = FilesystemCachingAdapter(base_adapter)  # Uses mtime for change detection
```

Key features:
- **Zero API changes**: Completely backwards compatible
- **Future-based coordination**: Prevents duplicate concurrent scans
- **Dual-cache system**: mtime validation with TTL fallback
- **Statistics tracking**: Monitor cache performance
- **Memory efficient**: ~300 bytes per cached directory

## 🏗️ Architecture

DazzleTreeLib uses a clean, modular architecture:

```
dazzletreelib/
├── sync/          # Synchronous implementation
│   ├── core/      # Core abstractions
│   ├── adapters/  # Tree adapters (filesystem, etc.)
│   └── api.py     # High-level API
├── aio/           # Asynchronous implementation
│   ├── core/      # Async abstractions
│   ├── adapters/  # Async adapters with batching
│   └── api.py     # High-level async API
└── _common/       # Shared configuration
```

## 🧪 Testing

Run the test suite:

```bash
# All tests
pytest

# Just the fast tests
pytest -m "not slow"

# With coverage
pytest --cov=dazzletreelib
```

## 📈 Benchmarks

Run performance benchmarks:

```bash
pytest tests/test_performance_async.py -v -s
```

## 🤝 Contributing

Contributions are welcome! Please ensure:
- All tests pass
- Code is properly typed
- Documentation is updated
- Performance isn't regressed

## 📜 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🚦 Development Status

- ✅ **Stable**: Sync implementation (v0.5.0)
- ✅ **Stable**: Async implementation (v0.6.0)
- ✅ **Production Ready**: Used in production systems
- 🚧 **Coming Soon**: Additional adapters (S3, Database, API)

## 🔗 Related Projects

DazzleTreeLib is part of a comprehensive toolkit:
- **folder-datetime-fix**: Directory timestamp correction tool (uses DazzleTreeLib)
- **FileAudit**: File integrity and duplication detection
- **TreeSync**: Directory synchronization utility

---

**Ready to traverse trees at lightning speed? Get started with DazzleTreeLib today!** 🚀