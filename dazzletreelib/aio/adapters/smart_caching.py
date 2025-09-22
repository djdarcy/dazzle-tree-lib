"""
Smart caching adapter with clean API design.

This module provides the new, cleaner API for DazzleTreeLib v1.0
without backward compatibility constraints.

Migration from CompletenessAwareCacheAdapter:
----------------------------------------------
The SmartCachingAdapter provides cleaner semantics than the old adapter:

Old API (CompletenessAwareCacheAdapter):
    adapter = CompletenessAwareCacheAdapter(base)
    was_visited = adapter.was_node_visited(path)  # Ambiguous!

New API (SmartCachingAdapter):
    adapter = SmartCachingAdapter(base)
    was_seen = adapter.was_discovered(path)  # Clear: encountered
    was_processed = adapter.was_expanded(path)  # Clear: get_children called

Key Differences:
- 'visited' → 'discovered' (node encountered) + 'expanded' (children fetched)
- Depth tracking included by default
- Cleaner configuration via factory functions
- Optional tri-state returns for incomplete cache scenarios

Factory Functions:
    # Bounded cache with tracking
    adapter = create_bounded_cache_adapter(base, max_memory_mb=100)

    # Unlimited cache
    adapter = create_unlimited_cache_adapter(base)

    # Tracking only, no caching
    adapter = create_tracking_only_adapter(base)
"""

from typing import Any, AsyncIterator, Optional, Union, Callable
from pathlib import Path
from abc import ABC, abstractmethod
from enum import Enum

from ..core import AsyncTreeAdapter
from ._cache_store import _LruCacheStore


class TrackingState(Enum):
    """
    Tri-state returns for tracking queries in safe mode.

    Used when cache eviction may have removed tracking data,
    providing honest answers about what we know.
    """
    KNOWN_PRESENT = 1      # Definitely discovered/expanded
    KNOWN_ABSENT = 2       # Definitely not discovered/expanded
    UNKNOWN_EVICTED = 3    # Data was evicted, can't be sure


