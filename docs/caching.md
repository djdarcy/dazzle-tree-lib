# DazzleTreeLib Caching Architecture

> **New to caching?** Start with our [Caching Basics Guide](caching-basics.md) for a beginner-friendly introduction to how caching works with tree traversal.

## Overview & Philosophy

DazzleTreeLib implements a sophisticated **completeness-aware caching system** that goes beyond simple key-value storage. Unlike traditional tree libraries that treat caching as an afterthought, our caching is designed specifically for tree traversal patterns.

### Core Philosophy

**"Caching should understand tree traversal patterns, not just store arbitrary data"**

Our cache doesn't just remember what you've accessed - it understands:
- Whether a subtree has been **completely** scanned or only **partially** explored
- How **deep** into the tree structure each scan went
- The **recency** of access for intelligent eviction
- The **validity** of cached data based on filesystem changes

## Architecture

### Two-Layer Design

Similar to industry-standard libraries like `fsspec` and `PyFilesystem2`, DazzleTreeLib separates the tree structure from cache metadata:

```
┌─────────────────────────────────────┐
│         User's Tree Structure       │  ← What you explicitly build
├─────────────────────────────────────┤
│      Cache Metadata Layer           │  ← What we manage for performance
│  • Directory listings               │
│  • Completeness tracking            │
│  • Access patterns (LRU)            │
│  • Validation timestamps            │
└─────────────────────────────────────┘
```

### Unique Concepts

#### 1. Completeness Tracking

Our cache tracks whether a directory scan was **complete** or **partial**:

```python
# Complete scan - we know ALL children exist in cache
entry.depth = -1  # COMPLETE_DEPTH constant

# Partial scan - we only scanned to depth 3
entry.depth = 3   # More levels may exist below
```

This enables intelligent cache reuse:
- A complete scan can satisfy ANY depth request
- A partial scan can only satisfy requests up to its depth

#### 2. Depth-Based Caching

Each cache entry knows how deep it was scanned:

```python
# Scanning /projects to depth 2
cache_key = "/projects:depth=2"
# Result: Immediate children and grandchildren cached

# Later request for depth 1 can reuse this cache
# Request for depth 3 triggers new scan
```

#### 3. Safe vs. Fast Mode

DazzleTreeLib offers two distinct operation modes:

| Mode | Data Structure | Eviction | Overhead | Use Case |
|------|---------------|----------|----------|----------|
| **Safe Mode** | `OrderedDict` | LRU with limits | ~15% | Default, production |
| **Fast Mode** | `dict` | No eviction | Minimal | Performance critical |

### LRU Eviction Implementation

In **Safe Mode**, we implement true LRU (Least Recently Used) eviction using Python's `OrderedDict`:

```python
# Cache hit moves entry to end (most recent)
if cache_key in self.cache:
    entry = self.cache[cache_key]
    if self.enable_oom_protection:
        self.cache.move_to_end(cache_key)  # O(1) operation
    return entry
```

When cache is full:
1. Remove least recently used entry (first in OrderedDict)
2. Track eviction for statistics
3. Ensure memory limits are respected

## Usage Guide

### Basic Configuration

```python
from dazzletreelib.aio.adapters import CompletenessAwareCacheAdapter

# Safe mode (default) - with OOM protection
safe_adapter = CompletenessAwareCacheAdapter(
    base_adapter,
    enable_oom_protection=True,
    max_entries=10000,
    max_memory_mb=100,
    validation_ttl_seconds=5
)

# Fast mode - maximum performance
fast_adapter = CompletenessAwareCacheAdapter(
    base_adapter,
    enable_oom_protection=False  # No limits, no eviction
)
```

### Configuration Options

| Parameter | Default | Description |
|-----------|---------|-------------|
| `enable_oom_protection` | `True` | Enable memory limits and LRU eviction |
| `max_entries` | `10000` | Maximum cache entries (safe mode only) |
| `max_memory_mb` | `100` | Memory limit in MB (safe mode only) |
| `max_tracked_nodes` | `10000` | Maximum completeness tracking entries |
| `validation_ttl_seconds` | `5` | Skip validation for entries younger than TTL |
| `max_cache_depth` | `50` | Maximum depth to cache |
| `max_path_depth` | `30` | Maximum filesystem path depth |

### Performance Characteristics

