# Composition vs Inheritance in DazzleTreeLib

## Table of Contents
1. [Introduction for Beginners](#introduction-for-beginners)
2. [The Old Way: Inheritance](#the-old-way-inheritance)
3. [The New Way: Composition](#the-new-way-composition)
4. [Real Examples from DazzleTreeLib](#real-examples-from-dazzletreelib)
5. [When to Use Each Pattern](#when-to-use-each-pattern)
6. [Benefits in Practice](#benefits-in-practice)
7. [Common Pitfalls and How to Avoid Them](#common-pitfalls-and-how-to-avoid-them)

---

## Introduction for Beginners

If you're new to design patterns, think of building software like building with LEGO blocks:

- **Inheritance** is like having specialized LEGO sets where each new set is based on a previous one, adding more features
- **Composition** is like having basic LEGO blocks that you can combine in different ways to build whatever you need

### A Simple Analogy

Imagine you're building different types of vehicles:

**Inheritance Approach** (IS-A relationship):
```
Vehicle
├── Car (IS-A Vehicle)
│   └── SportsCar (IS-A Car)
│       └── RacingCar (IS-A SportsCar)
└── Truck (IS-A Vehicle)
    └── DeliveryTruck (IS-A Truck)
```

**Composition Approach** (HAS-A relationship):
```
Vehicle HAS-A:
  - Engine
  - Wheels
  - SteeringSystem
  
SportsCar = Vehicle with:
  - TurboEngine
  - SportWheels  
  - PrecisionSteering
```

---

## The Old Way: Inheritance

### How We Used to Do It (Before v0.9.0)

```python
# OLD APPROACH - Using Inheritance
class AsyncFileSystemAdapter:
    """Base adapter for filesystem operations."""
    def __init__(self, use_stat_cache=False):
        self.use_stat_cache = use_stat_cache
    
    async def get_children(self, node):
        # Basic implementation using os.listdir
        return await self._get_children_basic(node)

class FastAsyncFileSystemAdapter(AsyncFileSystemAdapter):
    """Fast adapter that inherits from base adapter."""
    def __init__(self):
        super().__init__(use_stat_cache=True)  # Always uses cache
    
    async def get_children(self, node):
        # Override with faster implementation using os.scandir
        return await self._get_children_fast(node)

class AsyncFilteredFileSystemAdapter(AsyncFileSystemAdapter):
    """Filtered adapter that inherits from base adapter."""
    def __init__(self, include_patterns=None, **kwargs):
        super().__init__(**kwargs)  # Pass through parent's arguments
        self.include_patterns = include_patterns
    
    async def get_children(self, node):
        # Get children from parent, then filter
        children = await super().get_children(node)
        return self._apply_filters(children)
```

### Problems with Inheritance

1. **The Diamond Problem**:
```python
# What if we want a FAST and FILTERED adapter?
class FastFilteredAdapter(FastAsyncFileSystemAdapter, AsyncFilteredFileSystemAdapter):
    # Which get_children() method do we inherit?
    # Which __init__ gets called first?
    # This creates ambiguity and bugs!
    pass
```

2. **Tight Coupling**:
```python
# If we change AsyncFileSystemAdapter, ALL child classes might break
class AsyncFileSystemAdapter:
    def __init__(self, use_stat_cache=False, new_param=None):  # Added parameter
        # Now EVERY child class needs to handle this new parameter!
        pass
```

3. **Inflexibility**:
```python
# Want to add caching to an existing adapter at runtime? Too bad!
adapter = AsyncFilteredFileSystemAdapter()
# No way to add FastAdapter's speed benefits without creating a new class
```

---

## The New Way: Composition

### How We Do It Now (v0.9.0+)

```python
# NEW APPROACH - Using Composition
class AsyncFileSystemAdapter:
    """Single, optimized adapter implementation."""
    def __init__(self, max_concurrent=100):
        self.max_concurrent = max_concurrent
        # Always uses fast os.scandir - no switches needed
    
    async def get_children(self, node):
        # One optimized implementation
        return await self._get_children_scandir(node)

class AsyncFilteredFileSystemAdapter:
    """Filtered adapter that WRAPS another adapter (composition)."""
    def __init__(self, base_adapter=None, include_patterns=None):
        # HAS-A base adapter (composition)
        self.base_adapter = base_adapter or AsyncFileSystemAdapter()
        self.include_patterns = include_patterns
    
    async def get_children(self, node):
        # Delegate to wrapped adapter, then filter
        children = await self.base_adapter.get_children(node)
        return self._apply_filters(children)

class CachingTreeAdapter:
    """Caching wrapper that can wrap ANY adapter."""
    def __init__(self, base_adapter, cache_size=1000):
        # HAS-A base adapter (composition)
        self.base_adapter = base_adapter
        self.cache = LRUCache(cache_size)
    
    async def get_children(self, node):
        # Check cache first
        if node in self.cache:
            return self.cache[node]
        # Delegate to wrapped adapter
        children = await self.base_adapter.get_children(node)
        self.cache[node] = children
        return children
```

### The Power of Composition

Now we can combine features flexibly:

```python
# Want a filtered adapter? Simple:
filtered = AsyncFilteredFileSystemAdapter(
    include_patterns=['*.py', '*.js']
)

# Want a cached, filtered adapter? Just wrap it:
cached_filtered = CachingTreeAdapter(
    base_adapter=AsyncFilteredFileSystemAdapter(
        include_patterns=['*.py', '*.js']
    ),
    cache_size=5000
)

# Want to add caching to an existing adapter? No problem:
adapter = AsyncFileSystemAdapter()
# ... use it for a while ...
# Now add caching:
cached_adapter = CachingTreeAdapter(adapter)

# Want filtering, caching, AND rate limiting? Stack them:
rate_limiter = RateLimitingAdapter(
    base_adapter=CachingTreeAdapter(
        base_adapter=AsyncFilteredFileSystemAdapter(
            include_patterns=['*.py']
        )
    ),
    max_per_second=100
)
```

---

## Real Examples from DazzleTreeLib

### Example 1: The Filtered Adapter Refactoring

**Before (Inheritance)**:
```python
class AsyncFilteredFileSystemAdapter(AsyncFileSystemAdapter):
    """Inherited from base, causing problems."""
    def __init__(self, include_patterns=None, **kwargs):
        super().__init__(**kwargs)  # What if parent changes?
        self.include_patterns = include_patterns
    
    # Had to override EVERY method to add filtering
    async def get_children(self, node):
        children = await super().get_children(node)
        return self._filter(children)
    
    async def get_node_data(self, node):
        data = await super().get_node_data(node)
        # Oops, forgot to filter here! Bug!
        return data
```

**After (Composition)**:
```python
class AsyncFilteredFileSystemAdapter:
    """Wraps any adapter, much cleaner."""
    def __init__(self, base_adapter=None, include_patterns=None):
        self.base_adapter = base_adapter or AsyncFileSystemAdapter()
        self.include_patterns = include_patterns
        # Automatically delegate all methods we don't override
        self._setup_delegation()
    
    def _setup_delegation(self):
        """Forward all adapter methods to base adapter."""
        for attr_name in dir(self.base_adapter):
            if not attr_name.startswith('_'):
                attr = getattr(self.base_adapter, attr_name)
                if callable(attr) and not hasattr(self, attr_name):
                    setattr(self, attr_name, attr)
    
    async def get_children(self, node):
        """Only override what we need to change."""
        children = await self.base_adapter.get_children(node)
        return self._apply_filters(children)
```

### Example 2: The Caching Layer

With composition, we could add caching as a separate concern:

```python
# This adapter can cache ANY other adapter's results
class CachingTreeAdapter:
    """Universal caching wrapper."""
    def __init__(self, base_adapter, ttl=60, max_items=10000):
        self.base_adapter = base_adapter
        self.cache = TTLCache(ttl=ttl, max_items=max_items)
    
    async def get_children(self, node):
        cache_key = str(node.path)
        
        # Check cache
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # Delegate to wrapped adapter
        children = await self.base_adapter.get_children(node)
        
        # Cache the result
        self.cache[cache_key] = children
        return children
    
    # All other methods automatically delegated
    def __getattr__(self, name):
        """Delegate unknown attributes to base adapter."""
        return getattr(self.base_adapter, name)
```

### Example 3: Testing Benefits

Composition makes testing much easier:

```python
# Create a mock adapter for testing
class MockAdapter:
    """Fake adapter for testing."""
    def __init__(self, children_map):
        self.children_map = children_map
        self.call_count = 0
    
    async def get_children(self, node):
        self.call_count += 1
        return self.children_map.get(node.path, [])

# Test the caching wrapper independently
async def test_caching():
    mock = MockAdapter({
        '/root': ['file1.txt', 'file2.txt'],
        '/root/dir': ['file3.txt']
    })
    
    cached = CachingTreeAdapter(mock)
    
    # First call hits the mock
    children1 = await cached.get_children(Node('/root'))
    assert mock.call_count == 1
    
    # Second call hits the cache
    children2 = await cached.get_children(Node('/root'))
    assert mock.call_count == 1  # Still 1, cache was used!
    assert children1 == children2
```

---

## When to Use Each Pattern

### Use Inheritance When:

1. **Clear IS-A Relationship**: A SportsCar IS-A Car
2. **Shared Implementation**: All subclasses share 80%+ of code
3. **Template Method Pattern**: Base class defines algorithm structure
4. **Type Hierarchies**: Need polymorphism based on type

```python
# Good use of inheritance
class TreeNode:
    """Base class for all tree nodes."""
    def __init__(self, value):
        self.value = value
        self.children = []
    
    def add_child(self, child):
        self.children.append(child)

class FileNode(TreeNode):
    """IS-A TreeNode, adds file-specific behavior."""
    def __init__(self, path):
        super().__init__(path)
        self.size = 0
        self.modified_time = None
```

### Use Composition When:

1. **HAS-A Relationship**: A Car HAS-A Engine
2. **Multiple Behaviors**: Need to mix and match features
3. **Runtime Flexibility**: Want to change behavior at runtime
4. **Testing**: Need to mock/stub dependencies
5. **Avoiding Diamond Problem**: Multiple inheritance gets complex

```python
# Good use of composition
class Car:
    """Car HAS-A engine, wheels, etc."""
    def __init__(self, engine, transmission):
        self.engine = engine  # HAS-A engine
        self.transmission = transmission  # HAS-A transmission
    
    def start(self):
        self.engine.start()
        self.transmission.engage()

# Can mix and match components
sports_car = Car(
    engine=TurboEngine(horsepower=400),
    transmission=ManualTransmission(gears=6)
)

family_car = Car(
    engine=EfficientEngine(mpg=35),
    transmission=AutomaticTransmission()
)
```

---

## Benefits in Practice

### 1. Easier to Test

```python
# With composition, we can inject test doubles
async def test_filtered_adapter():
    # Create a predictable mock
    mock_adapter = MockAdapter(test_data)
    
    # Test filtering in isolation
    filtered = AsyncFilteredFileSystemAdapter(
        base_adapter=mock_adapter,
        include_patterns=['*.py']
    )
    
    result = await filtered.get_children(test_node)
    # Assert filtering worked correctly
```

### 2. More Flexible Configuration

```python
# Users can configure adapters based on their needs
def create_adapter(config):
    # Start with base adapter
    adapter = AsyncFileSystemAdapter(
        max_concurrent=config.get('max_concurrent', 100)
    )
    
    # Add filtering if needed
    if config.get('filters'):
        adapter = AsyncFilteredFileSystemAdapter(
            base_adapter=adapter,
            include_patterns=config['filters']
        )
    
    # Add caching if needed
    if config.get('cache'):
        adapter = CachingTreeAdapter(
            base_adapter=adapter,
            ttl=config['cache']['ttl']
        )
    
    # Add rate limiting if needed
    if config.get('rate_limit'):
        adapter = RateLimitingAdapter(
            base_adapter=adapter,
            max_per_second=config['rate_limit']
        )
    
    return adapter
```

### 3. Better Separation of Concerns

```python
# Each adapter focuses on ONE thing
class LoggingAdapter:
    """ONLY handles logging."""
    def __init__(self, base_adapter, logger):
        self.base_adapter = base_adapter
        self.logger = logger
    
    async def get_children(self, node):
        self.logger.debug(f"Getting children of {node.path}")
        try:
            children = await self.base_adapter.get_children(node)
            self.logger.debug(f"Found {len(children)} children")
            return children
        except Exception as e:
            self.logger.error(f"Error getting children: {e}")
            raise

class MetricsAdapter:
    """ONLY handles metrics."""
    def __init__(self, base_adapter, metrics_client):
        self.base_adapter = base_adapter
        self.metrics = metrics_client
    
    async def get_children(self, node):
        start = time.time()
        try:
            children = await self.base_adapter.get_children(node)
            self.metrics.histogram('get_children.duration', time.time() - start)
            self.metrics.counter('get_children.success')
            return children
        except Exception as e:
            self.metrics.counter('get_children.error')
            raise
```

### 4. Easier to Maintain

```python
# Need to fix a bug in filtering? Only look at ONE class:
class AsyncFilteredFileSystemAdapter:
    # All filtering logic in one place
    # No need to trace through inheritance hierarchy
    # No worry about breaking child classes
    pass

# Compare to inheritance where a change might break:
# - FastFilteredAdapter
# - CachedFilteredAdapter  
# - LoggingFilteredAdapter
# - ... any other subclass
```

---

## Common Pitfalls and How to Avoid Them

### Pitfall 1: Forgetting to Delegate Methods

**Problem**:
```python
class BadWrapper:
    def __init__(self, base):
        self.base = base
    
    async def get_children(self, node):
        # Wrapped this method
        result = await self.base.get_children(node)
        return process(result)
    
    # Forgot to wrap get_node_data()!
    # Users calling wrapper.get_node_data() will fail!
```

**Solution**:
```python
class GoodWrapper:
    def __init__(self, base):
        self.base = base
    
    def __getattr__(self, name):
        """Automatically delegate unknown methods."""
        return getattr(self.base, name)
    
    async def get_children(self, node):
        # Only override what we need
        result = await self.base.get_children(node)
        return process(result)
```

### Pitfall 2: Creating Deep Nesting

**Problem**:
```python
# This gets hard to debug
adapter = Wrapper1(
    Wrapper2(
        Wrapper3(
            Wrapper4(
                Wrapper5(
                    BaseAdapter()
                )
            )
        )
    )
)
```

**Solution**:
```python
# Use a builder or factory
class AdapterBuilder:
    def __init__(self):
        self.adapter = AsyncFileSystemAdapter()
    
    def with_filtering(self, patterns):
        self.adapter = AsyncFilteredFileSystemAdapter(
            base_adapter=self.adapter,
            include_patterns=patterns
        )
        return self
    
    def with_caching(self, ttl=60):
        self.adapter = CachingTreeAdapter(
            base_adapter=self.adapter,
            ttl=ttl
        )
        return self
    
    def build(self):
        return self.adapter

# Clean and readable
adapter = (AdapterBuilder()
    .with_filtering(['*.py'])
    .with_caching(ttl=120)
    .build())
```

### Pitfall 3: Performance Overhead

**Problem**:
```python
# Each wrapper adds a function call
for i in range(1000000):
    await wrapped_wrapped_wrapped_adapter.get_children(node)
    # Multiple delegation layers can add up
```

**Solution**:
```python
# For performance-critical paths, consider:
# 1. Combining related functionality
class FilteredCachingAdapter:
    """Combines filtering and caching for performance."""
    pass

# 2. Or using direct composition
class OptimizedAdapter:
    def __init__(self):
        self.cache = Cache()
        self.filter = Filter()
    
    async def get_children(self, node):
        # Direct calls, no delegation overhead
        if self.cache.has(node):
            return self.cache.get(node)
        
        children = await self._scan_directory(node)
        filtered = self.filter.apply(children)
        self.cache.set(node, filtered)
        return filtered
```

---

## Summary

The move from inheritance to composition in DazzleTreeLib v0.9.0 was a deliberate architectural decision that provides:

1. **Flexibility**: Mix and match features as needed
2. **Testability**: Inject mocks and test in isolation
3. **Maintainability**: Each component has a single responsibility
4. **Extensibility**: Add new features without modifying existing code
5. **Clarity**: Explicit relationships, no hidden inheritance chains

While inheritance still has its place (like our Node class hierarchy), composition gives us the flexibility to build complex behaviors from simple, focused components. This is especially valuable in a library like DazzleTreeLib where users have diverse needs and want to customize behavior without forking the entire codebase.

The key takeaway: **Favor composition over inheritance** when you need flexibility, and use inheritance when you have a clear, stable hierarchy that won't change often.