class TraversalTracker:
    """
    Tracks which nodes were discovered and expanded during tree traversal.

    This provides clear, unambiguous semantics:
    - discovered: All nodes encountered during traversal
    - expanded: Nodes that had get_children() called on them
    - discovered_depths: Depth at which each node was first discovered
    - expanded_depths: Depth at which each node was expanded
    """

    def __init__(self, enable_safe_mode: bool = False):
        """Initialize empty tracking sets and depth maps.

        Args:
            enable_safe_mode: If True, track evicted nodes for tri-state returns
        """
        self.discovered = set()  # All nodes we've seen
        self.expanded = set()    # Nodes we've looked inside
        self.discovered_depths = {}  # {path: depth when discovered}
        self.expanded_depths = {}    # {path: depth when expanded}

        # For tri-state tracking in safe mode
        self.enable_safe_mode = enable_safe_mode
        self.evicted_discovered = set()  # Nodes that were discovered but evicted
        self.evicted_expanded = set()    # Nodes that were expanded but evicted

    def track_discovery(self, path: Union[str, Path], depth: int = 0):
        """Record that a node was discovered at a specific depth."""
        path_str = str(path)
        self.discovered.add(path_str)
        # Only record first discovery depth
        if path_str not in self.discovered_depths:
            self.discovered_depths[path_str] = depth

    def track_expansion(self, path: Union[str, Path], depth: int = 0):
        """Record that a node was expanded (get_children called) at a specific depth."""
        path_str = str(path)
        self.expanded.add(path_str)
        # Record expansion depth (may overwrite if expanded multiple times)
        self.expanded_depths[path_str] = depth

    # Removed track_exposure - not needed since SmartCachingAdapter exposes everything it discovers

    def was_discovered(self, path: Union[str, Path]) -> bool:
        """Check if a node was encountered during traversal."""
        return str(path) in self.discovered

    def was_expanded(self, path: Union[str, Path]) -> bool:
        """Check if get_children() was called on this node."""
        return str(path) in self.expanded

    def was_exposed(self, path: Union[str, Path]) -> bool:
        """For SmartCachingAdapter, exposed is same as discovered."""
        return self.was_discovered(path)

    def get_discovery_depth(self, path: Union[str, Path]) -> Optional[int]:
        """Get the depth at which a node was first discovered."""
        return self.discovered_depths.get(str(path))

    def get_expansion_depth(self, path: Union[str, Path]) -> Optional[int]:
        """Get the depth at which a node was expanded."""
        return self.expanded_depths.get(str(path))

    def get_exposure_depth(self, path: Union[str, Path]) -> Optional[int]:
        """For SmartCachingAdapter, exposure depth is discovery depth."""
        return self.get_discovery_depth(path)

    def get_discovered_count(self) -> int:
        """Get number of discovered nodes."""
        return len(self.discovered)

    def get_expanded_count(self) -> int:
        """Get number of expanded nodes."""
        return len(self.expanded)

    def get_discovery_state(self, path: Union[str, Path]) -> TrackingState:
        """Get tri-state discovery status for safe mode.

        Returns:
            TrackingState indicating if node was discovered, not discovered, or unknown
        """
        path_str = str(path)
        if path_str in self.discovered:
            return TrackingState.KNOWN_PRESENT
        elif self.enable_safe_mode and path_str in self.evicted_discovered:
            return TrackingState.UNKNOWN_EVICTED
        else:
            return TrackingState.KNOWN_ABSENT

    def get_expansion_state(self, path: Union[str, Path]) -> TrackingState:
        """Get tri-state expansion status for safe mode.

        Returns:
            TrackingState indicating if node was expanded, not expanded, or unknown
        """
        path_str = str(path)
        if path_str in self.expanded:
            return TrackingState.KNOWN_PRESENT
        elif self.enable_safe_mode and path_str in self.evicted_expanded:
            return TrackingState.UNKNOWN_EVICTED
        else:
            return TrackingState.KNOWN_ABSENT

    def get_exposure_state(self, path: Union[str, Path]) -> TrackingState:
        """Get tri-state exposure status for safe mode.

        For SmartCachingAdapter, exposure state equals discovery state.

        Returns:
            TrackingState indicating if node was exposed, not exposed, or unknown
        """
        return self.get_discovery_state(path)

    def mark_evicted(self, path: Union[str, Path]):
        """Mark a node's tracking data as evicted (safe mode only).

        When LRU eviction happens, we can track that we once knew about this node.
        """
        if not self.enable_safe_mode:
            return

        path_str = str(path)
        if path_str in self.discovered:
            self.evicted_discovered.add(path_str)
            self.discovered.discard(path_str)
            self.discovered_depths.pop(path_str, None)

        if path_str in self.expanded:
            self.evicted_expanded.add(path_str)
            self.expanded.discard(path_str)
            self.expanded_depths.pop(path_str, None)

        # No need to track exposure eviction - exposure equals discovery

    def clear(self):
        """Reset all tracking for a new traversal."""
        self.discovered.clear()
        self.expanded.clear()
        self.discovered_depths.clear()
        self.expanded_depths.clear()
        if self.enable_safe_mode:
            self.evicted_discovered.clear()
            self.evicted_expanded.clear()