Based on our benchmarks and the resolution of Issues #29 and #30:

| Metric | Safe Mode | Fast Mode | Improvement |
|--------|-----------|-----------|-------------|
| Cache Misses | Baseline | 85-90% faster | 🚀 |
| Cache Hits | Baseline | 10-20% faster | ✓ |
| Memory Usage | Controlled | Unlimited | ⚠️ |
| Node Tracking | 10,000 parents | 10,000 parents | Same |

### Code Examples

#### Example 1: Traversing Large Directory Trees

```python
import asyncio
from dazzletreelib.aio import FileSystemNode, traverse_tree_async
from dazzletreelib.aio.adapters import CompletenessAwareCacheAdapter

async def scan_projects():
    # Wrap filesystem adapter with caching
    cached_adapter = CompletenessAwareCacheAdapter(
        base_adapter,
        max_memory_mb=200,  # Increase for large trees
        validation_ttl_seconds=60  # Longer TTL for stable directories
    )

    # First traversal - populates cache
    async for node in traverse_tree_async("/home/user/projects",
                                         adapter=cached_adapter,
                                         max_depth=3):
        print(f"Found: {node.path}")

    # Second traversal - uses cache (much faster!)
    async for node in traverse_tree_async("/home/user/projects",
                                         adapter=cached_adapter,
                                         max_depth=2):  # Less depth - fully cached
        process(node)
```

#### Example 2: Performance-Critical Scanning

```python
# Use fast mode for maximum performance
fast_adapter = CompletenessAwareCacheAdapter(
    base_adapter,
    enable_oom_protection=False  # Disable all safety checks
)

# Scan millions of files quickly
async for node in traverse_tree_async("/massive/dataset",
                                     adapter=fast_adapter):
    # Process at maximum speed
    # Note: Monitor memory usage externally!
    await process_file(node)
```

#### Example 3: Monitoring Cache Performance

```python
adapter = CompletenessAwareCacheAdapter(base_adapter)

# Perform operations...
await scan_directory(adapter)

# Check cache statistics
print(f"Cache hits: {adapter.hits}")
print(f"Cache misses: {adapter.misses}")
print(f"Hit rate: {adapter.hits / (adapter.hits + adapter.misses) * 100:.1f}%")
print(f"Evictions: {adapter.evictions}")
print(f"Current entries: {len(adapter.cache)}")
```

## Comparison with Other Libraries

### Feature Comparison Table

| Feature | DazzleTreeLib | fsspec | PyFilesystem2 | anytree |
|---------|--------------|--------|---------------|---------|
| **Adapter Pattern** | ✅ | ✅ | ✅ | ❌ |
| **LRU Eviction** | ✅ | ✅ | Partial | ❌ |
| **TTL Validation** | ✅ | ✅ | ✅ | ❌ |
| **Completeness Tracking** | ✅ | ❌ | ❌ | ❌ |
| **Depth-Based Caching** | ✅ | ❌ | ❌ | ❌ |
| **Safe/Fast Modes** | ✅ | ❌ | ❌ | ❌ |
| **Memory Limits** | ✅ | ✅ | Partial | ❌ |
| **Cache Bypass** | ✅ | ✅ | ✅ | N/A |
| **Manual Invalidation** | ⚠️ | ✅ | ✅ | N/A |
| **Cache Statistics** | ✅ | Partial | Partial | ❌ |

### Key Differences

#### vs. fsspec
- **fsspec** focuses on filesystem abstraction with generic caching
- **DazzleTreeLib** specializes in tree traversal with completeness awareness
- fsspec has `invalidate_cache()`, we use TTL-based validation
- We track traversal depth, fsspec doesn't

#### vs. PyFilesystem2
- **PyFilesystem2** uses wrapper pattern (CacheFS, WrapCachedDir)
- **DazzleTreeLib** integrates caching into adapters
- PyFilesystem2 focuses on filesystem operations
- We focus on tree traversal patterns

#### vs. anytree
- **anytree** is pure in-memory tree structure
- **DazzleTreeLib** bridges filesystem to tree with caching
- anytree has no adapter concept
- We provide async traversal with caching

## Current Limitations

### Available Features

1. **Cache Bypass per Call** ✅ (v0.9.4+)
   
   ```python
   # Force fresh read, bypassing cache
   async for child in adapter.get_children(node, use_cache=False):
       # Always fetches from source
       process(child)
   ```

