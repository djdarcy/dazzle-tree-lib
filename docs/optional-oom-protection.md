# Optional OOM Protection

## Overview

DazzleTreeLib's cache adapter provides optional Out-Of-Memory (OOM) protection, allowing you to choose between maximum safety and maximum performance based on your needs.

## The Trade-off

After implementing OOM prevention features, we discovered a ~21% performance regression. To address this, we made OOM protection optional through the `enable_oom_protection` parameter, allowing developers to "live dangerously" when they need to maximize performance.

## How It Works

### Method Assignment Pattern

Instead of runtime checks that slow down every operation, we use a **method assignment pattern** that makes the safety decision once at initialization:

```python
# At initialization, we assign different methods based on the mode
if enable_oom_protection:
    self._add_to_cache_impl = self._add_to_cache_safe  # Full safety checks
else:
    self._add_to_cache_impl = self._add_to_cache_fast  # Zero overhead

# Later, all calls go through the assigned method - no runtime checks!
self._add_to_cache_impl(key, data, depth, mtime)
```

This approach provides "compile-time-like" optimization in Python, similar to C++ templates or Rust generics.

### Data Structure Differences

| Aspect | Safe Mode (Default) | Fast Mode |
|--------|-------------------|-----------|
| Cache Storage | `OrderedDict` | Regular `dict` |
| Node Tracking | `OrderedDict` | Regular `dict` |
| Memory Usage | ~87KB for 1000 entries | ~4.7KB for 1000 entries |
| LRU Eviction | ✅ Supported | ❌ Not supported |
| Entry Limits | ✅ Enforced | ❌ Disabled |
| Depth Limits | ✅ Enforced | ❌ Disabled |

## Usage

### Safe Mode (Default)

For production environments where memory safety is critical:

```python
from dazzletreelib.aio.adapters import CompletenessAwareCacheAdapter

# Default behavior - full OOM protection
adapter = CompletenessAwareCacheAdapter(
    base_adapter,
    enable_oom_protection=True,  # This is the default
    max_entries=10000,           # Enforced
    max_cache_depth=50,          # Enforced
    max_path_depth=30,           # Enforced
    max_tracked_nodes=10000      # Enforced
)
```

### Fast Mode

For performance-critical scenarios where you control memory usage:

```python
# Maximum performance, no safety nets
adapter = CompletenessAwareCacheAdapter(
    base_adapter,
    enable_oom_protection=False  # Disable all safety checks
)
# All limits are ignored when protection is disabled
```

## Performance Impact

Based on our benchmarks with 1000 operations:

| Metric | Safe Mode | Fast Mode | Improvement |
|--------|-----------|-----------|-------------|
| Time per 1000 ops | 0.169s | 0.146s | 13.7% faster |
| Operations/sec | 5,905 | 6,844 | 1.16x speedup |
| Memory per entry | ~87 bytes | ~5 bytes | 94.6% less |
| Cache hit overhead | 0.003s | 0.003s | 4.5% faster |

## When to Use Each Mode

### Use Safe Mode When:
- Running in production environments
- Processing untrusted or unbounded data
- Memory usage must be predictable
- System stability is more important than speed
- You need LRU eviction for long-running processes

### Use Fast Mode When:
- Performance is critical
- You control the data size
- Memory usage is already bounded elsewhere
- Running in development/testing environments
- Processing known, finite datasets
- Short-lived processes that won't accumulate memory

## Technical Implementation

### Zero-Overhead Abstraction

The fast mode achieves true zero-overhead by:

1. **No Runtime Type Checks**: We use boolean flags instead of `isinstance()`
2. **Method Assignment**: Methods are assigned once at initialization
3. **No Conditional Logic**: Fast path has no if-statements
4. **Simpler Data Structures**: Regular dict instead of OrderedDict

### The isinstance() Problem

Our initial implementation had a critical bug where we used `isinstance()` checks:

```python
# BAD - This was 2.6x SLOWER than safe mode!
if isinstance(self.cache, OrderedDict):
    self.cache.move_to_end(cache_key)

# GOOD - Simple boolean check
if self.enable_oom_protection:
    self.cache.move_to_end(cache_key)
```

Even simple type checks in hot paths can cause massive performance degradation.

## Migration Guide

### From Existing Code

The change is backward compatible. Existing code continues to work with full safety:

```python
# Old code - still works, uses safe mode
adapter = CompletenessAwareCacheAdapter(base_adapter)

# Explicit safe mode
adapter = CompletenessAwareCacheAdapter(
    base_adapter,
    enable_oom_protection=True
)

# Opt into fast mode
adapter = CompletenessAwareCacheAdapter(
    base_adapter,
    enable_oom_protection=False
)
```

### Testing Both Modes

We recommend testing your application with both modes:

```python
import pytest
from dazzletreelib.aio.adapters import CompletenessAwareCacheAdapter

@pytest.mark.parametrize("enable_oom_protection", [True, False])
async def test_my_feature(enable_oom_protection):
    adapter = CompletenessAwareCacheAdapter(
        base_adapter,
        enable_oom_protection=enable_oom_protection
    )
    # Your test code here
```

## Future Improvements

We're considering additional enhancements:

1. **Balanced Mode**: A middle ground with some safety but better performance
2. **Performance Tracking**: Automatic performance metrics to files
3. **Strategy Pattern**: Pluggable cache backends (Issue #28)
4. **Redundant Tracking Fix**: Optimize node tracking (Issue #30)

## Related Issues

- Issue #21: Original OOM implementation
- Issue #25: Memory limit implementation  
- Issue #28: Strategy pattern discussion
- Issue #29: This optional OOM protection feature
- Issue #30: Redundant node tracking optimization

## Benchmarking

To measure performance in your specific use case:

```python
import time
import asyncio
from pathlib import Path

async def benchmark_modes():
    operations = 1000
    
    # Test safe mode
    safe_adapter = CompletenessAwareCacheAdapter(
        base_adapter,
        enable_oom_protection=True
    )
    
    start = time.perf_counter()
    for i in range(operations):
        async for child in safe_adapter.get_children(node):
            pass
    safe_time = time.perf_counter() - start
    
    # Test fast mode
    fast_adapter = CompletenessAwareCacheAdapter(
        base_adapter,
        enable_oom_protection=False
    )
    
    start = time.perf_counter()
    for i in range(operations):
        async for child in fast_adapter.get_children(node):
            pass
    fast_time = time.perf_counter() - start
    
    print(f"Safe mode: {safe_time:.3f}s")
    print(f"Fast mode: {fast_time:.3f}s")
    print(f"Improvement: {(safe_time - fast_time) / safe_time * 100:.1f}%")
```

## Conclusion

The optional OOM protection feature gives you control over the safety vs. performance trade-off. Use safe mode by default, and only switch to fast mode when you've measured the performance benefit and understand the risks.

Remember: **premature optimization is the root of all evil**. Profile first, optimize second, and always measure the actual impact in your specific use case.