class SmartCachingAdapter(AsyncTreeAdapter):
    """
    Tree adapter with intelligent caching and traversal tracking.

    This is the 'batteries included' adapter that provides:
    - Caching with configurable memory bounds
    - Traversal tracking (discovery vs expansion)
    - Cache invalidation
    - Clear, unambiguous API

    This replaces the confusingly-named CompletenessAwareCacheAdapter.
    """

    def __init__(self,
                 base_adapter: AsyncTreeAdapter,
                 max_memory_mb: int = 100,
                 track_traversal: bool = True,
                 validation_ttl_seconds: float = 5.0,
                 max_cache_depth: int = 50,
                 max_path_depth: int = 30,
                 max_tracked_nodes: int = 10000,
                 enable_safe_mode: bool = False):
        """
        Initialize smart caching adapter.

        Args:
            base_adapter: The underlying tree adapter to wrap
            max_memory_mb: Maximum cache memory in MB (0 = unlimited, -1 = no cache)
            track_traversal: Whether to track discovered/expanded nodes
            validation_ttl_seconds: Time to trust cached data without revalidation
                                   (0=always validate, -1=never validate)
            max_cache_depth: Maximum depth level to cache (0 = unlimited)
            max_path_depth: Maximum path components to cache (0 = unlimited)
            max_tracked_nodes: Maximum nodes to track (0 = unlimited)
            enable_safe_mode: Enable tri-state tracking for LRU eviction awareness
        """
        super().__init__()
        self.base_adapter = base_adapter

        # Store configuration
        self.validation_ttl_seconds = validation_ttl_seconds
        self.max_cache_depth = max_cache_depth
        self.max_path_depth = max_path_depth
        self.max_tracked_nodes = max_tracked_nodes

        # Set up tracking if requested
        self.enable_safe_mode = enable_safe_mode
        self.tracker = TraversalTracker(enable_safe_mode=enable_safe_mode) if track_traversal else None

        # Set up caching based on memory limit
        if max_memory_mb < 0:
            # Negative = no caching at all
            self._cache = None
        elif max_memory_mb == 0:
            # Zero = unlimited cache
            self._cache = _LruCacheStore(
                enable_protection=False,
                eviction_callback=self._on_cache_eviction if enable_safe_mode else None
            )
        else:
            # Positive = bounded cache
            self._cache = _LruCacheStore(
                enable_protection=True,
                max_memory_mb=max_memory_mb,
                eviction_callback=self._on_cache_eviction if enable_safe_mode else None
            )

        # Statistics
        self.cache_hits = 0
        self.cache_misses = 0

    async def get_children(self, node: Any, use_cache: bool = True) -> AsyncIterator[Any]:
        """
        Get children of a node, with caching and tracking.

        This method:
        1. Tracks the node as expanded (if tracking enabled)
        2. Checks cache for results (if caching enabled and use_cache=True)
        3. Fetches from base adapter if needed
        4. Tracks discovered children (if tracking enabled)
        5. Caches results (if caching enabled)

        Args:
            node: The node to get children for
            use_cache: If False, bypass cache and fetch directly from source

        Yields:
            Children of the node
        """
        # Extract path from node - normalize to forward slashes for consistency
        if hasattr(node, 'path'):
            path = str(node.path).replace('\\', '/')
        else:
            path = str(node).replace('\\', '/')

        # Get depth first as we need it for tracking
        depth = 1  # Default depth
        try:
            depth = await self.base_adapter.get_depth(node)
        except:
            pass  # Use default depth if base adapter doesn't support get_depth

        # Track this node as expanded (and discovered if not already)
        if self.tracker:
            # Check tracking limits
            if self.max_tracked_nodes > 0 and self.tracker.get_discovered_count() >= self.max_tracked_nodes:
                # Tracking limit reached, clear oldest entries
                self.tracker.clear()
            self.tracker.track_discovery(path, depth)  # Ensure it's marked as discovered with depth
            self.tracker.track_expansion(path, depth)  # And mark as expanded with depth

        # Determine if we should cache (early exit for performance)
        should_cache = use_cache and self._cache

        # Check if we should skip caching based on depth limits
        if should_cache and (self.max_cache_depth > 0 or self.max_path_depth > 0):
            if self.max_cache_depth > 0 and depth > self.max_cache_depth:
                should_cache = False  # Too deep to cache

            # Check path depth limit only if still caching
            if should_cache and self.max_path_depth > 0:
                path_parts = path.split('/')
                if len(path_parts) > self.max_path_depth:
                    should_cache = False  # Path too long to cache

        # Check cache if enabled
        if should_cache:
            # Create cache key with actual depth
            cache_key = (str(path), depth)
            cached_entry = self._cache.get(cache_key)

            if cached_entry and self._should_use_cached_entry(cached_entry):
                # Cache hit
                self.cache_hits += 1
                # Track cached children as discovered and exposed
                for child in cached_entry.data:
                    if self.tracker:
                        if hasattr(child, 'path'):
                            child_path = str(child.path).replace('\\', '/')
                        else:
                            child_path = str(child).replace('\\', '/')
                        self.tracker.track_discovery(child_path, depth + 1)  # Children are at depth+1
                        # No need to track exposure - SmartCachingAdapter exposes everything it discovers
                    yield child
                return

            # Cache miss
            self.cache_misses += 1

        # Fetch from base adapter
        children = []
        async for child in self.base_adapter.get_children(node):
            children.append(child)

            # Track as discovered at depth+1
            if self.tracker:
                if hasattr(child, 'path'):
                    child_path = str(child.path).replace('\\', '/')
                else:
                    child_path = str(child).replace('\\', '/')
                self.tracker.track_discovery(child_path, depth + 1)  # Children are at depth+1
                # No need to track exposure - SmartCachingAdapter exposes everything it discovers

            yield child

        # Cache the results if caching was enabled for this depth
        if should_cache:
            # Create cache entry with metadata
            import time
            from collections import namedtuple
            CacheEntry = namedtuple('CacheEntry', ['data', 'depth', 'size_estimate', 'cached_at'])
            entry = CacheEntry(
                data=children,
                depth=depth,
                size_estimate=len(children) * 100,
                cached_at=time.time()
            )

            cache_key = (str(path), depth)
            self._cache.put(cache_key, entry)

    # Clean, unambiguous public API

    def was_discovered(self, path: Union[str, Path]) -> bool:
        """
        Check if a node was encountered during traversal.

        Args:
            path: Path to check

        Returns:
            True if the node was discovered, False otherwise
        """
        return self.tracker.was_discovered(path) if self.tracker else False

    def was_expanded(self, path: Union[str, Path]) -> bool:
        """
        Check if get_children() was called on this node.

        Args:
            path: Path to check

        Returns:
            True if the node was expanded, False otherwise
        """
        return self.tracker.was_expanded(path) if self.tracker else False

    def was_exposed(self, path: Union[str, Path]) -> bool:
        """
        Check if this node was yielded to the layer above.

        For SmartCachingAdapter, this is equivalent to was_discovered()
        because this adapter doesn't filter - it yields everything it sees.
        The distinction only matters for adapters that filter internally.

        Args:
            path: Path to check

        Returns:
            True if the node was yielded upward, False otherwise
        """
        # SmartCachingAdapter yields everything it discovers
        return self.was_discovered(path)

    def was_filtered(self, path: Union[str, Path]) -> bool:
        """
        Check if this node was discovered but not exposed (i.e., filtered).

        For SmartCachingAdapter, this always returns False because
        this adapter doesn't filter - everything discovered is also exposed.

        Args:
            path: Path to check

        Returns:
            Always False for SmartCachingAdapter
        """
        # SmartCachingAdapter doesn't filter anything
        return False

    async def invalidate(self, path: Union[str, Path] = None, deep: bool = False) -> int:
        """
        Invalidate cache entries (async for API compatibility).

        Args:
            path: Path pattern to invalidate (None = all)
            deep: If True, invalidate all descendants

        Returns:
            Number of entries invalidated
        """
        if not self._cache:
            return 0
        return self._cache.invalidate(str(path) if path else None, deep)

    def invalidate_cache(self, path: Union[str, Path] = None, deep: bool = False) -> int:
        """
        Invalidate cache entries (sync version).

        Args:
            path: Path pattern to invalidate (None = all)
            deep: If True, invalidate all descendants

        Returns:
            Number of entries invalidated
        """
        if not self._cache:
            return 0
        return self._cache.invalidate(str(path) if path else None, deep)

    async def invalidate_all(self) -> int:
        """
        Invalidate all cache entries.

        Returns:
            Number of entries invalidated
        """
        return await self.invalidate()

    async def invalidate_node(self, node: Any, deep: bool = False) -> int:
        """
        Invalidate cache entries for a specific node.

        Args:
            node: Tree node to invalidate
            deep: If True, also invalidate all descendant nodes

        Returns:
            Number of entries invalidated
        """
        if node is None:
            raise ValueError("Cannot invalidate None node")

        # Extract path from node
        if hasattr(node, 'identifier'):
            # AsyncTreeNode compatible
            path = await node.identifier()
        elif hasattr(node, 'path'):
            path = str(node.path)
        else:
            path = str(node)

        return await self.invalidate(path, deep=deep)

    async def invalidate_nodes(self,
                              nodes: list,
                              deep: bool = False,
                              ignore_errors: bool = False) -> int:
        """
        Invalidate cache entries for multiple nodes.

        Args:
            nodes: Iterable of tree nodes to invalidate
            deep: If True, also invalidate all descendants
            ignore_errors: If True, continue on errors (default: False)

        Returns:
            Total number of entries invalidated
        """
        total = 0
        for node in nodes:
            try:
                count = await self.invalidate_node(node, deep=deep)
                total += count
            except Exception:
                if not ignore_errors:
                    raise
        return total

    def clear_cache(self):
        """Clear all cached data."""
        if self._cache:
            self._cache.clear()

    def clear_tracking(self):
        """Reset traversal tracking for a new traversal."""
        if self.tracker:
            self.tracker.clear()

    def get_cache_stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache metrics
        """
        stats = {
            'cache_enabled': self._cache is not None,
            'tracking_enabled': self.tracker is not None,
        }

        if self._cache:
            cache_stats = self._cache.get_stats()
            stats.update(cache_stats)
            stats['hit_rate'] = (
                self.cache_hits / (self.cache_hits + self.cache_misses)
                if (self.cache_hits + self.cache_misses) > 0
                else 0
            )

        if self.tracker:
            stats['discovered_nodes'] = self.tracker.get_discovered_count()
            stats['expanded_nodes'] = self.tracker.get_expanded_count()
            # Add depth tracking info
            if self.tracker.discovered_depths:
                depths = list(self.tracker.discovered_depths.values())
                stats['max_discovered_depth'] = max(depths) if depths else 0
                stats['avg_discovered_depth'] = sum(depths) / len(depths) if depths else 0
            if self.tracker.expanded_depths:
                depths = list(self.tracker.expanded_depths.values())
                stats['max_expanded_depth'] = max(depths) if depths else 0
                stats['avg_expanded_depth'] = sum(depths) / len(depths) if depths else 0

        return stats

    def get_stats(self) -> dict:
        """
        Get comprehensive statistics (alias for get_cache_stats).

        Returns:
            Dictionary with cache metrics, tracking info, and depth statistics
        """
        return self.get_cache_stats()

    def get_discovered_nodes(self) -> set:
        """Get the set of all discovered node paths."""
        return self.tracker.discovered.copy() if self.tracker else set()

    def get_expanded_nodes(self) -> set:
        """Get the set of all expanded node paths."""
        return self.tracker.expanded.copy() if self.tracker else set()

    def get_discovery_depth(self, path: Union[str, Path]) -> Optional[int]:
        """Get the depth at which a node was first discovered."""
        return self.tracker.get_discovery_depth(path) if self.tracker else None

    def get_expansion_depth(self, path: Union[str, Path]) -> Optional[int]:
        """Get the depth at which a node was expanded."""
        return self.tracker.get_expansion_depth(path) if self.tracker else None

    def get_discovery_state(self, path: Union[str, Path]) -> Optional[TrackingState]:
        """Get tri-state discovery status (safe mode only).

        Returns:
            TrackingState if tracking enabled, None otherwise
        """
        return self.tracker.get_discovery_state(path) if self.tracker else None

    def get_expansion_state(self, path: Union[str, Path]) -> Optional[TrackingState]:
        """Get tri-state expansion status (safe mode only).

        Returns:
            TrackingState if tracking enabled, None otherwise
        """
        return self.tracker.get_expansion_state(path) if self.tracker else None

    def _should_use_cached_entry(self, entry) -> bool:
        """
        Check if a cached entry is still valid based on TTL.

        Args:
            entry: Cache entry to validate

        Returns:
            True if entry is still valid, False if expired
        """
        if self.validation_ttl_seconds < 0:
            # Never validate, always use cache
            return True

        if self.validation_ttl_seconds == 0:
            # Always validate, never use cache
            return False

        # Check if entry has cached_at attribute
        if not hasattr(entry, 'cached_at'):
            # Old entry format, consider expired
            return False

        import time
        age = time.time() - entry.cached_at
        return age <= self.validation_ttl_seconds

    # Required abstract methods from AsyncTreeAdapter
    async def get_parent(self, node: Any) -> Optional[Any]:
        """Get parent of a node (delegates to base adapter)."""
        return await self.base_adapter.get_parent(node)

    async def get_depth(self, node: Any) -> int:
        """Get depth of a node (delegates to base adapter)."""
        return await self.base_adapter.get_depth(node)

    def _on_cache_eviction(self, path: str):
        """Callback when cache evicts an entry.

        Args:
            path: Path that was evicted from cache
        """
        if self.tracker and self.enable_safe_mode:
            self.tracker.mark_evicted(path)


# Convenience factory functions

def create_bounded_cache_adapter(base_adapter: AsyncTreeAdapter,
                                  max_memory_mb: int = 100) -> SmartCachingAdapter:
    """Create an adapter with bounded memory cache."""
    return SmartCachingAdapter(base_adapter, max_memory_mb=max_memory_mb)


def create_unlimited_cache_adapter(base_adapter: AsyncTreeAdapter) -> SmartCachingAdapter:
    """Create an adapter with unlimited cache."""
    return SmartCachingAdapter(base_adapter, max_memory_mb=0)


def create_tracking_only_adapter(base_adapter: AsyncTreeAdapter) -> SmartCachingAdapter:
    """Create an adapter that only tracks, no caching."""
    return SmartCachingAdapter(base_adapter, max_memory_mb=-1, track_traversal=True)


def create_simple_cache_adapter(base_adapter: AsyncTreeAdapter) -> SmartCachingAdapter:
    """Create an adapter with caching but no tracking."""
    return SmartCachingAdapter(base_adapter, max_memory_mb=100, track_traversal=False)