### Missing Features (Planned for Phase 2)

1. **Manual Cache Refresh**
   ```python
   # Not yet available (planned):
   adapter.refresh("/path/to/dir", deep=True)
   ```

2. **Explicit Invalidation**
   ```python
   # Not yet available (planned):
   adapter.invalidate("/specific/path")
   adapter.invalidate_all()
   ```

3. **Per-Path TTL Configuration**
   ```python
   # Not yet available (planned):
   adapter.set_ttl("/volatile/dir", ttl_seconds=1)
   adapter.set_ttl("/stable/dir", ttl_seconds=3600)
   ```

### Workarounds

Until these features are added:

- **Force fresh read**: Use `use_cache=False` parameter (available now!)
- **Clear cache**: Create new adapter instance
- **Selective invalidation**: Use short TTL for volatile directories

## Performance Tuning

### Choosing the Right Mode

**Use Safe Mode when:**
- Running in production
- Memory is limited
- Processing unknown directory sizes
- Default choice for most applications

**Use Fast Mode when:**
- Benchmarking or performance testing
- Processing known, bounded directories
- Memory is plentiful
- Speed is absolutely critical

### Optimization Tips

1. **Tune TTL for your use case**:
   - Static directories: 300-3600 seconds
   - Active directories: 5-30 seconds
   - Real-time monitoring: 0-1 seconds

2. **Adjust memory limits**:
   ```python
   # For large codebases
   adapter = CompletenessAwareCacheAdapter(
       base_adapter,
       max_entries=50000,
       max_memory_mb=500
   )
   ```

3. **Monitor cache effectiveness**:
   ```python
   if adapter.hits / (adapter.hits + adapter.misses) < 0.8:
       print("Consider increasing cache size or TTL")
   ```

## API Reference

### CompletenessAwareCacheAdapter

```python
class CompletenessAwareCacheAdapter(AsyncTreeAdapter):
    """
    Caching adapter with completeness tracking and OOM protection.

    Attributes:
        hits (int): Number of cache hits
        misses (int): Number of cache misses
        bypasses (int): Number of cache bypass calls (v0.9.4+)
        evictions (int): Number of LRU evictions
        upgrades (int): Number of depth upgrades
        cache (dict/OrderedDict): The cache storage
        node_completeness (dict/OrderedDict): Completeness tracking
    """

    def __init__(self,
                 base_adapter: AsyncTreeAdapter,
                 enable_oom_protection: bool = True,
                 max_memory_mb: int = 100,
                 max_depth: int = 100,
                 max_entries: int = 10000,
                 max_tracked_nodes: int = 10000,
                 max_cache_depth: int = 50,
                 max_path_depth: int = 30,
                 validation_ttl_seconds: float = 5.0)

    async def get_children(self, node: Any, use_cache: bool = True) -> AsyncIterator[Any]:
        """
        Get children with caching, completeness tracking, and validation.

        Args:
            node: The node to get children for
            use_cache: If False, bypass cache and fetch from source (v0.9.4+)

        Yields:
            Children of the node
        """
```

## Best Practices

1. **Start with defaults** - They're tuned for common use cases
2. **Monitor memory usage** - Especially in fast mode
3. **Use appropriate TTL** - Balance freshness vs. performance
4. **Profile your workload** - Check cache hit rates
5. **Consider completeness** - Leverage deep scans when beneficial

## Future Roadmap

### Phase 2 Enhancements (Planned)
- Cache control API (refresh, invalidate)
- Per-path configuration
- Cache warming strategies
- Persistent cache support
- Multi-level cache hierarchies

### Community Feedback Welcome
We're actively seeking feedback on caching needs. Please open issues for:
- Feature requests
- Performance problems
- API suggestions
- Documentation improvements

## Conclusion

DazzleTreeLib's caching system is designed specifically for tree traversal patterns, offering unique features like completeness tracking and depth-based caching not found in generic filesystem libraries. With the addition of cache bypass functionality, combined with our validation-based approach and configurable TTL, we provide a solid foundation for most use cases. Manual invalidation and refresh APIs are planned for future releases.

The recent removal of redundant child tracking (Issue #30) has resulted in 99% memory reduction and 85-90% performance improvements in fast mode, making DazzleTreeLib one of the most efficient tree traversal libraries available for Python.