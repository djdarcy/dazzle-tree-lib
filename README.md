# DazzleTreeLib - Universal Tree Traversal Library

[![Version](https://img.shields.io/github/v/release/djdarcy/dazzle-tree-lib?sort=semver&color=blue)](https://github.com/djdarcy/dazzle-tree-lib/releases)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green)](https://github.com/djdarcy/dazzle-tree-lib/blob/main/LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)]()

DazzleTreeLib is the first Python library with a [universal adapter system](docs/universal-adapters.md) for tree traversal, providing both synchronous and asynchronous tree traversal with a universal interface. Currently optimized for high-performance filesystem operations with 4-5x caching speedup and production-grade error handling, the architecture is designed to support any tree-like data structure - from game development BSTs to JSON manipulation to hierarchical data processing.

> **⚠️ Pre-Alpha Release**: This library is in active development. APIs may change between versions. We welcome feedback and contributions!

## Why another tree library?

Have you ever needed to traverse different types of tree structures - filesystems, databases, API hierarchies, JSON documents - but ended up writing similar-but-different code for each one?

Or struggled with existing libraries that are either too limited (filesystem-only) or too complex (full graph theory) when you just need solid tree traversal with good performance?

What about when you need finer control - stopping at specific depths, filtering during traversal, caching results, or processing huge trees efficiently with async/await?

DazzleTreeLib solves these problems with a [universal adapter system](docs/design-patterns/adapter-pattern-guide.md) that works with ANY tree structure while providing powerful traversal controls.

## Features

-  **Universal Interface**: One API for filesystem, database, API, or custom trees
-  **Async Support**: Built-in parallelism, with full async/await implementation, and batching (3.3x faster than sync)
-  **Flexible Adapters**: Easy integration with any tree-like data structure
-  **Smart Traversal** - Stop at any depth, filter during traversal, control breadth
-  **Memory Efficient**: Streaming iterators for handling large trees
-  **Highly Extensible**: Custom adapters, collectors, and traversal strategies
-  **High-Performance Intelligent Caching**: 4-5x speedup with completeness-aware caching

- **Error Resilient & Production Ready** - Structured concurrency, proper error handling, streaming

## What Makes DazzleTreeLib Different?

### Quick Comparison

| Feature | DazzleTreeLib | anytree | treelib | NetworkX |
|---------|--------------|---------|---------|----------|
| [Universal adapter system](docs/universal-adapters.md) | ✅ | ❌ | ❌ | ❌ |
| [One API for any tree source](docs/design-patterns/adapter-pattern-guide.md) | ✅ | ❌ | ❌ | ❌ |
| [Composable adapters](docs/design-patterns/composition-vs-inheritance.md) | ✅ | ❌ | ❌ | ❌ |
| [Async/sync feature parity](docs/sync-async-compatibility.md) | ✅ | ❌ | ❌ | ❌ |
| [Built-in caching](docs/caching-basics.md) | ✅ | ❌ | ❌ | ❌ |

For more, see the [detailed comparison](docs/comparison.md) in [docs](/docs)

✅ **DazzleTreeLib is Perfect for:**
- Multi-source tree traversal (files + database + API)
- Complex filtering and transformation logic
- Async/await workflows with parallel processing
- Large trees requiring streaming and caching
- Custom tree structures needing standard traversal

❌ **Consider alternatives for:**
- Simple filesystem-only tasks (use `os.scandir` - 6-7x faster)
- Pure graph algorithms (use [NetworkX](https://github.com/networkx/networkx))
- In-memory-only trees (use [anytree](https://github.com/c0fec0de/anytree) or [treelib](https://github.com/caesar0301/treelib))

## Performance

### Benchmark Assessment (Sept. 2025)

| Comparison | Performance | Best Use Case |
|------------|-------------|---------------|
| **DazzleTree async vs sync** | 3.3x faster | When using DazzleTreeLib |
| **DazzleTree vs os.scandir** | 6-7x slower | DazzleTree for flexibility, os.scandir for speed |
| **Memory usage** | ~15MB base + 14MB/1K nodes | Acceptable for most applications |


## Quick Start

### Installation

```bash
# Install from PyPI (recommended)
pip install dazzletreelib

# Or install from source for development:
git clone https://github.com/djdarcy/dazzle-tree-lib.git
cd dazzle-tree-lib
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

## Real-World Examples

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

## Migrating from Sync to Async

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

## Advanced Features

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

### High-Performance Caching

DazzleTreeLib features a sophisticated **completeness-aware caching system** that provides 4-5x performance improvements with intelligent memory management.

```python
from dazzletreelib.aio.adapters import CompletenessAwareCacheAdapter

# Safe mode (default) - with memory protection
cached_adapter = CompletenessAwareCacheAdapter(
    base_adapter,
    enable_oom_protection=True,
    max_entries=10000,
    validation_ttl_seconds=5
)

# Fast mode - maximum performance (4-5x faster on repeated traversals)
fast_adapter = CompletenessAwareCacheAdapter(
    base_adapter,
    enable_oom_protection=False
)

# First traversal: populates cache
async for node in traverse_tree_async(root, adapter=cached_adapter):
    process(node)

# Second traversal: uses cache (4-5x faster!)
async for node in traverse_tree_async(root, adapter=cached_adapter):
    process(node)
```

Key features:
- **Completeness tracking**: Knows if subtree is fully or partially cached
- **Depth-based caching**: Understands traversal depth patterns
- **Safe/Fast modes**: Choose between safety and maximum performance
- **LRU eviction**: Intelligent memory management with OrderedDict
- **TTL validation**: Configurable freshness checks with mtime
- **99% memory reduction**: Recent optimization removed redundant tracking

📖 **Documentation:**
- **[Caching Basics](docs/caching-basics.md)** - Start here if new to caching concepts
- **[Advanced Caching](docs/caching.md)** - Architecture details, comparisons with other libraries

## Architecture

DazzleTreeLib uses a clean, modular architecture:

```
dazzletreelib/
├── version.py     # Centralized version management
├── sync/          # Synchronous implementation
│   ├── core/      # Core abstractions (Node, Adapter, Collector)
│   ├── adapters/  # Tree adapters
│   │   ├── filesystem.py      # FileSystem traversal
│   │   ├── filtering.py       # FilteringWrapper
│   │   └── smart_caching.py   # Caching with tracking
│   └── api.py     # High-level sync API
├── aio/           # Asynchronous implementation
│   ├── core/      # Async abstractions with batching
│   ├── adapters/  # Async adapters
│   │   ├── filesystem.py      # Async filesystem with parallel I/O
│   │   ├── filtering.py       # Async filtering
│   │   └── smart_caching.py   # Async caching adapter
│   └── api.py     # High-level async API
└── _common/       # Shared configuration and constants
```

## Testing

Run the test suite:

```bash
# Recommended: Full test suite with proper isolation
python run_tests.py

# Run specific test categories
python run_tests.py --fast       # Quick tests only
python run_tests.py --isolated   # Interaction-sensitive tests
python run_tests.py --benchmarks # Performance benchmarks

# Manual pytest (for development)
pytest -m "not slow and not benchmark"  # Fast tests only
pytest -m benchmark                      # Benchmark tests only
pytest -m "not interaction_sensitive"    # Skip isolation-required tests
pytest --cov=dazzletreelib               # With coverage report
```

## Benchmarks

Run performance benchmarks:

```bash
# Run all benchmarks
python benchmarks/accurate_performance_test.py

# Compare with native Python methods
python benchmarks/compare_file_search.py

# Run pytest benchmarks
pytest -m benchmark -v -s
```

## Contributing

Contributions are welcome! Please ensure:
- All tests pass (`python run_tests.py`)
- Code is properly typed
- Documentation is updated
- Performance isn't regressed

Note: Git hooks are configured to:
- Update version automatically on commit
- Run fast tests before push
- Block commits with private files on public branches

Like the project?

[!["Buy Me A Coffee"](https://camo.githubusercontent.com/0b448aabee402aaf7b3b256ae471e7dc66bcf174fad7d6bb52b27138b2364e47/68747470733a2f2f7777772e6275796d6561636f666665652e636f6d2f6173736574732f696d672f637573746f6d5f696d616765732f6f72616e67655f696d672e706e67)](https://www.buymeacoffee.com/djdarcy)

## Development Status

- **Stable**: Sync implementation (v0.5.0)
- **Stable**: Async implementation (v0.6.0)
- **Production Ready**: Used in production systems (v0.10.0)
- 🚧 **Coming Soon**: Additional adapters (S3, Database, API)

## Related Projects

DazzleTreeLib is used in a growing set of tools:
- **[folder-datetime-fix](https://github.com/djdarcy/folder-datetime-fix)**: Directory timestamp correction tool (uses DazzleTreeLib)
- **[preserve](https://github.com/djdarcy/preserve)**: File tracking for easy location recovery & backup (/w integrity and sync functionality)

## Acknowledgments

- Inspired by excellent tree/graph libraries:
  - [anytree](https://github.com/c0fec0de/anytree) - Python tree data structures with visualization
  - [treelib](https://github.com/caesar0301/treelib) - Efficient tree structure and operations
  - [NetworkX](https://github.com/networkx/networkx) - Extensive graph algorithms
  - [pathlib](https://docs.python.org/3/library/pathlib.html) - Modern path handling in Python stdlib
  - [graph-tool](https://git.skewed.de/count0/graph-tool) - Rust-based / Python graph analysis toolkit
- Uses [aiofiles](https://github.com/Tinche/aiofiles) for async file operations
- [GitRepoKit](https://github.com/djdarcy/git-repokit) - Automated version management system
- Community contributors - Testing, feedback, and improvements

## License

DazzleTreeLib Copyright (C) 2025 Dustin Darcy

MIT License - see [LICENSE](LICENSE) file for details.
